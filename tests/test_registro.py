"""Tests unitarios de ``gestor_json.registro``.

``RegistroTipos`` se prueba con un almacén en memoria: solo depende de la interfaz
``AlmacenEsquemas``, no de ``esquemas.json``.
"""

import copy
import json
import re

import pytest

from gestor_json.almacenamiento import AlmacenEsquemasPropio
from gestor_json.inferencia import inferir_esquema
from gestor_json.modelos import ErrorGestor, TipoRegistrado
from gestor_json.registro import RegistroTipos, clasificar_archivo, especificidad


class AlmacenEnMemoria:
    """Implementación de ``AlmacenEsquemas`` para tests, que cuenta cuántas veces se guarda."""

    def __init__(self):
        self.tipos = {}
        self.guardados = 0

    def cargar(self):
        return copy.deepcopy(self.tipos)

    def guardar(self, tipos):
        self.tipos = copy.deepcopy(tipos)
        self.guardados += 1


@pytest.fixture
def almacen():
    return AlmacenEnMemoria()


@pytest.fixture
def registro(almacen):
    return RegistroTipos(almacen)


@pytest.fixture
def modelo(tmp_path):
    """Escribe un modelo JSON en una carpeta temporal y devuelve su ruta."""
    def escribir(nombre, contenido):
        ruta = tmp_path / nombre
        ruta.write_text(json.dumps(contenido), encoding="utf-8")
        return str(ruta)
    return escribir


# --------------------------------------------------------------------------- clasificación

@pytest.mark.parametrize("patron, literales", [
    ("pedido_*.json", 12),
    ("pedido_?.json", 12),
    ("*_borrador.json", 14),
    ("*", 0),
    ("*.json", 5),
])
def test_especificidad(patron, literales):
    assert especificidad(patron) == literales


def tipo(nombre, patron):
    return TipoRegistrado(nombre, patron, 1, "2026-09-29T10:00:00", inferir_esquema({}))


TIPOS = {t.nombre: t for t in [
    tipo("pedido", "pedido_*.json"),
    tipo("borrador", "*_borrador.json"),
    tipo("corto", "pedido_?.json"),
]}


@pytest.mark.parametrize("archivo, elegido, candidatos", [
    ("pedido_12.json", "pedido", ["pedido"]),
    ("pedido_7_borrador.json", "borrador", ["pedido", "borrador"]),
    ("pedido_1.json", "pedido", ["pedido", "corto"]),  # empate: gana el registrado primero
    ("informe_1.json", None, []),
    ("PEDIDO_12.json", None, []),  # distingue mayúsculas
    ("pedido_12.json.bak", None, []),
])
def test_clasificar_archivo(archivo, elegido, candidatos):
    clasificacion = clasificar_archivo(archivo, TIPOS)

    assert (clasificacion.tipo.nombre if clasificacion.tipo else None) == elegido
    assert clasificacion.candidatos == candidatos
    assert clasificacion.ambigua == (len(candidatos) > 1)


# --------------------------------------------------------------------------- operaciones

def test_registrar(registro, almacen, modelo):
    tipo_nuevo = registro.registrar("t", "t_*.json", [modelo("m1.json", {"a": 1}),
                                                      modelo("m2.json", {"a": 2, "b": "x"})])

    assert almacen.guardados == 1
    assert almacen.tipos == {"t": tipo_nuevo}
    assert (tipo_nuevo.patron, tipo_nuevo.modelos_usados) == ("t_*.json", 2)
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d", tipo_nuevo.registrado)
    assert tipo_nuevo.esquema.campos["b"].obligatorio is False


def test_registrar_tipo_existente(registro, almacen, modelo):
    registro.registrar("t", "t_*.json", [modelo("m.json", {})])

    with pytest.raises(ErrorGestor, match="el tipo 't' ya existe"):
        registro.registrar("t", "otro_*.json", [modelo("m.json", {})])
    assert almacen.guardados == 1


def test_registrar_modelo_ilegible_no_guarda(registro, almacen, tmp_path):
    roto = tmp_path / "roto.json"
    roto.write_text("{", encoding="utf-8")

    with pytest.raises(ErrorGestor, match="no se puede leer el modelo .*roto.json"):
        registro.registrar("t", "t_*.json", [str(roto)])
    assert almacen.guardados == 0


def test_actualizar_fusiona_y_conserva_la_fecha(registro, almacen, modelo):
    original = registro.registrar("t", "t_*.json", [modelo("m1.json", {"a": 1})])

    actualizado = registro.actualizar("t", [modelo("m2.json", {"a": "x"})])

    assert actualizado.modelos_usados == 2
    assert actualizado.registrado == original.registrado
    assert actualizado.esquema.campos["a"].esquema.describir() == "numero | texto"
    assert almacen.tipos["t"] == actualizado


def test_obtener_y_eliminar(registro, almacen, modelo):
    registro.registrar("t", "t_*.json", [modelo("m.json", {})])

    assert registro.obtener("t").nombre == "t"
    registro.eliminar("t")
    assert almacen.tipos == {}


@pytest.mark.parametrize("operacion", [
    lambda r: r.obtener("nada"),
    lambda r: r.actualizar("nada", []),
    lambda r: r.eliminar("nada"),
], ids=["obtener", "actualizar", "eliminar"])
def test_tipo_inexistente(registro, almacen, operacion):
    with pytest.raises(ErrorGestor, match="el tipo 'nada' no existe"):
        operacion(registro)
    assert almacen.guardados == 0


def test_con_el_almacen_propio_el_esquema_sobrevive_a_guardar_y_cargar(tmp_path, modelo):
    registro = RegistroTipos(AlmacenEsquemasPropio(tmp_path / "esquemas.json"))
    registrado = registro.registrar("t", "t_*.json", [
        modelo("m1.json", {"a": [1, "x"], "b": None, "c": {"zona 1": []}}),
        modelo("m2.json", {"a": [], "b": True})])

    assert RegistroTipos(AlmacenEsquemasPropio(tmp_path / "esquemas.json")).tipos() == {
        "t": registrado}
