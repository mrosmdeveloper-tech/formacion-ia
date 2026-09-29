"""Almacenamiento de los tipos registrados en el formato propio (``esquemas.json``)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from gestor_json.config import ARCHIVO_ESQUEMAS
from gestor_json.modelos import CampoEsquema, ErrorGestor, NodoEsquema, TipoRegistrado
from gestor_json.tipos_logicos import TipoLogico

# Códigos de tipo del formato propio. Solo este módulo los conoce.
_CODIGO_DE_TIPO = {
    TipoLogico.BOOLEANO: "bool",
    TipoLogico.LISTA: "list",
    TipoLogico.NUMERO: "num",
    TipoLogico.OBJETO: "obj",
    TipoLogico.TEXTO: "str",
    TipoLogico.DESCONOCIDO: "unk",
}
_TIPO_DE_CODIGO = {codigo: tipo for tipo, codigo in _CODIGO_DE_TIPO.items()}


def esquema_a_dict(nodo: NodoEsquema) -> dict[str, Any]:
    """Convierte un esquema al diccionario del formato propio.

    Un solo tipo se guarda como texto (``"t": "str"``) y una unión como lista. El orden de las
    claves (``t``, ``nulo``, ``campos``, ``item``) forma parte del formato.
    """
    codigos = [_CODIGO_DE_TIPO[tipo] for tipo in nodo.tipos]
    datos: dict[str, Any] = {"t": codigos[0] if len(codigos) == 1 else codigos,
                             "nulo": nodo.admite_nulo}
    if TipoLogico.OBJETO in nodo.tipos:
        datos["campos"] = {
            clave: {"req": campo.obligatorio, "esq": esquema_a_dict(campo.esquema)}
            for clave, campo in nodo.campos.items()
        }
    if TipoLogico.LISTA in nodo.tipos:
        datos["item"] = esquema_a_dict(nodo.elementos)
    return datos


def esquema_desde_dict(datos: dict[str, Any]) -> NodoEsquema:
    """Convierte un diccionario del formato propio en un esquema."""
    codigos = datos["t"] if isinstance(datos["t"], list) else [datos["t"]]
    campos = {
        clave: CampoEsquema(campo["req"], esquema_desde_dict(campo["esq"]))
        for clave, campo in datos.get("campos", {}).items()
    }
    item = esquema_desde_dict(datos["item"]) if "item" in datos else None
    return NodoEsquema(tuple(_TIPO_DE_CODIGO[c] for c in codigos), datos["nulo"], campos, item)


def leer_json(ruta: str | Path) -> Any:
    """Lee un archivo JSON en UTF-8, con o sin BOM."""
    with open(ruta, encoding="utf-8-sig") as archivo:
        return json.load(archivo)


class AlmacenEsquemas(Protocol):
    """Guarda y recupera los tipos registrados. Aísla al resto del programa del formato."""

    def cargar(self) -> dict[str, TipoRegistrado]:
        """Tipos registrados, en orden de registro (vacío si todavía no hay ninguno)."""
        ...

    def guardar(self, tipos: dict[str, TipoRegistrado]) -> None:
        """Sustituye todos los tipos guardados por ``tipos``."""
        ...


class AlmacenEsquemasPropio:
    """Todos los tipos en un único ``esquemas.json`` con el formato propio."""

    def __init__(self, ruta: str | Path = ARCHIVO_ESQUEMAS) -> None:
        self._ruta = Path(ruta)

    def cargar(self) -> dict[str, TipoRegistrado]:
        """Lee ``esquemas.json``; si no existe, no hay tipos registrados."""
        if not self._ruta.exists():
            return {}
        try:
            datos = leer_json(self._ruta)
        except Exception as error:  # noqa: BLE001 - cualquier fallo de lectura se informa igual
            raise ErrorGestor(f"no se puede leer {self._ruta}: {error}") from error
        return {
            nombre: TipoRegistrado(nombre, tipo["patron"], tipo["modelos_usados"],
                                   tipo["registrado"], esquema_desde_dict(tipo["esquema"]))
            for nombre, tipo in datos["tipos"].items()
        }

    def guardar(self, tipos: dict[str, TipoRegistrado]) -> None:
        """Escribe ``esquemas.json`` con sangría de 2 y en UTF-8 sin escapar."""
        datos = {"tipos": {
            nombre: {
                "patron": tipo.patron,
                "modelos_usados": tipo.modelos_usados,
                "registrado": tipo.registrado,
                "esquema": esquema_a_dict(tipo.esquema),
            }
            for nombre, tipo in tipos.items()
        }}
        with open(self._ruta, "w", encoding="utf-8") as archivo:
            json.dump(datos, archivo, indent=2, ensure_ascii=False)
