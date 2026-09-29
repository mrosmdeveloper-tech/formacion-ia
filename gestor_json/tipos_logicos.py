"""Tipos lógicos de los valores JSON."""

from enum import Enum


class TipoLogico(Enum):
    """Tipo lógico de un valor JSON; el valor es el nombre que se muestra al usuario.

    El orden de declaración es el orden en que se muestran los tipos de una unión.
    """

    BOOLEANO = "booleano"
    LISTA = "lista"
    NUMERO = "numero"
    OBJETO = "objeto"
    TEXTO = "texto"
    DESCONOCIDO = "desconocido"
    NULO = "nulo"


def clasificar_valor(valor: object) -> TipoLogico:
    """Devuelve el tipo lógico de un valor JSON ya decodificado.

    ``bool`` se comprueba antes que los números porque en Python ``True`` es un ``int``.
    ``int`` y ``float`` son el mismo tipo lógico: número.
    """
    if valor is None:
        return TipoLogico.NULO
    if isinstance(valor, bool):
        return TipoLogico.BOOLEANO
    if isinstance(valor, (int, float)):
        return TipoLogico.NUMERO
    if isinstance(valor, str):
        return TipoLogico.TEXTO
    if isinstance(valor, dict):
        return TipoLogico.OBJETO
    if isinstance(valor, list):
        return TipoLogico.LISTA
    return TipoLogico.DESCONOCIDO
