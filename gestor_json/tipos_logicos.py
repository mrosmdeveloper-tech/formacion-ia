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
