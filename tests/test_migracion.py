"""Tests de la migración a JSON Schema y de la exportación a VS Code."""

import json
from pathlib import Path

import pytest

from conftest import DATOS
from gestor_json.almacenamiento import AlmacenEsquemasPropio
from gestor_json.jsonschema_formato import AlmacenEsquemasJsonSchema, exportar_vscode
from gestor_json.migracion import migrar, verificar
from gestor_json.modelos import ErrorGestor

MODELOS = DATOS / "modelos"
DOCUMENTOS = DATOS / "documentos"


@pytest.fixture
def esquemas_propios(ejecutar):
    """Tres tipos registrados en ``esquemas.json`` (formato propio)."""
    for tipo, patron, modelos in [
        ("base", "base_*.json", ["base_1.json", "base_2.json"]),
        ("completo", "c_*.json", ["completo.json"]),
        ("todo", "*_1*.json", ["vacio.json"]),
    ]:
        ejecutar("registrar", "--formato", "propio", "--tipo", tipo, "--patron", patron,
                 *[arg for m in modelos for arg in ("--modelo", MODELOS / m)])
    return Path("esquemas.json")


# --------------------------------------------------------------------------- migración

def test_migrar_conserva_todos_los_datos_y_el_orden(esquemas_propios):
    tipos = migrar("esquemas.json", "esquemas")

    assert tipos == ["base", "completo", "todo"]
    originales = AlmacenEsquemasPropio("esquemas.json").cargar()
    migrados = AlmacenEsquemasJsonSchema("esquemas").cargar()
    assert list(migrados) == list(originales)
    for nombre, original in originales.items():
        migrado = migrados[nombre]
        assert (migrado.patron, migrado.modelos_usados, migrado.registrado, migrado.esquema) == (
            original.patron, original.modelos_usados, original.registrado, original.esquema)


def test_migrar_no_sobrescribe_una_carpeta_con_tipos(esquemas_propios):
    migrar("esquemas.json", "esquemas")

    with pytest.raises(ErrorGestor, match="ya contiene tipos registrados"):
        migrar("esquemas.json", "esquemas")


def test_migrar_sin_origen(ejecutar):
    with pytest.raises(ErrorGestor, match="no existe nada.json"):
        migrar("nada.json", "esquemas")


def test_migrar_sin_tipos(ejecutar):
    Path("esquemas.json").write_text('{"tipos": {}}', encoding="utf-8")

    with pytest.raises(ErrorGestor, match="no hay tipos que migrar"):
        migrar("esquemas.json", "esquemas")


def test_verificacion_correcta(esquemas_propios):
    migrar("esquemas.json", "esquemas")

    verificacion = verificar("esquemas.json", "esquemas", DOCUMENTOS)

    assert verificacion.correcta
    assert verificacion.archivos == 12


def test_verificacion_detecta_diferencias(esquemas_propios):
    migrar("esquemas.json", "esquemas")
    esquema = json.loads(Path("esquemas/base.schema.json").read_text(encoding="utf-8"))
    esquema["properties"]["cantidad"]["minimum"] = 3
    Path("esquemas/base.schema.json").write_text(json.dumps(esquema), encoding="utf-8")

    verificacion = verificar("esquemas.json", "esquemas", DOCUMENTOS)

    assert not verificacion.correcta
    assert "base_valido.json" in verificacion.distintos  # cantidad 2 < 3


def test_verificar_datos_inexistentes(esquemas_propios):
    migrar("esquemas.json", "esquemas")

    with pytest.raises(ErrorGestor, match="no existe nada"):
        verificar("esquemas.json", "esquemas", "nada")


# --------------------------------------------------------------------------- comando migrar-esquemas

def test_comando_migrar_con_verificacion(ejecutar, esquemas_propios):
    codigo, salida = ejecutar("migrar-esquemas", "--verificar", DOCUMENTOS)

    assert codigo == 0
    assert salida == (
        "Migrados 3 tipo(s) de esquemas.json a esquemas: base, completo, todo\n"
        f"Verificación con {DOCUMENTOS}: 12 archivo(s), mismas incidencias con los dos formatos\n")
    assert ejecutar("tipos")[1] == ejecutar("tipos", "--formato", "propio")[1]


