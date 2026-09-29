"""Migración de los esquemas del formato propio (``esquemas.json``) a JSON Schema."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from gestor_json.almacenamiento import AlmacenEsquemasPropio
from gestor_json.config import MAX_INCIDENCIAS_POR_DEFECTO
from gestor_json.jsonschema_formato import AlmacenEsquemasJsonSchema, crear_validador_jsonschema
from gestor_json.lote import ValidadorLote, listar_archivos
from gestor_json.modelos import ErrorGestor
from gestor_json.validacion import crear_validador_propio


@dataclass
class Verificacion:
    """Resultado de validar los mismos archivos con los dos formatos."""

    archivos: int
    distintos: list[str]
    """Archivos cuyas incidencias no coinciden entre los dos formatos."""

    @property
    def correcta(self) -> bool:
        return not self.distintos


def migrar(desde: str | Path, hacia: str | Path) -> list[str]:
    """Copia todos los tipos de ``desde`` (formato propio) a la carpeta ``hacia`` (JSON Schema).

    Conserva el patrón, los modelos usados, la fecha de registro y el orden de registro. No
    sobrescribe una carpeta que ya tenga tipos. Devuelve los nombres de los tipos migrados.
    """
    if not Path(desde).exists():
        raise ErrorGestor(f"no existe {desde}")
    destino = AlmacenEsquemasJsonSchema(hacia)
    if destino.cargar():
        raise ErrorGestor(f"{hacia} ya contiene tipos registrados; elige otra carpeta o bórrala")
    tipos = AlmacenEsquemasPropio(desde).cargar()
    if not tipos:
        raise ErrorGestor(f"no hay tipos que migrar en {desde}")
    destino.guardar(tipos)
    return list(tipos)


def verificar(desde: str | Path, hacia: str | Path, datos: str | Path) -> Verificacion:
    """Valida ``datos`` con los dos formatos, en modo normal y estricto, y compara el resultado.

    Compara las incidencias completas (nivel, categoría, ruta, esperado, encontrado y mensaje) y
    la clasificación de cada archivo.
    """
    if not Path(datos).exists():
        raise ErrorGestor(f"no existe {datos}")
    propio = AlmacenEsquemasPropio(desde).cargar()
    jsonschema = AlmacenEsquemasJsonSchema(hacia).cargar()
    archivos = listar_archivos(datos)
    distintos: list[str] = []
    for estricto in (False, True):
        lote_propio = ValidadorLote(propio, estricto, MAX_INCIDENCIAS_POR_DEFECTO,
                                    crear_validador_propio)
        lote_jsonschema = ValidadorLote(jsonschema, estricto, MAX_INCIDENCIAS_POR_DEFECTO,
                                        crear_validador_jsonschema)
        for archivo in archivos:
            if (lote_propio.validar_archivo(archivo) != lote_jsonschema.validar_archivo(archivo)
                    and archivo.name not in distintos):
                distintos.append(archivo.name)
    return Verificacion(len(archivos), distintos)
