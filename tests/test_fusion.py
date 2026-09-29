"""Tests unitarios de ``gestor_json.fusion``."""

import copy

import pytest

from gestor_json.fusion import fusionar
from gestor_json.modelos import CampoEsquema, NodoEsquema
from gestor_json.tipos_logicos import TipoLogico as T

TEXTO = NodoEsquema((T.TEXTO,))
NUMERO = NodoEsquema((T.NUMERO,))
BOOLEANO = NodoEsquema((T.BOOLEANO,))
DESCONOCIDO = NodoEsquema((T.DESCONOCIDO,))
DESCONOCIDO_NULO = NodoEsquema((T.DESCONOCIDO,), admite_nulo=True)


def obligatorio(esquema):
    return CampoEsquema(True, esquema)


def opcional(esquema):
    return CampoEsquema(False, esquema)


def objeto(**campos):
    return NodoEsquema((T.OBJETO,), campos=campos)


def lista(item):
    return NodoEsquema((T.LISTA,), item=item)


REGLAS = {
    "mismo tipo": (TEXTO, TEXTO, TEXTO),
    "tipos distintos dan una unión": (NUMERO, TEXTO, NodoEsquema((T.NUMERO, T.TEXTO))),
    "la unión se ordena": (TEXTO, BOOLEANO, NodoEsquema((T.BOOLEANO, T.TEXTO))),
    "desconocido + X da X": (DESCONOCIDO, BOOLEANO, BOOLEANO),
    "desconocido nulo + X da X nulo": (
        DESCONOCIDO_NULO, TEXTO, NodoEsquema((T.TEXTO,), admite_nulo=True)),
    "desconocido + desconocido": (DESCONOCIDO, DESCONOCIDO_NULO, DESCONOCIDO_NULO),
    "el nulo se conserva": (
        NodoEsquema((T.TEXTO,), admite_nulo=True), TEXTO, NodoEsquema((T.TEXTO,), admite_nulo=True)),
    "campo presente en ambos y obligatorio": (
        objeto(a=obligatorio(NUMERO)), objeto(a=obligatorio(NUMERO)), objeto(a=obligatorio(NUMERO))),
    "campo presente solo en uno pasa a opcional": (
        objeto(a=obligatorio(NUMERO)), objeto(b=obligatorio(TEXTO)),
        objeto(a=opcional(NUMERO), b=opcional(TEXTO))),
    "opcional en uno queda opcional": (
        objeto(a=opcional(NUMERO)), objeto(a=obligatorio(NUMERO)), objeto(a=opcional(NUMERO))),
    "los campos se fusionan recursivamente": (
        objeto(a=obligatorio(NUMERO)), objeto(a=obligatorio(TEXTO)),
        objeto(a=obligatorio(NodoEsquema((T.NUMERO, T.TEXTO))))),
    "listas: se fusionan los elementos": (
        lista(DESCONOCIDO), lista(NUMERO), lista(NUMERO)),
    "objeto + texto conserva los campos": (
        objeto(x=obligatorio(NUMERO)), TEXTO,
        NodoEsquema((T.OBJETO, T.TEXTO), campos={"x": obligatorio(NUMERO)})),
    "lista + texto conserva el elemento": (
        TEXTO, lista(NUMERO), NodoEsquema((T.LISTA, T.TEXTO), item=NUMERO)),
}


@pytest.mark.parametrize("a, b, esperado", REGLAS.values(), ids=REGLAS.keys())
def test_reglas_de_fusion(a, b, esperado):
    assert fusionar(a, b) == esperado


@pytest.mark.parametrize("a, b, _", REGLAS.values(), ids=REGLAS.keys())
def test_la_fusion_no_depende_del_orden(a, b, _):
    ab, ba = fusionar(a, b), fusionar(b, a)

    # El orden de los campos puede variar, pero no su contenido.
    assert (ab.tipos, ab.admite_nulo, ab.item) == (ba.tipos, ba.admite_nulo, ba.item)
    assert dict(ab.campos) == dict(ba.campos)


def test_la_fusion_no_modifica_ni_comparte_los_esquemas_de_entrada():
    a = objeto(a=obligatorio(lista(NUMERO)))
    b = TEXTO
    copia_a = copy.deepcopy(a)

    resultado = fusionar(a, b)
    resultado.campos["a"].esquema.item.admite_nulo = True

    assert a == copia_a
