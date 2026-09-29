"""Tests del formato JSON Schema: conversión, almacén, validador, equivalencia y nuevas reglas."""

import csv
import json
from pathlib import Path

import pytest

from conftest import DATOS, EJEMPLOS
from gestor_json.config import Categoria, Nivel
from gestor_json.inferencia import inferir_de_modelos
from gestor_json.jsonschema_formato import (
    DIALECTO,
    AlmacenEsquemasJsonSchema,
    ValidadorJsonSchema,
    crear_validador_jsonschema,
    describir_tipos,
    documento_jsonschema,
    jsonschema_a_nodo,
    nodo_a_jsonschema,
)
from gestor_json.modelos import CampoEsquema, ErrorGestor, NodoEsquema, TipoRegistrado
from gestor_json.tipos_logicos import TipoLogico as T
from gestor_json.validacion import ValidadorPropio

MODELOS = DATOS / "modelos"
DOCUMENTOS = DATOS / "documentos"
BASE = [MODELOS / "base_1.json", MODELOS / "base_2.json"]


def leer(ruta):
    return json.loads(Path(ruta).read_text(encoding="utf-8"))


def escribir(ruta, datos):
    Path(ruta).write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")


# --------------------------------------------------------------------------- conversión

NUMERO = NodoEsquema((T.NUMERO,))
TEXTO = NodoEsquema((T.TEXTO,))

CONVERSIONES = {
    "texto": (TEXTO, {"type": "string"}),
    "número": (NUMERO, {"type": "number"}),
    "booleano": (NodoEsquema((T.BOOLEANO,)), {"type": "boolean"}),
    "admite nulo": (NodoEsquema((T.TEXTO,), admite_nulo=True), {"type": ["string", "null"]}),
    "unión": (NodoEsquema((T.NUMERO, T.TEXTO)), {"type": ["number", "string"]}),
    "unión con nulo": (NodoEsquema((T.BOOLEANO, T.TEXTO), admite_nulo=True),
                       {"type": ["boolean", "string", "null"]}),
    "desconocido": (NodoEsquema((T.DESCONOCIDO,)), {}),
    "desconocido de un null": (NodoEsquema((T.DESCONOCIDO,), admite_nulo=True),
                               {"examples": [None]}),
    "lista vacía": (NodoEsquema((T.LISTA,), item=NodoEsquema((T.DESCONOCIDO,))),
                    {"type": "array", "items": {}}),
    "lista": (NodoEsquema((T.LISTA,), item=NUMERO), {"type": "array", "items": {"type": "number"}}),
    "objeto con opcional": (
        NodoEsquema((T.OBJETO,), campos={"a": CampoEsquema(True, NUMERO),
                                         "zona 1": CampoEsquema(False, TEXTO)}),
        {"type": "object", "properties": {"a": {"type": "number"}, "zona 1": {"type": "string"}},
         "required": ["a"], "additionalProperties": False}),
    "objeto vacío": (NodoEsquema((T.OBJETO,)),
                     {"type": "object", "properties": {}, "required": [],
                      "additionalProperties": False}),
}


@pytest.mark.parametrize("nodo, esperado", CONVERSIONES.values(), ids=CONVERSIONES.keys())
def test_conversion(nodo, esperado):
    assert nodo_a_jsonschema(nodo) == esperado
    assert jsonschema_a_nodo(esperado) == nodo


@pytest.mark.parametrize("modelos", [
    [MODELOS / "completo.json"],
    BASE,
    *[sorted(EJEMPLOS.glob(f"modelos/{prefijo}_modelo_*.json"))
      for prefijo in ("pedido", "sensor", "ruta")],
], ids=["completo", "base", "pedido", "sensor", "actividad"])
def test_ida_y_vuelta_sin_perdidas(modelos):
    nodo = inferir_de_modelos([leer(m) for m in modelos])

    assert jsonschema_a_nodo(documento_jsonschema("t", nodo)) == nodo


def test_documento_completo_es_un_json_schema_valido():
    documento = documento_jsonschema("base", inferir_de_modelos([leer(m) for m in BASE]))

    assert documento["$schema"] == DIALECTO
    assert documento["title"] == "base"
    assert "base" in documento["description"]
    ValidadorJsonSchema(documento)  # no lanza SchemaError


