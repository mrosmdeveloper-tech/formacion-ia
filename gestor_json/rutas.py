"""Rutas JSONPath de las incidencias: ``$.cliente.email``, ``$.lineas[3].precio``, ``$.pulso["zona 1"]``."""

from __future__ import annotations

import json
import re

RUTA_RAIZ = "$"

_IDENTIFICADOR = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SEGMENTO = re.compile(r'\.([A-Za-z_][A-Za-z0-9_]*)|\[(\d+)\]|\[("(?:[^"\\]|\\.)*")\]')
_INDICE = re.compile(r"\[\d+\]")

# Tipo de cada segmento en la clave de orden (una clave y un índice nunca compiten en la misma
# posición, porque un valor es objeto o lista).
_CLAVE = 0
_POSICION = 1


def ruta_campo(ruta: str, clave: str) -> str:
    """Ruta de un campo: con punto si la clave es un identificador y entre corchetes si no."""
    if _IDENTIFICADOR.match(clave):
        return f"{ruta}.{clave}"
    return f"{ruta}[{json.dumps(clave, ensure_ascii=False)}]"


def ruta_elemento(ruta: str, posicion: int) -> str:
    """Ruta del elemento ``posicion`` de una lista."""
    return f"{ruta}[{posicion}]"


def clave_orden(ruta: str) -> list[tuple[int, str | int]]:
    """Clave para ordenar rutas: por claves y con los índices en orden numérico (``[2]`` < ``[10]``)."""
    clave: list[tuple[int, str | int]] = []
    for segmento in _SEGMENTO.finditer(ruta):
        nombre, posicion, nombre_entre_comillas = segmento.groups()
        if nombre is not None:
            clave.append((_CLAVE, nombre))
        elif posicion is not None:
            clave.append((_POSICION, int(posicion)))
        else:
            clave.append((_CLAVE, json.loads(nombre_entre_comillas)))
    return clave


def normalizar(ruta: str) -> str:
    """Sustituye los índices por ``[*]`` para agrupar las incidencias de todos los elementos."""
    return _INDICE.sub("[*]", ruta)
