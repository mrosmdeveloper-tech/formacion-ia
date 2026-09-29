"""Deducción del esquema de un documento JSON."""

from __future__ import annotations

from functools import reduce
from typing import Any

from gestor_json.fusion import fusionar
from gestor_json.modelos import CampoEsquema, NodoEsquema
from gestor_json.tipos_logicos import TipoLogico, clasificar_valor


def inferir_esquema(valor: Any) -> NodoEsquema:
    """Deduce el esquema de un valor JSON.

    - Objeto: cada clave es un campo obligatorio con su esquema deducido.
    - Lista: el esquema de sus elementos es la fusión de todos ellos; vacía, ``desconocido``.
    - ``null``: ``desconocido`` admitiendo nulo (un modelo posterior puede concretarlo).
    - Resto: su tipo lógico (``int`` y ``float`` son número).
    """
    tipo = clasificar_valor(valor)
    if tipo is TipoLogico.NULO:
        return NodoEsquema((TipoLogico.DESCONOCIDO,), admite_nulo=True)
    if tipo is TipoLogico.OBJETO:
        campos = {clave: CampoEsquema(True, inferir_esquema(v)) for clave, v in valor.items()}
        return NodoEsquema((TipoLogico.OBJETO,), campos=campos)
    if tipo is TipoLogico.LISTA:
        if valor:
            item = reduce(fusionar, (inferir_esquema(elemento) for elemento in valor))
        else:
            item = NodoEsquema((TipoLogico.DESCONOCIDO,))
        return NodoEsquema((TipoLogico.LISTA,), item=item)
    return NodoEsquema((tipo,))


def inferir_de_modelos(modelos: list[Any]) -> NodoEsquema:
    """Esquema que admite todos los modelos: la fusión de sus esquemas deducidos."""
    return reduce(fusionar, (inferir_esquema(modelo) for modelo in modelos))