def test_integer_se_lee_como_numero():
    assert jsonschema_a_nodo({"type": ["integer", "null"]}) == NodoEsquema((T.NUMERO,), True)


@pytest.mark.parametrize("esquema, mensaje", [
    ({"type": "fecha"}, "tipo de JSON Schema no admitido: fecha"),
    ({"type": "null"}, "solo admite null"),
])
def test_tipos_no_admitidos(esquema, mensaje):
    with pytest.raises(ErrorGestor, match=mensaje):
        jsonschema_a_nodo(esquema)


def test_al_regenerar_se_conservan_las_reglas_anadidas_a_mano():
    anterior = documento_jsonschema("t", inferir_de_modelos([{"a": 1, "l": [{"x": "s"}]}]))
    anterior["description"] = "Mi descripción"
    anterior["properties"]["a"]["minimum"] = 1
    anterior["properties"]["l"]["minItems"] = 1
    anterior["properties"]["l"]["items"]["properties"]["x"]["pattern"] = "^s"

    nuevo = documento_jsonschema("t", inferir_de_modelos([{"a": 1, "l": [{"x": "s"}]}, {"a": "b"}]),
                                 anterior)

    assert nuevo["description"] == "Mi descripción"
    assert nuevo["properties"]["a"] == {"type": ["number", "string"], "minimum": 1}
    assert nuevo["properties"]["l"]["minItems"] == 1
    assert nuevo["properties"]["l"]["items"]["properties"]["x"]["pattern"] == "^s"
    assert nuevo["required"] == ["a"]  # lo generado sí se actualiza


def test_describir_tipos():
    assert describir_tipos({"type": ["string", "null"]}) == "texto | nulo"
    assert describir_tipos({"type": "integer"}) == "entero"
    assert describir_tipos({}) == "desconocido"
    assert describir_tipos({"examples": [None]}) == "desconocido | nulo"


# --------------------------------------------------------------------------- almacén

def tipo_registrado(nombre, patron, modelo):
    return TipoRegistrado(nombre, patron, 1, "2026-09-29T10:00:00", inferir_de_modelos([modelo]))


def test_almacen_guarda_indice_y_esquemas_en_orden(tmp_path):
    almacen = AlmacenEsquemasJsonSchema(tmp_path / "esquemas")
    tipos = {"z": tipo_registrado("z", "z_*.json", {"a": 1}),
             "a": tipo_registrado("a", "a_*.json", {"b": None})}

    almacen.guardar(tipos)

    assert leer(tmp_path / "esquemas" / "registro.json") == {"tipos": [
        {"tipo": "z", "patron": "z_*.json", "archivo": "z.schema.json", "modelos_usados": 1,
         "registrado": "2026-09-29T10:00:00"},
        {"tipo": "a", "patron": "a_*.json", "archivo": "a.schema.json", "modelos_usados": 1,
         "registrado": "2026-09-29T10:00:00"},
    ]}
    cargados = almacen.cargar()
    assert list(cargados) == ["z", "a"]
    assert {n: t.esquema for n, t in cargados.items()} == {n: t.esquema for n, t in tipos.items()}
    assert cargados["z"].esquema_json == leer(tmp_path / "esquemas" / "z.schema.json")


def test_almacen_borra_el_esquema_de_un_tipo_eliminado(tmp_path):
    almacen = AlmacenEsquemasJsonSchema(tmp_path)
    almacen.guardar({"a": tipo_registrado("a", "a_*", {}), "b": tipo_registrado("b", "b_*", {})})

    almacen.guardar({"b": tipo_registrado("b", "b_*", {})})

    assert sorted(p.name for p in tmp_path.iterdir()) == ["b.schema.json", "registro.json"]


def test_almacen_sin_indice_no_tiene_tipos(tmp_path):
    assert AlmacenEsquemasJsonSchema(tmp_path / "no_existe").cargar() == {}


def test_almacen_con_indice_corrupto(tmp_path):
    (tmp_path / "registro.json").write_text("{roto", encoding="utf-8")

    with pytest.raises(ErrorGestor, match="no se puede leer .*registro.json"):
        AlmacenEsquemasJsonSchema(tmp_path).cargar()


