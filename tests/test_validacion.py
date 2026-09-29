"""Tests unitarios de ``gestor_json.validacion``."""

import pytest

from gestor_json.config import Categoria, Nivel
from gestor_json.inferencia import inferir_de_modelos
from gestor_json.modelos import TipoRegistrado
from gestor_json.validacion import ValidadorPropio, crear_validador_propio

# id: texto; n: número; ok: booleano; notas: texto | nulo; obj: {x: número};
# lista: [{v: número}]; libre: desconocido | nulo (acepta cualquier cosa)
ESQUEMA = inferir_de_modelos([
    {"id": "a", "n": 1, "ok": True, "notas": "x", "obj": {"x": 1}, "lista": [{"v": 1}],
     "libre": None},
    {"id": "b", "n": 2.5, "ok": False, "notas": None, "obj": {"x": 2}, "lista": [],
     "libre": None},
])


def documento(**cambios):
    """Documento válido con los cambios indicados; un valor ``...`` quita ese campo."""
    doc = {"id": "c", "n": 3, "ok": True, "notas": None, "obj": {"x": 0}, "lista": [{"v": 7}],
           "libre": "lo que sea"}
    doc.update(cambios)
    return {clave: valor for clave, valor in doc.items() if valor is not ...}


CASOS = {
    "válido": (documento(), []),
    "notas admite nulo": (documento(notas=None), []),
    "libre acepta cualquier cosa": (documento(libre={"y": [1, None]}), []),
    "lista vacía": (documento(lista=[]), []),
    "falta un campo": (documento(id=...), [(Nivel.ERROR, Categoria.FALTA_CAMPO, "$.id")]),
    "falta un campo anidado en lista": (
        documento(lista=[{"v": 1}, {}]), [(Nivel.ERROR, Categoria.FALTA_CAMPO, "$.lista[1].v")]),
    "campo extra": (documento(z=1), [(Nivel.AVISO, Categoria.CAMPO_EXTRA, "$.z")]),
    "campo extra con espacio": (
        documento(obj={"x": 1, "zona 1": 2}),
        [(Nivel.AVISO, Categoria.CAMPO_EXTRA, '$.obj["zona 1"]')]),
    "número como texto": (documento(n="3"), [(Nivel.ERROR, Categoria.TIPO_INCORRECTO, "$.n")]),
    "booleano donde va número": (
        documento(n=True), [(Nivel.ERROR, Categoria.TIPO_INCORRECTO, "$.n")]),
    "número donde va booleano": (
        documento(ok=1), [(Nivel.ERROR, Categoria.TIPO_INCORRECTO, "$.ok")]),
    "texto en lugar de objeto": (
        documento(obj="sin datos"), [(Nivel.ERROR, Categoria.TIPO_INCORRECTO, "$.obj")]),
    "nulo no permitido": (
        documento(id=None), [(Nivel.ERROR, Categoria.NULO_NO_PERMITIDO, "$.id")]),
    "elemento de lista con otra forma": (
        documento(lista=[5]), [(Nivel.ERROR, Categoria.TIPO_INCORRECTO, "$.lista[0]")]),
    "raíz que no es objeto": ([], [(Nivel.ERROR, Categoria.TIPO_INCORRECTO, "$")]),
}


def resumen(incidencias):
    return [(i.nivel, i.categoria, i.ruta) for i in incidencias]


@pytest.mark.parametrize("doc, esperadas", CASOS.values(), ids=CASOS.keys())
def test_categorias_de_incidencia(doc, esperadas):
    assert resumen(ValidadorPropio(ESQUEMA).validar(doc)) == esperadas


def test_modo_estricto_convierte_campos_extra_en_error():
    incidencias = ValidadorPropio(ESQUEMA, estricto=True).validar(documento(z=1))

    assert resumen(incidencias) == [(Nivel.ERROR, Categoria.CAMPO_EXTRA, "$.z")]


def test_detalle_de_una_incidencia():
    [incidencia] = ValidadorPropio(ESQUEMA).validar(documento(notas=5))

    assert incidencia.esperado == "texto | nulo"
    assert incidencia.encontrado == "numero"
    assert incidencia.mensaje == "Tipo incorrecto: se esperaba texto | nulo y se encontró numero"


def test_las_incidencias_salen_ordenadas_por_ruta():
    doc = documento(ok="si", id=None, lista=[{"v": "a"}] * 11)

    rutas = [i.ruta for i in ValidadorPropio(ESQUEMA).validar(doc)]

    assert rutas == ["$.id", *[f"$.lista[{n}].v" for n in range(11)], "$.ok"]


def test_el_validador_no_guarda_estado_entre_documentos():
    validador = ValidadorPropio(ESQUEMA)

    assert len(validador.validar(documento(id=None))) == 1
    assert validador.validar(documento()) == []


def test_fabrica_del_validador_propio():
    tipo = TipoRegistrado("t", "t_*.json", 2, "2026-09-29T10:00:00", ESQUEMA)

    validador = crear_validador_propio(tipo, True)

    assert isinstance(validador, ValidadorPropio)
    assert resumen(validador.validar(documento(z=1))) == [
        (Nivel.ERROR, Categoria.CAMPO_EXTRA, "$.z")]