def test_comando_migrar_sin_verificacion(ejecutar, esquemas_propios):
    codigo, salida = ejecutar("migrar-esquemas", "--desde", "esquemas.json", "--hacia", "otra")

    assert codigo == 0
    assert salida.splitlines() == [
        "Migrados 3 tipo(s) de esquemas.json a otra: base, completo, todo",
        "Sin verificación: usa --verificar <archivo_o_carpeta> para comparar las incidencias "
        "con los dos formatos",
    ]


def test_comando_migrar_con_diferencias(ejecutar, esquemas_propios, monkeypatch):
    import gestor_json.migracion as migracion

    original = migracion.migrar

    def migrar_y_editar(desde, hacia):
        tipos = original(desde, hacia)
        ruta = Path(hacia) / "base.schema.json"
        esquema = json.loads(ruta.read_text(encoding="utf-8"))
        esquema["properties"]["id"]["maxLength"] = 1
        ruta.write_text(json.dumps(esquema), encoding="utf-8")
        return tipos

    monkeypatch.setattr(migracion, "migrar", migrar_y_editar)

    codigo, salida = ejecutar("migrar-esquemas", "--verificar", DOCUMENTOS)

    assert codigo == 1
    assert "archivo(s) con incidencias distintas: base_bom.json" in salida


def test_comando_migrar_con_error(ejecutar):
    assert ejecutar("migrar-esquemas") == (2, "Error: no existe esquemas.json\n")


# --------------------------------------------------------------------------- exportar a VS Code

def test_exportar_vscode_crea_la_configuracion(ejecutar, esquemas_propios):
    migrar("esquemas.json", "esquemas")

    codigo, salida = ejecutar("exportar-vscode")

    assert codigo == 0
    assert salida.startswith("3 esquema(s) asociados en .vscode/settings.json")
    assert json.loads(Path(".vscode/settings.json").read_text(encoding="utf-8")) == {
        "json.schemas": [
            {"fileMatch": ["**/base_*.json"], "url": "./esquemas/base.schema.json"},
            {"fileMatch": ["**/c_*.json"], "url": "./esquemas/completo.schema.json"},
            {"fileMatch": ["**/*_1*.json"], "url": "./esquemas/todo.schema.json"},
        ]}


def test_exportar_vscode_conserva_la_configuracion_existente(ejecutar, esquemas_propios):
    migrar("esquemas.json", "esquemas")
    Path(".vscode").mkdir()
    Path(".vscode/settings.json").write_text(json.dumps({
        "editor.tabSize": 2,
        "json.schemas": [
            {"fileMatch": ["x.json"], "url": "https://ejemplo.example/x.json"},
            {"fileMatch": ["**/viejo_*.json"], "url": "./esquemas/viejo.schema.json"},
        ]}), encoding="utf-8")

    exportar_vscode("esquemas", ".vscode/settings.json")

    configuracion = json.loads(Path(".vscode/settings.json").read_text(encoding="utf-8"))
    assert configuracion["editor.tabSize"] == 2
    assert [a["url"] for a in configuracion["json.schemas"]] == [
        "https://ejemplo.example/x.json",
        "./esquemas/base.schema.json",
        "./esquemas/completo.schema.json",
        "./esquemas/todo.schema.json",
    ]


def test_exportar_vscode_con_carpeta_absoluta(esquemas_propios, tmp_path):
    migrar("esquemas.json", tmp_path / "abs")

    exportar_vscode(tmp_path / "abs", "settings.json")

    url = json.loads(Path("settings.json").read_text(encoding="utf-8"))["json.schemas"][0]["url"]
    assert url == (tmp_path / "abs").as_uri() + "/base.schema.json"


def test_exportar_vscode_con_comentarios(ejecutar, esquemas_propios):
    migrar("esquemas.json", "esquemas")
    Path("settings.json").write_text('{\n  // comentario\n}', encoding="utf-8")

    codigo, salida = ejecutar("exportar-vscode", "--salida", "settings.json")

    assert codigo == 2
    assert salida.startswith("Error: no se puede leer settings.json (¿tiene comentarios?)")


def test_exportar_vscode_sin_tipos(ejecutar):
    assert ejecutar("exportar-vscode") == (2, "Error: no hay tipos registrados en esquemas\n")