def test_almacen_con_esquema_que_falta(tmp_path):
    almacen = AlmacenEsquemasJsonSchema(tmp_path)
    almacen.guardar({"a": tipo_registrado("a", "a_*", {})})
    (tmp_path / "a.schema.json").unlink()

    with pytest.raises(ErrorGestor, match="no se puede leer el esquema .*a.schema.json"):
        almacen.cargar()


# --------------------------------------------------------------------------- validador

ESQUEMA = inferir_de_modelos([leer(m) for m in BASE])


def _documentos_legibles():
    """Documentos ``base_*.json`` que son JSON válido, ya leídos.

    ``base_json_invalido.json`` queda fuera: no se puede leer, así que nunca llega a un validador.
    Su incidencia ``json_invalido`` la comparan los tests de informes con los dos formatos.
    """
    documentos = []
    for ruta in sorted(DOCUMENTOS.glob("base_*.json")):
        try:
            documentos.append(pytest.param(
                json.loads(ruta.read_text(encoding="utf-8-sig")), id=ruta.name))
        except json.JSONDecodeError:
            pass
    return documentos


def test_todos_los_documentos_menos_el_invalido_se_comparan():
    assert len(_documentos_legibles()) == len(list(DOCUMENTOS.glob("base_*.json"))) - 1


@pytest.mark.parametrize("contenido", _documentos_legibles())
@pytest.mark.parametrize("estricto", [False, True], ids=["normal", "estricto"])
def test_mismas_incidencias_que_el_validador_propio(contenido, estricto):
    propio = ValidadorPropio(ESQUEMA, estricto).validar(contenido)

    assert ValidadorJsonSchema(documento_jsonschema("base", ESQUEMA), estricto).validar(
        contenido) == propio


def test_regla_incumplida():
    esquema = {"type": "object", "properties": {"n": {"type": "number", "minimum": 1}}}

    [incidencia] = ValidadorJsonSchema(esquema).validar({"n": 0})

    assert (incidencia.nivel, incidencia.categoria, incidencia.ruta) == (
        Nivel.ERROR, Categoria.REGLA_INCUMPLIDA, "$.n")
    assert (incidencia.esperado, incidencia.encontrado) == ("minimum: 1", "0")
    assert incidencia.mensaje == "Regla 'minimum' incumplida: debe ser mayor o igual que 1"


@pytest.mark.parametrize("formato, valido, invalido", [
    ("email", "ana@correo.example", "sin-arroba"),
    ("date-time", "2026-09-29T10:00:00Z", "2026-13-45T99:00:00Z"),
])
def test_los_formatos_se_comprueban(formato, valido, invalido):
    """Sin el FormatChecker de jsonschema, ``format`` sería solo una anotación."""
    validador = ValidadorJsonSchema({"type": "string", "format": formato})

    assert validador.validar(valido) == []
    [incidencia] = validador.validar(invalido)
    assert incidencia.categoria == Categoria.REGLA_INCUMPLIDA
    assert incidencia.mensaje == f"Regla 'format' incumplida: debe tener el formato {formato}"


def test_regla_sin_mensaje_propio_usa_el_de_jsonschema():
    [incidencia] = ValidadorJsonSchema({"not": {"type": "string"}}).validar("x")

    assert incidencia.categoria == Categoria.REGLA_INCUMPLIDA
    assert incidencia.encontrado == '"x"'
    assert "should not be valid" in incidencia.mensaje


def test_regla_sobre_un_objeto_muestra_su_tipo():
    [incidencia] = ValidadorJsonSchema({"type": "array", "minItems": 2}).validar([1])

    assert (incidencia.esperado, incidencia.encontrado) == ("minItems: 2", "lista")


def test_esquema_invalido():
    with pytest.raises(ErrorGestor, match="no es un JSON Schema válido"):
        ValidadorJsonSchema({"title": "t", "type": 3})


def test_la_fabrica_usa_el_esquema_guardado_con_sus_reglas():
    tipo = tipo_registrado("t", "t_*", {"n": 1})
    tipo.esquema_json = documento_jsonschema("t", tipo.esquema)
    tipo.esquema_json["properties"]["n"]["minimum"] = 5

    assert [i.categoria for i in crear_validador_jsonschema(tipo, False).validar({"n": 1})] == [
        Categoria.REGLA_INCUMPLIDA]
    tipo.esquema_json = None
    assert crear_validador_jsonschema(tipo, False).validar({"n": 1}) == []


# --------------------------------------------------------------------------- equivalencia de informes

