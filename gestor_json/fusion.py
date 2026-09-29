"""Fusión de esquemas: combina lo que dicen dos modelos (o dos elementos de una lista)."""

from __future__ import annotations

import copy

from gestor_json.modelos import CampoEsquema, NodoEsquema
from gestor_json.tipos_logicos import TipoLogico

_ORDEN_DE_TIPOS = list(TipoLogico)


def fusionar(a: NodoEsquema, b: NodoEsquema) -> NodoEsquema:
    """Devuelve un esquema nuevo que admite lo que admiten ``a`` y ``b``, sin modificarlos.

    Reglas:

    - Mismo tipo: se conserva; en objetos y listas se fusiona recursivamente.
    - Tipos distintos: unión de ambos.
    - ``desconocido`` + X: X (desconocido solo queda si no hay nada más).
    - Admite nulo si lo admite cualquiera de los dos.
    - En objetos, un campo es obligatorio solo si lo es en los dos; si falta en uno, es opcional.
    """
    tipos = set(a.tipos) | set(b.tipos)
    if len(tipos) > 1:
        tipos.discard(TipoLogico.DESCONOCIDO)
    resultado = NodoEsquema(tuple(sorted(tipos, key=_ORDEN_DE_TIPOS.index)),
                            a.admite_nulo or b.admite_nulo)
    if TipoLogico.OBJETO in tipos:
        resultado.campos = _fusionar_campos(a, b)
    if TipoLogico.LISTA in tipos:
        resultado.item = _fusionar_items(a, b)
    return resultado


def _fusionar_campos(a: NodoEsquema, b: NodoEsquema) -> dict[str, CampoEsquema]:
    a_es_objeto = TipoLogico.OBJETO in a.tipos
    b_es_objeto = TipoLogico.OBJETO in b.tipos
    if not (a_es_objeto and b_es_objeto):
        return copy.deepcopy(a.campos if a_es_objeto else b.campos)

    campos: dict[str, CampoEsquema] = {}
    for clave, campo_a in a.campos.items():
        campo_b = b.campos.get(clave)
        if campo_b is None:
            campos[clave] = CampoEsquema(False, copy.deepcopy(campo_a.esquema))
        else:
            campos[clave] = CampoEsquema(campo_a.obligatorio and campo_b.obligatorio,
                                         fusionar(campo_a.esquema, campo_b.esquema))
    for clave, campo_b in b.campos.items():
        if clave not in a.campos:
            campos[clave] = CampoEsquema(False, copy.deepcopy(campo_b.esquema))
    return campos


def _fusionar_items(a: NodoEsquema, b: NodoEsquema) -> NodoEsquema:
    if a.item is not None and b.item is not None:
        return fusionar(a.item, b.item)
    return copy.deepcopy(a.item if a.item is not None else b.item)
