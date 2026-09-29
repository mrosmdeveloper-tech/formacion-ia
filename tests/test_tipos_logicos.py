"""Tests unitarios de ``gestor_json.tipos_logicos``."""

import pytest

from gestor_json.tipos_logicos import TipoLogico, clasificar_valor


@pytest.mark.parametrize("valor, esperado", [
    (None, TipoLogico.NULO),
    (True, TipoLogico.BOOLEANO),
    (False, TipoLogico.BOOLEANO),
    (0, TipoLogico.NUMERO),
    (150, TipoLogico.NUMERO),
    (9.2, TipoLogico.NUMERO),
    (-1.5e3, TipoLogico.NUMERO),
    ("", TipoLogico.TEXTO),
    ("hola", TipoLogico.TEXTO),
    ({}, TipoLogico.OBJETO),
    ({"a": 1}, TipoLogico.OBJETO),
    ([], TipoLogico.LISTA),
    ([1, "a"], TipoLogico.LISTA),
    ((1, 2), TipoLogico.DESCONOCIDO),
    (object(), TipoLogico.DESCONOCIDO),
], ids=repr)
def test_clasificar_valor(valor, esperado):
    assert clasificar_valor(valor) is esperado


@pytest.mark.parametrize("valor", [True, False])
def test_bool_no_es_numero_aunque_sea_subclase_de_int(valor):
    assert isinstance(valor, int)
    assert clasificar_valor(valor) is not TipoLogico.NUMERO


def test_el_valor_del_enum_es_el_nombre_que_se_muestra():
    assert [tipo.value for tipo in TipoLogico] == [
        "booleano", "lista", "numero", "objeto", "texto", "desconocido", "nulo"]