def informes(carpeta):
    return {nombre: (Path(carpeta) / nombre).read_bytes()
            for nombre in ("incidencias.csv", "resumen_archivos.csv", "resumen_lote.json")}


@pytest.mark.parametrize("opciones", [[], ["--estricto"], ["--max-incidencias", "5"]],
                         ids=["normal", "estricto", "max_5"])
def test_informes_identicos_con_los_dos_formatos(ejecutar, opciones):
    for formato in ("propio", "jsonschema"):
        ejecutar("registrar", "--formato", formato, "--tipo", "base", "--patron", "base_*.json",
                 "--modelo", BASE[0], "--modelo", BASE[1])
        ejecutar("registrar", "--formato", formato, "--tipo", "todo", "--patron", "*_1*.json",
                 "--modelo", MODELOS / "vacio.json")
        ejecutar("validar", DOCUMENTOS, "--salida", f"salida_{formato}", "--formato", formato,
                 *opciones)

    assert informes("salida_jsonschema") == informes("salida_propio")


def test_informes_de_clasificacion_identicos(ejecutar):
    for formato in ("propio", "jsonschema"):
        for tipo, patron in [("pedido", "pedido_*.json"), ("borrador", "*_borrador.json"),
                             ("corto", "pedido_?.json")]:
            ejecutar("registrar", "--formato", formato, "--tipo", tipo, "--patron", patron,
                     "--modelo", MODELOS / "vacio.json")
        ejecutar("validar", DATOS / "clasificacion", "--salida", f"s_{formato}", "--formato", formato)

    assert informes("s_jsonschema") == informes("s_propio")


def test_lote_de_ejemplo_con_json_schema_identico_a_la_referencia_legacy(ejecutar):
    for tipo, patron, prefijo in [("pedido", "pedido_*.json", "pedido"),
                                  ("lectura_sensor", "sensor_*.json", "sensor"),
                                  ("actividad", "ruta_*.json", "ruta")]:
        modelos = sorted(EJEMPLOS.glob(f"modelos/{prefijo}_modelo_*.json"))
        ejecutar("registrar", "--tipo", tipo, "--patron", patron,
                 *[arg for m in modelos for arg in ("--modelo", m)])

    codigo, _ = ejecutar("validar", EJEMPLOS / "entrada", "--salida", "salida")

    assert codigo == 1
    assert informes("salida") == informes(DATOS / "esperado" / "ejemplos")


# --------------------------------------------------------------------------- nuevas capacidades

def preparar(ejecutar, tipo, patron, prefijo, reglas):
    """Registra el tipo con JSON Schema y añade a mano ``reglas`` (ruta de claves → regla)."""
    modelos = sorted(EJEMPLOS.glob(f"modelos/{prefijo}_modelo_*.json"))
    ejecutar("registrar", "--tipo", tipo, "--patron", patron,
             *[arg for m in modelos for arg in ("--modelo", m)])
    ruta = Path("esquemas") / f"{tipo}.schema.json"
    esquema = leer(ruta)
    for camino, regla in reglas:
        nodo = esquema
        for clave in camino:
            nodo = nodo[clave]
        nodo.update(regla)
    escribir(ruta, esquema)


def campo(*nombres):
    """Camino de claves en el esquema hasta un campo anidado (``items`` para las listas)."""
    camino = []
    for nombre in nombres:
        camino += ["items"] if nombre == "[]" else ["properties", nombre]
    return camino


REGLAS_PEDIDO = [
    (campo("lineas", "[]", "cantidad"), {"minimum": 1}),
    (campo("lineas", "[]", "sku"), {"pattern": "^SKU-[0-9]{4}-[A-Z]{2}$"}),
    (campo("cliente", "email"), {"format": "email"}),
    (campo("fecha"), {"format": "date-time"}),
]
REGLAS_ACTIVIDAD = [
    (campo("deporte"), {"enum": ["carrera", "ciclismo", "senderismo"]}),
    (campo("segmentos", "[]", "puntos", "[]", "fc"), {"minimum": 30, "maximum": 220}),
]


def cambiar(documento, camino, valor):
    nodo = documento
    for clave in camino[:-1]:
        nodo = nodo[clave]
    nodo[camino[-1]] = valor


