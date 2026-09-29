"""Tests unitarios de ``gestor_json.rutas``."""

import pytest

from gestor_json.rutas import RUTA_RAIZ, clave_orden, normalizar, ruta_campo, ruta_elemento


@pytest.mark.parametrize("clave, esperada", [
    ("cliente", "$.cliente"),
    ("_privado", "$._privado"),
    ("campo_2", "$.campo_2"),
    ("zona 1", '$["zona 1"]'),
    ("%grasa", '$["%grasa"]'),
    ("1abc", '$["1abc"]'),
    ("año", '$["año"]'),
    ('con "comillas"', '$["con \\"comillas\\""]'),
    ("", '$[""]'),
])
def test_ruta_campo(clave, esperada):
    assert ruta_campo(RUTA_RAIZ, clave) == esperada


def test_rutas_anidadas():
    ruta = ruta_campo(ruta_elemento(ruta_campo(RUTA_RAIZ, "lineas"), 3), "precio")
    assert ruta == "$.lineas[3].precio"
    assert ruta_campo(ruta_campo(RUTA_RAIZ, "pulso"), "zona 1") == '$.pulso["zona 1"]'


def test_clave_orden_ordena_indices_numericamente_y_padres_antes_que_hijos():
    rutas = ["$.b", "$.a[10]", '$.a[2]["zona 1"]', "$.a[2]", "$"]

    assert sorted(rutas, key=clave_orden) == [
        "$", "$.a[2]", '$.a[2]["zona 1"]', "$.a[10]", "$.b"]


@pytest.mark.parametrize("ruta, clave", [
    ("$", []),
    ("$.cliente.email", [(0, "cliente"), (0, "email")]),
    ("$.lineas[12]", [(0, "lineas"), (1, 12)]),
    ('$.pulso["zona 1"]', [(0, "pulso"), (0, "zona 1")]),
    ('$["con \\"comillas\\""]', [(0, 'con "comillas"')]),
])
def test_clave_orden(ruta, clave):
    assert clave_orden(ruta) == clave


def test_clave_entre_corchetes_y_con_punto_ordenan_igual():
    assert clave_orden('$["zona"]') == clave_orden("$.zona")


@pytest.mark.parametrize("ruta, normalizada", [
    ("$", "$"),
    ("$.cliente.email", "$.cliente.email"),
    ("$.lineas[3].precio", "$.lineas[*].precio"),
    ("$.segmentos[12].puntos[3].lat", "$.segmentos[*].puntos[*].lat"),
    ('$.pulso["zona 1"]', '$.pulso["zona 1"]'),
])
def test_normalizar(ruta, normalizada):
    assert normalizar(ruta) == normalizada
