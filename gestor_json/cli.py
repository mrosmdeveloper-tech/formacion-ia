"""Interfaz de línea de comandos: argumentos, orquestación de los comandos y códigos de salida.

Códigos de salida: 0 si todo ha ido bien (en ``validar``, si no hay errores), 1 si ``validar``
encuentra errores y 2 si falla la ejecución (argumentos incorrectos, archivos ilegibles…).

Los mensajes de error son los del programa original: ``argparse`` no imprime los suyos, sino que
sus errores se traducen a "argumento no reconocido".
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from typing import NoReturn

from gestor_json.almacenamiento import AlmacenEsquemasPropio
from gestor_json.config import MAX_INCIDENCIAS_POR_DEFECTO
from gestor_json.informes import EscritorInformes, escribir_resumen_lote, imprimir_resumen
from gestor_json.lote import ResumenLote, ValidadorLote, listar_archivos
from gestor_json.modelos import ErrorGestor, NodoEsquema
from gestor_json.registro import RegistroTipos
from gestor_json.tipos_logicos import TipoLogico

SALIDA_CORRECTA = 0
SALIDA_CON_ERRORES = 1
SALIDA_FALLO = 2

COMANDOS = ("registrar", "actualizar", "tipos", "mostrar", "eliminar", "validar")

_FALTA_VALOR = re.compile(r"argument (\S+): expected one argument")


class _ParserSinMensajes(argparse.ArgumentParser):
    """``ArgumentParser`` que lanza :class:`ErrorGestor` en lugar de imprimir y salir."""

    def error(self, message: str) -> NoReturn:
        falta_valor = _FALTA_VALOR.match(message)
        if falta_valor:
            raise ErrorGestor(f"argumento no reconocido: {falta_valor.group(1)}")
        raise ErrorGestor(message)


def _crear_parser(programa: str) -> argparse.ArgumentParser:
    opciones = {"add_help": False, "allow_abbrev": False}
    parser = _ParserSinMensajes(prog=programa, **opciones)
    comandos = parser.add_subparsers(dest="comando")

    registrar = comandos.add_parser("registrar", **opciones)
    registrar.add_argument("--tipo")
    registrar.add_argument("--patron")
    registrar.add_argument("--modelo", dest="modelos", action="append", default=[])

    actualizar = comandos.add_parser("actualizar", **opciones)
    actualizar.add_argument("--tipo")
    actualizar.add_argument("--modelo", dest="modelos", action="append", default=[])

    comandos.add_parser("tipos", **opciones)
    for nombre in ("mostrar", "eliminar"):
        comandos.add_parser(nombre, **opciones).add_argument("--tipo")

    validar = comandos.add_parser("validar", **opciones)
    validar.add_argument("ruta", nargs="?")
    validar.add_argument("--salida")
    validar.add_argument("--estricto", action="store_true")
    # Se lee como texto para dar el mensaje de error propio si no es un entero.
    validar.add_argument("--max-incidencias", default=str(MAX_INCIDENCIAS_POR_DEFECTO))
    return parser


def main(argv: list[str] | None = None) -> int:
    """Ejecuta el comando indicado en ``argv`` (por defecto, ``sys.argv[1:]``) y devuelve el código de salida."""
    argv = sys.argv[1:] if argv is None else argv
    programa = os.path.basename(sys.argv[0]) if sys.argv and sys.argv[0] else "main.py"
    if not argv:
        print(f"Uso: python {programa} <comando> [opciones]")
        print(f"Comandos: {', '.join(COMANDOS)}")
        return SALIDA_FALLO
    try:
        if argv[0] not in COMANDOS:
            raise ErrorGestor(f"comando desconocido: {argv[0]}")
        argumentos, sobrantes = _crear_parser(programa).parse_known_args(argv)
        if sobrantes:
            raise ErrorGestor(f"argumento no reconocido: {sobrantes[0]}")
        registro = RegistroTipos(AlmacenEsquemasPropio())
        return _EJECUTORES[argumentos.comando](argumentos, registro)
    except ErrorGestor as error:
        print(f"Error: {error}")
        return SALIDA_FALLO
    except Exception as error:  # noqa: BLE001 - último recurso: nunca una traza al usuario
        print(f"Error inesperado: {error}")
        return SALIDA_FALLO


# --------------------------------------------------------------------------- comandos

def _registrar(argumentos: argparse.Namespace, registro: RegistroTipos) -> int:
    if argumentos.tipo is None or not argumentos.tipo.strip():
        raise ErrorGestor("falta --tipo")
    if argumentos.patron is None or not argumentos.patron.strip():
        raise ErrorGestor("el patrón no puede estar vacío")
    _exigir_modelos(argumentos.modelos)
    registro.registrar(argumentos.tipo, argumentos.patron, argumentos.modelos)
    print(f"Tipo '{argumentos.tipo}' registrado con {len(argumentos.modelos)} modelo(s) "
          f"(patrón: {argumentos.patron})")
    return SALIDA_CORRECTA


def _actualizar(argumentos: argparse.Namespace, registro: RegistroTipos) -> int:
    _exigir_tipo(argumentos.tipo)
    _exigir_modelos(argumentos.modelos)
    tipo = registro.actualizar(argumentos.tipo, argumentos.modelos)
    print(f"Tipo '{tipo.nombre}' actualizado: {tipo.modelos_usados} modelo(s) en total")
    return SALIDA_CORRECTA


def _tipos(argumentos: argparse.Namespace, registro: RegistroTipos) -> int:
    tipos = registro.tipos()
    if not tipos:
        print("No hay tipos registrados")
        return SALIDA_CORRECTA
    print(f"{'TIPO':<20}{'PATRÓN':<22}{'MODELOS':>7}  REGISTRADO")
    for tipo in tipos.values():
        print(f"{tipo.nombre:<20}{tipo.patron:<22}{tipo.modelos_usados:>7}  {tipo.registrado}")
    return SALIDA_CORRECTA


def _mostrar(argumentos: argparse.Namespace, registro: RegistroTipos) -> int:
    _exigir_tipo(argumentos.tipo)
    tipo = registro.obtener(argumentos.tipo)
    print(f"Tipo: {tipo.nombre}")
    print(f"Patrón: {tipo.patron}")
    print(f"Modelos usados: {tipo.modelos_usados}")
    print(f"Registrado: {tipo.registrado}")
    print("Esquema:")
    _imprimir_arbol(tipo.esquema, "$", 0)
    return SALIDA_CORRECTA


def _eliminar(argumentos: argparse.Namespace, registro: RegistroTipos) -> int:
    _exigir_tipo(argumentos.tipo)
    registro.eliminar(argumentos.tipo)
    print(f"Tipo '{argumentos.tipo}' eliminado")
    return SALIDA_CORRECTA


def _validar(argumentos: argparse.Namespace, registro: RegistroTipos) -> int:
    max_incidencias = _leer_max_incidencias(argumentos.max_incidencias)
    if argumentos.ruta is None:
        raise ErrorGestor("falta el archivo o la carpeta a validar")
    if argumentos.salida is None:
        raise ErrorGestor("falta --salida")
    if not os.path.exists(argumentos.ruta):
        raise ErrorGestor(f"no existe {argumentos.ruta}")

    inicio = time.perf_counter()
    tipos = registro.tipos()
    archivos = listar_archivos(argumentos.ruta)
    try:
        informes = EscritorInformes(argumentos.salida)
    except Exception as error:  # noqa: BLE001 - cualquier fallo al crear los informes
        raise ErrorGestor(
            f"no se pueden crear los informes en {argumentos.salida}: {error}") from error
    validador = ValidadorLote(tipos, argumentos.estricto, max_incidencias)
    resumen = ResumenLote.para(tipos)
    with informes:
        for archivo in archivos:
            resultado = validador.validar_archivo(archivo)
            informes.escribir(resultado)
            resumen.agregar(resultado)
    segundos = round(time.perf_counter() - inicio, 3)

    escribir_resumen_lote(argumentos.salida, resumen, segundos)
    imprimir_resumen(argumentos.salida, resumen, segundos)
    return SALIDA_CON_ERRORES if resumen.con_errores else SALIDA_CORRECTA


_EJECUTORES = {
    "registrar": _registrar,
    "actualizar": _actualizar,
    "tipos": _tipos,
    "mostrar": _mostrar,
    "eliminar": _eliminar,
    "validar": _validar,
}


# --------------------------------------------------------------------------- utilidades

def _exigir_tipo(tipo: str | None) -> None:
    if tipo is None:
        raise ErrorGestor("falta --tipo")


def _exigir_modelos(modelos: list[str]) -> None:
    if not modelos:
        raise ErrorGestor("hay que indicar al menos un --modelo")


def _leer_max_incidencias(texto: str) -> int:
    try:
        maximo = int(texto)
    except ValueError:
        raise ErrorGestor("--max-incidencias debe ser un número entero") from None
    if maximo < 1:
        raise ErrorGestor("--max-incidencias debe ser al menos 1")
    return maximo


def _imprimir_arbol(esquema: NodoEsquema, etiqueta: str, nivel: int) -> None:
    """Imprime el esquema como árbol sangrado: una línea por campo o por elemento de lista."""
    print(f"{'  ' * nivel}{etiqueta}: {esquema.describir()}")
    if TipoLogico.OBJETO in esquema.tipos:
        for clave, campo in esquema.campos.items():
            etiqueta_campo = clave if campo.obligatorio else f"{clave} (opcional)"
            _imprimir_arbol(campo.esquema, etiqueta_campo, nivel + 1)
    if TipoLogico.LISTA in esquema.tipos:
        _imprimir_arbol(esquema.item, "[]", nivel + 1)