CASOS = {
    "pedido válido": ("pedido", None, None, []),
    "cantidad por debajo del mínimo": (
        "pedido", ["lineas", 0, "cantidad"], 0, [("$.lineas[0].cantidad", "minimum")]),
    "sku que no sigue el patrón": (
        "pedido", ["lineas", 0, "sku"], "ABC", [("$.lineas[0].sku", "pattern")]),
    "email inválido": ("pedido", ["cliente", "email"], "sin-arroba", [("$.cliente.email", "format")]),
    "fecha inválida": ("pedido", ["fecha"], "2026-13-45T99:00:00Z", [("$.fecha", "format")]),
    "actividad válida": ("actividad", None, None, []),
    "deporte no permitido": ("actividad", ["deporte"], "natacion", [("$.deporte", "enum")]),
    "fc por encima del máximo": (
        "actividad", ["segmentos", 0, "puntos", 0, "fc"], 250,
        [("$.segmentos[0].puntos[0].fc", "maximum")]),
    "fc por debajo del mínimo": (
        "actividad", ["segmentos", 0, "puntos", 0, "fc"], 10,
        [("$.segmentos[0].puntos[0].fc", "minimum")]),
}


@pytest.mark.parametrize("tipo, camino, valor, esperadas", CASOS.values(), ids=CASOS.keys())
def test_reglas_anadidas_a_mano_se_detectan(ejecutar, tipo, camino, valor, esperadas):
    if tipo == "pedido":
        preparar(ejecutar, "pedido", "pedido_*.json", "pedido", REGLAS_PEDIDO)
        documento = leer(EJEMPLOS / "modelos" / "pedido_modelo_1.json")
        documento["fecha"] = "2026-09-29T10:00:00Z"  # date-time exige zona horaria (RFC 3339)
    else:
        preparar(ejecutar, "actividad", "ruta_*.json", "ruta", REGLAS_ACTIVIDAD)
        documento = leer(EJEMPLOS / "modelos" / "ruta_modelo_1.json")
        documento["segmentos"][0]["puntos"][0]["fc"] = 120
    if camino:
        cambiar(documento, camino, valor)
    nombre = "pedido_x.json" if tipo == "pedido" else "ruta_x.json"
    escribir(nombre, documento)

    codigo, _ = ejecutar("validar", nombre, "--salida", "salida")

    with open("salida/incidencias.csv", encoding="utf-8", newline="") as archivo:
        filas = list(csv.DictReader(archivo))
    assert [(f["ruta"], f["esperado"].split(":")[0]) for f in filas] == esperadas
    assert all(f["categoria"] == "regla_incumplida" and f["nivel"] == "error" for f in filas)
    assert codigo == (1 if esperadas else 0)


def test_con_el_formato_propio_las_reglas_no_existen(ejecutar):
    """El mismo documento, validado con el formato propio, no puede detectar la regla."""
    ejecutar("registrar", "--formato", "propio", "--tipo", "pedido", "--patron", "pedido_*.json",
             "--modelo", EJEMPLOS / "modelos" / "pedido_modelo_1.json")
    documento = leer(EJEMPLOS / "modelos" / "pedido_modelo_1.json")
    documento["lineas"][0]["cantidad"] = -5
    escribir("pedido_x.json", documento)

    assert ejecutar("validar", "pedido_x.json", "--salida", "s", "--formato", "propio")[0] == 0


# --------------------------------------------------------------------------- CLI

def test_por_defecto_se_usa_json_schema(ejecutar):
    ejecutar("registrar", "--tipo", "t", "--patron", "t_*.json", "--modelo", MODELOS / "vacio.json")

    assert sorted(p.name for p in Path("esquemas").iterdir()) == ["registro.json", "t.schema.json"]
    assert not Path("esquemas.json").exists()
    assert ejecutar("tipos")[1].splitlines()[1].startswith("t ")
    assert ejecutar("tipos", "--formato", "propio") == (0, "No hay tipos registrados\n")


def test_formato_desconocido(ejecutar):
    assert ejecutar("tipos", "--formato", "xml") == (
        2, "Error: formato desconocido: xml (usa jsonschema o propio)\n")


# --------------------------------------------------------------------------- reglas a mano y actualizar

def incidencias_de(ruta_csv):
    with open(ruta_csv, encoding="utf-8", newline="") as archivo:
        return [(f["categoria"], f["ruta"], f["esperado"]) for f in csv.DictReader(archivo)]


