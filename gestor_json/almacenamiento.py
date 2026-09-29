"""Almacenamiento de los tipos registrados en el formato propio (``esquemas.json``)."""

from __future__ import annotations

from typing import Any

from gestor_json.modelos import CampoEsquema, NodoEsquema
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
        datos["item"] = esquema_a_dict(nodo.item)
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
