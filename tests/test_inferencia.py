"""Tests unitarios de ``gestor_json.inferencia``."""

import copy

import pytest

from gestor_json.inferencia import inferir_de_modelos, inferir_esquema
from gestor_json.modelos import CampoEsquema, NodoEsquema
from gestor_json.tipos_logicos import TipoLogico as T

TEXTO = NodoEsquema((T.TEXTO,))
NUMERO = NodoEsquema((T.NUMERO,))
DESCONOCIDO = NodoEsquema((T.DESCONOCIDO,))


def objeto(**campos):
    return NodoEsquema((T.OBJETO,), campos=campos)


def lista(item):
    return NodoEsquema((T.LISTA,), item=item)


@pytest.mark.parametrize("valor, esperado", [
    ("hola", TEXTO),
    ("", TEXTO),
    (150, NUMERO),
    (9.2, NUMERO),
    (True, NodoEsquema((T.BOOLEANO,))),
    (None, NodoEsquema((T.DESCONOCIDO,), admite_nulo=True)),
    ([], lista(DESCONOCIDO)),
    ([1, 2.5], lista(NUMERO)),
    ([1, "uno"], lista(NodoEsquema((T.NUMERO, T.TEXTO)))),
    ([None, 1], lista(NodoEsquema((T.NUMERO,), admite_nulo=True))),
    ({}, objeto()),
    ({"a": 1}, objeto(a=CampoEsquema(True, NUMERO))),
    ([{"a": 1}, {"a": 2, "b": "x"}],
     lista(objeto(a=CampoEsquema(True, NUMERO), b=CampoEsquema(False, TEXTO)))),
], ids=repr)
def test_inferir_esquema(valor, esperado):
    assert inferir_esquema(valor) == esperado


def test_claves_con_espacios_y_simbolos():
    esquema = inferir_esquema({"zona 1": 10, "%grasa": 12.5})

    assert list(esquema.campos) == ["zona 1", "%grasa"]


def test_inferir_no_modifica_el_documento():
    documento = {"a": [{"b": None}, {"c": 1}], "d": []}
    copia = copy.deepcopy(documento)

    inferir_esquema(documento)

    assert documento == copia


def test_inferir_de_modelos_fusiona_todos():
    esquema = inferir_de_modelos([{"a": 1, "b": None}, {"a": 2}, {"a": 3, "b": "x"}])

    assert esquema == objeto(a=CampoEsquema(True, NUMERO),
                             b=CampoEsquema(False, NodoEsquema((T.TEXTO,), admite_nulo=True)))