def registrar_pedido(ejecutar, *numeros):
    ejecutar("registrar", "--tipo", "pedido", "--patron", "pedido_*.json",
             *[arg for n in numeros
               for arg in ("--modelo", EJEMPLOS / "modelos" / f"pedido_modelo_{n}.json")])


def test_minimum_a_mano_se_respeta_al_validar_y_sobrevive_a_actualizar(ejecutar):
    registrar_pedido(ejecutar, 1, 2)
    esquema_path = Path("esquemas/pedido.schema.json")
    esquema = leer(esquema_path)
    esquema["properties"]["lineas"]["items"]["properties"]["cantidad"]["minimum"] = 1
    escribir(esquema_path, esquema)
    documento = leer(EJEMPLOS / "modelos" / "pedido_modelo_1.json")
    documento["lineas"][0]["cantidad"] = 0
    escribir("pedido_x.json", documento)
    esperada = [("regla_incumplida", "$.lineas[0].cantidad", "minimum: 1")]

    ejecutar("validar", "pedido_x.json", "--salida", "antes")
    codigo, salida = ejecutar("actualizar", "--tipo", "pedido", "--modelo",
                              EJEMPLOS / "modelos" / "pedido_modelo_3.json")
    ejecutar("validar", "pedido_x.json", "--salida", "despues")

    assert incidencias_de("antes/incidencias.csv") == esperada
    assert (codigo, salida) == (0, "Tipo 'pedido' actualizado: 3 modelo(s) en total\n")
    cantidad = leer(esquema_path)["properties"]["lineas"]["items"]["properties"]["cantidad"]
    assert cantidad == {"type": "number", "minimum": 1}
    assert incidencias_de("despues/incidencias.csv") == esperada


def test_ref_a_un_subesquema_comun_se_respeta_y_sobrevive_a_actualizar(ejecutar):
    modelos = sorted(EJEMPLOS.glob("modelos/ruta_modelo_*.json"))
    ejecutar("registrar", "--tipo", "actividad", "--patron", "ruta_*.json",
             "--modelo", modelos[0], "--modelo", modelos[1])
    esquema_path = Path("esquemas/actividad.schema.json")
    esquema = leer(esquema_path)
    esquema["$defs"] = {"latitud": {"minimum": -90, "maximum": 90}}
    punto = esquema["properties"]["segmentos"]["items"]["properties"]["puntos"]["items"]
    punto["properties"]["lat"]["$ref"] = "#/$defs/latitud"
    escribir(esquema_path, esquema)
    documento = leer(modelos[0])
    documento["segmentos"][0]["puntos"][0]["lat"] = 100
    escribir("ruta_x.json", documento)

    ejecutar("actualizar", "--tipo", "actividad", "--modelo", modelos[2])
    ejecutar("validar", "ruta_x.json", "--salida", "salida")

    assert leer(esquema_path)["$defs"] == {"latitud": {"minimum": -90, "maximum": 90}}
    assert incidencias_de("salida/incidencias.csv") == [
        ("regla_incumplida", "$.segmentos[0].puntos[0].lat", "maximum: 90")]


def test_integer_a_mano_se_valida_pero_se_regenera_al_actualizar(ejecutar):
    """Limitación documentada: ``type`` es estructura deducida y se regenera al actualizar."""
    registrar_pedido(ejecutar, 1)
    esquema_path = Path("esquemas/pedido.schema.json")
    esquema = leer(esquema_path)
    esquema["properties"]["lineas"]["items"]["properties"]["cantidad"]["type"] = "integer"
    escribir(esquema_path, esquema)
    documento = leer(EJEMPLOS / "modelos" / "pedido_modelo_1.json")
    documento["lineas"][0]["cantidad"] = 2.5
    escribir("pedido_x.json", documento)

    ejecutar("validar", "pedido_x.json", "--salida", "antes")
    ejecutar("actualizar", "--tipo", "pedido", "--modelo",
             EJEMPLOS / "modelos" / "pedido_modelo_2.json")

    assert incidencias_de("antes/incidencias.csv") == [
        ("tipo_incorrecto", "$.lineas[0].cantidad", "entero")]
    cantidad = leer(esquema_path)["properties"]["lineas"]["items"]["properties"]["cantidad"]
    assert cantidad == {"type": "number"}
