"""Formato de esquema JSON Schema (draft 2020-12): conversión, almacenamiento y validación.

Ver la decisión en ``docs/adr/0001-json-schema.md``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gestor_json.almacenamiento import leer_json
from gestor_json.config import ARCHIVO_REGISTRO, CARPETA_ESQUEMAS, EXTENSION_ESQUEMA
from gestor_json.modelos import CampoEsquema, ErrorGestor, NodoEsquema, TipoRegistrado
from gestor_json.tipos_logicos import TipoLogico

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
