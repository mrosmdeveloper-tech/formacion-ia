"""Formato de esquema JSON Schema (draft 2020-12): conversión, almacenamiento y validación.

Ver la decisión en ``docs/adr/0001-json-schema.md``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

from jsonschema import Draft202012Validator, SchemaError, ValidationError

from gestor_json.almacenamiento import leer_json
from gestor_json.config import ARCHIVO_REGISTRO, CARPETA_ESQUEMAS, EXTENSION_ESQUEMA
from gestor_json.modelos import CampoEsquema, ErrorGestor, Incidencia, NodoEsquema, TipoRegistrado
from gestor_json.rutas import RUTA_RAIZ, clave_orden, ruta_campo, ruta_elemento
from gestor_json.tipos_logicos import TipoLogico, clasificar_valor
from gestor_json.validacion import Validador

DIALECTO = "https://json-schema.org/draft/2020-12/schema"

_TIPO_JSON = {
    TipoLogico.BOOLEANO: "boolean",
    TipoLogico.LISTA: "array",
    TipoLogico.NUMERO: "number",
    TipoLogico.OBJETO: "object",
    TipoLogico.TEXTO: "string",
}
_TIPO_LOGICO = {nombre: tipo for tipo, nombre in _TIPO_JSON.items()}
_TIPO_LOGICO["integer"] = TipoLogico.NUMERO  # por si se cambia a mano "number" por "integer"
_NULO = "null"

# Claves que genera la conversión en cada nodo. El resto (minimum, pattern, enum, format,
# description…) son reglas añadidas a mano y se conservan al volver a generar el esquema.
_CLAVES_GENERADAS = frozenset({"$schema", "title", "type", "properties", "required",
                               "additionalProperties", "items", "examples"})


# --------------------------------------------------------------------------- conversión

def nodo_a_jsonschema(nodo: NodoEsquema) -> dict[str, Any]:
    """Convierte un esquema deducido en un (sub)esquema JSON Schema.

    - texto, número, booleano, objeto y lista: ``string``, ``number``, ``boolean``, ``object``
      (con ``properties``, ``required`` y ``additionalProperties: false``) y ``array`` (con
      ``items``).
    - Admite nulo: ``"null"`` en ``type``. Unión: ``type`` como lista.
    - Desconocido: ``{}`` (acepta cualquier valor). Si procede de un ``null`` en los modelos,
      lleva la anotación ``"examples": [null]``, que no afecta a la validación pero conserva la
      información para fusiones posteriores (desconocido nulo + X = X admitiendo nulo).
    """
    if nodo.acepta_cualquier_valor:
        return {"examples": [None]} if nodo.admite_nulo else {}
    tipos = [_TIPO_JSON[tipo] for tipo in nodo.tipos]
    if nodo.admite_nulo:
        tipos.append(_NULO)
    esquema: dict[str, Any] = {"type": tipos[0] if len(tipos) == 1 else tipos}
    if TipoLogico.OBJETO in nodo.tipos:
        esquema["properties"] = {clave: nodo_a_jsonschema(campo.esquema)
                                 for clave, campo in nodo.campos.items()}
        esquema["required"] = [clave for clave, campo in nodo.campos.items() if campo.obligatorio]
        esquema["additionalProperties"] = False
    if TipoLogico.LISTA in nodo.tipos:
        esquema["items"] = nodo_a_jsonschema(nodo.elementos)
    return esquema


def documento_jsonschema(nombre: str, nodo: NodoEsquema,
                         anterior: dict[str, Any] | None = None) -> dict[str, Any]:
    """Esquema completo de un tipo, con ``$schema``, ``title`` y ``description``.

    Si se pasa el esquema ``anterior`` (el que había guardado), se conservan sus reglas añadidas
    a mano en los nodos que siguen existiendo.
    """
    documento: dict[str, Any] = {
        "$schema": DIALECTO,
        "title": nombre,
        "description": (f"Esquema del tipo '{nombre}', deducido de sus modelos por el gestor "
                        "de tipos JSON."),
        **nodo_a_jsonschema(nodo),
    }
    if anterior is not None:
        _conservar_reglas(documento, anterior)
    return documento


def _conservar_reglas(nuevo: dict[str, Any], anterior: dict[str, Any]) -> None:
    """Copia en ``nuevo`` las claves no generadas de ``anterior``, nodo a nodo."""
    for clave, valor in anterior.items():
        if clave not in _CLAVES_GENERADAS or (clave == "examples" and "type" in anterior):
            nuevo[clave] = valor
    for clave, subesquema in nuevo.get("properties", {}).items():
        subanterior = anterior.get("properties", {}).get(clave)
        if isinstance(subanterior, dict):
            _conservar_reglas(subesquema, subanterior)
    if isinstance(nuevo.get("items"), dict) and isinstance(anterior.get("items"), dict):
        _conservar_reglas(nuevo["items"], anterior["items"])


def jsonschema_a_nodo(esquema: dict[str, Any]) -> NodoEsquema:
    """Convierte un (sub)esquema JSON Schema en un esquema deducido.

    Solo se tienen en cuenta ``type``, ``properties``, ``required``, ``items`` y la anotación
    ``examples: [null]`` de los desconocidos; el resto de reglas no forma parte del esquema
    deducido (se conservan en el documento guardado).
    """
    tipos_json = esquema.get("type")
    if tipos_json is None:
        return NodoEsquema((TipoLogico.DESCONOCIDO,), admite_nulo=esquema.get("examples") == [None])
    if isinstance(tipos_json, str):
        tipos_json = [tipos_json]
    try:
        tipos = {_TIPO_LOGICO[t] for t in tipos_json if t != _NULO}
    except KeyError as error:
        raise ErrorGestor(f"tipo de JSON Schema no admitido: {error.args[0]}") from None
    if not tipos:
        raise ErrorGestor("un esquema que solo admite null no está admitido")
    requeridos = set(esquema.get("required", []))
    campos = {clave: CampoEsquema(clave in requeridos, jsonschema_a_nodo(subesquema))
              for clave, subesquema in esquema.get("properties", {}).items()}
    item = jsonschema_a_nodo(esquema.get("items", {})) if TipoLogico.LISTA in tipos else None
    orden = list(TipoLogico)
    return NodoEsquema(tuple(sorted(tipos, key=orden.index)), _NULO in tipos_json, campos, item)


# --------------------------------------------------------------------------- almacenamiento

class AlmacenEsquemasJsonSchema:
    """Un ``<tipo>.schema.json`` por tipo y un índice ``registro.json``, en una carpeta.

    El índice guarda, en orden de registro, el tipo, el patrón, el archivo del esquema, los
    modelos usados y la fecha de registro. Implementa :class:`AlmacenEsquemas`.
    """

    def __init__(self, carpeta: str | Path = CARPETA_ESQUEMAS) -> None:
        self._carpeta = Path(carpeta)
        self._indice = self._carpeta / ARCHIVO_REGISTRO

    def cargar(self) -> dict[str, TipoRegistrado]:
        """Lee el índice y los esquemas; si no hay índice, no hay tipos registrados."""
        if not self._indice.exists():
            return {}
        tipos = {}
        for entrada in self._leer_indice():
            ruta = self._carpeta / entrada["archivo"]
            try:
                esquema_json = leer_json(ruta)
            except Exception as error:  # noqa: BLE001 - cualquier fallo de lectura se informa igual
                raise ErrorGestor(f"no se puede leer el esquema {ruta}: {error}") from error
            nombre = entrada["tipo"]
            tipos[nombre] = TipoRegistrado(nombre, entrada["patron"], entrada["modelos_usados"],
                                           entrada["registrado"], jsonschema_a_nodo(esquema_json),
                                           esquema_json)
        return tipos

    def guardar(self, tipos: dict[str, TipoRegistrado]) -> None:
        """Escribe los esquemas y el índice, y borra los esquemas de los tipos eliminados."""
        anteriores = ({entrada["archivo"] for entrada in self._leer_indice()}
                      if self._indice.exists() else set())
        self._carpeta.mkdir(parents=True, exist_ok=True)
        indice = []
        for nombre, tipo in tipos.items():
            archivo = f"{nombre}{EXTENSION_ESQUEMA}"
            _escribir_json(self._carpeta / archivo,
                           documento_jsonschema(nombre, tipo.esquema, tipo.esquema_json))
            indice.append({"tipo": nombre, "patron": tipo.patron, "archivo": archivo,
                           "modelos_usados": tipo.modelos_usados, "registrado": tipo.registrado})
        _escribir_json(self._indice, {"tipos": indice})
        for archivo in anteriores - {entrada["archivo"] for entrada in indice}:
            (self._carpeta / archivo).unlink(missing_ok=True)

    def _leer_indice(self) -> list[dict[str, Any]]:
        try:
            entradas: list[dict[str, Any]] = leer_json(self._indice)["tipos"]
        except Exception as error:  # noqa: BLE001 - cualquier fallo de lectura se informa igual
            raise ErrorGestor(f"no se puede leer {self._indice}: {error}") from error
        return entradas


def _escribir_json(ruta: Path, datos: Any) -> None:
    with open(ruta, "w", encoding="utf-8") as archivo:
        json.dump(datos, archivo, indent=2, ensure_ascii=False)


# --------------------------------------------------------------------------- validación

_NOMBRE_TIPO = {"string": "texto", "number": "numero", "integer": "entero", "boolean": "booleano",
                "object": "objeto", "array": "lista", _NULO: "nulo"}

# Mensajes de las reglas más habituales; el resto usa el mensaje de jsonschema.
_MENSAJES_REGLA = {
    "minimum": "debe ser mayor o igual que {}",
    "maximum": "debe ser menor o igual que {}",
    "exclusiveMinimum": "debe ser mayor que {}",
    "exclusiveMaximum": "debe ser menor que {}",
    "multipleOf": "debe ser múltiplo de {}",
    "minLength": "debe tener al menos {} caracteres",
    "maxLength": "debe tener como máximo {} caracteres",
    "pattern": "debe seguir el patrón {}",
    "enum": "debe ser uno de {}",
    "const": "debe ser {}",
    "format": "debe tener el formato {}",
    "minItems": "debe tener al menos {} elementos",
    "maxItems": "debe tener como máximo {} elementos",
    "uniqueItems": "no debe tener elementos repetidos",
}


class ValidadorJsonSchema:
    """Validador basado en la librería ``jsonschema`` (draft 2020-12). Implementa :class:`Validador`.

    Se compila una vez por tipo y comprueba los formatos (``email``, ``date-time``…) con el
    ``FormatChecker`` de ``jsonschema``: sin él, ``format`` sería solo una anotación. Traduce los
    errores a las mismas incidencias que el validador propio, más la categoría
    ``regla_incumplida`` para el resto de reglas.
    """

    def __init__(self, esquema: dict[str, Any], estricto: bool = False) -> None:
        """``estricto``: los campos no previstos cuentan como error en lugar de como aviso."""
        try:
            Draft202012Validator.check_schema(esquema)
        except SchemaError as error:
            raise ErrorGestor(f"el esquema '{esquema.get('title', '')}' no es un JSON Schema "
                              f"válido: {error.message}") from error
        self._validador = Draft202012Validator(
            esquema, format_checker=Draft202012Validator.FORMAT_CHECKER)
        self._estricto = estricto

    def validar(self, documento: Any) -> list[Incidencia]:
        """Valida el documento y devuelve sus incidencias ordenadas por ruta."""
        incidencias: list[Incidencia] = []
        objetos_revisados: set[str] = set()
        for error in self._validador.iter_errors(documento):
            ruta = _ruta(error.absolute_path)
            if error.validator == "required":
                # jsonschema da un error por campo que falta; se calculan todos a la vez.
                if ruta not in objetos_revisados:
                    objetos_revisados.add(ruta)
                    incidencias.extend(_campos_que_faltan(error, ruta))
            elif error.validator == "additionalProperties":
                incidencias.extend(self._campos_extra(error, ruta))
            elif error.validator == "type":
                incidencias.append(_tipo_incorrecto(error, ruta))
            else:
                incidencias.append(_regla_incumplida(error, ruta))
        return sorted(incidencias, key=lambda incidencia: clave_orden(incidencia.ruta))

    def _campos_extra(self, error: ValidationError, ruta: str) -> list[Incidencia]:
        subesquema = _subesquema(error)
        previstos = subesquema.get("properties", {})
        patrones = [re.compile(p) for p in subesquema.get("patternProperties", {})]
        objeto: dict[str, Any] = error.instance  # type: ignore[assignment]
        return [
            Incidencia.campo_extra(ruta_campo(ruta, clave), clave, clasificar_valor(valor).value,
                                   self._estricto)
            for clave, valor in objeto.items()
            if clave not in previstos and not any(p.search(clave) for p in patrones)
        ]


def crear_validador_jsonschema(tipo: TipoRegistrado, estricto: bool) -> Validador:
    """Fábrica de validadores JSON Schema: usa el esquema guardado (con sus reglas a mano)."""
    esquema = tipo.esquema_json or documento_jsonschema(tipo.nombre, tipo.esquema)
    return ValidadorJsonSchema(esquema, estricto)


def describir_tipos(esquema: Mapping[str, Any]) -> str:
    """Tipos admitidos por un subesquema, con los mismos nombres que el formato propio."""
    tipos = esquema.get("type")
    if tipos is None:
        nulo = " | nulo" if esquema.get("examples") == [None] else ""
        return TipoLogico.DESCONOCIDO.value + nulo
    if isinstance(tipos, str):
        tipos = [tipos]
    return " | ".join(_NOMBRE_TIPO.get(t, t) for t in tipos)


def _subesquema(error: ValidationError) -> Mapping[str, Any]:
    """Subesquema donde se produjo el error (en los tipos de jsonschema puede ser ``bool``)."""
    return error.schema if isinstance(error.schema, Mapping) else {}


def _ruta(camino: Iterable[str | int]) -> str:
    ruta = RUTA_RAIZ
    for paso in camino:
        ruta = ruta_elemento(ruta, paso) if isinstance(paso, int) else ruta_campo(ruta, paso)
    return ruta


def _campos_que_faltan(error: ValidationError, ruta: str) -> list[Incidencia]:
    propiedades = _subesquema(error).get("properties", {})
    objeto: dict[str, Any] = error.instance  # type: ignore[assignment]
    requeridos: list[str] = error.validator_value  # type: ignore[assignment]
    return [
        Incidencia.falta_campo(ruta_campo(ruta, campo), campo,
                               describir_tipos(propiedades.get(campo, {})))
        for campo in requeridos if campo not in objeto
    ]


def _tipo_incorrecto(error: ValidationError, ruta: str) -> Incidencia:
    esperado = describir_tipos(_subesquema(error))
    if error.instance is None:
        return Incidencia.nulo_no_permitido(ruta, esperado)
    return Incidencia.tipo_incorrecto(ruta, esperado, clasificar_valor(error.instance).value)


def _regla_incumplida(error: ValidationError, ruta: str) -> Incidencia:
    regla = str(error.validator)
    valor = error.validator_value
    valor_texto = valor if isinstance(valor, str) else json.dumps(valor, ensure_ascii=False)
    plantilla = _MENSAJES_REGLA.get(regla)
    detalle = plantilla.format(valor_texto) if plantilla else error.message
    if isinstance(error.instance, (dict, list)):
        encontrado = clasificar_valor(error.instance).value
    else:
        encontrado = json.dumps(error.instance, ensure_ascii=False)
    return Incidencia.regla_incumplida(ruta, regla, f"{regla}: {valor_texto}", encontrado, detalle)


# --------------------------------------------------------------------------- VS Code

CLAVE_ESQUEMAS_VSCODE = "json.schemas"


def asociaciones_vscode(carpeta: str | Path = CARPETA_ESQUEMAS) -> list[dict[str, Any]]:
    """Una asociación de ``json.schemas`` por tipo: su patrón (en cualquier carpeta) y su esquema.

    La URL es relativa a la carpeta del proyecto (``./esquemas/pedido.schema.json``) si la
    carpeta de esquemas es relativa, o ``file://`` si es absoluta.
    """
    carpeta = Path(carpeta)
    base = carpeta.as_uri() if carpeta.is_absolute() else f"./{carpeta.as_posix()}"
    tipos = AlmacenEsquemasJsonSchema(carpeta).cargar()
    if not tipos:
        raise ErrorGestor(f"no hay tipos registrados en {carpeta}")
    return [{"fileMatch": [f"**/{tipo.patron}"], "url": f"{base}/{nombre}{EXTENSION_ESQUEMA}"}
            for nombre, tipo in tipos.items()]


def exportar_vscode(carpeta: str | Path, salida: str | Path) -> int:
    """Escribe en ``salida`` (un ``settings.json`` de VS Code) las asociaciones de los esquemas.

    Si el archivo existe, conserva el resto de la configuración y las asociaciones de otros
    esquemas, y sustituye las de esta carpeta. Devuelve el número de asociaciones escritas.
    """
    salida = Path(salida)
    asociaciones = asociaciones_vscode(carpeta)
    configuracion: dict[str, Any] = {}
    if salida.exists():
        try:
            configuracion = leer_json(salida)
        except Exception as error:  # noqa: BLE001 - cualquier fallo de lectura se informa igual
            raise ErrorGestor(f"no se puede leer {salida} (¿tiene comentarios?): {error}") from error
    nuevas = {asociacion["url"] for asociacion in asociaciones}
    base = asociaciones[0]["url"].rsplit("/", 1)[0] + "/"
    otras = [a for a in configuracion.get(CLAVE_ESQUEMAS_VSCODE, [])
             if a.get("url") not in nuevas and not str(a.get("url", "")).startswith(base)]
    configuracion[CLAVE_ESQUEMAS_VSCODE] = otras + asociaciones
    salida.parent.mkdir(parents=True, exist_ok=True)
    _escribir_json(salida, configuracion)
    return len(asociaciones)
