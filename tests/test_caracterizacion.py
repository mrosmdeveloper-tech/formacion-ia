"""Tests de caracterización del gestor de tipos JSON.

Se escribieron sobre la versión legacy (``gestor.py``, un único archivo) antes de refactorizarla, y
fijan su comportamiento ejecutando los comandos de principio a fin: el contenido exacto de
``esquemas.json`` y de los informes, la salida por consola y el código de salida. La versión
modular (``gestor_json``) los pasa sin cambiar ningún valor esperado; el único cambio es el nombre
del programa en el mensaje de uso (``main.py`` en lugar de ``gestor.py``).

Cada test se ejecuta en una carpeta temporal (nunca toca el ``esquemas.json`` real), con la fecha
de registro y el cronómetro fijados para que los resultados sean deterministas.
"""

import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

import gestor_json.cli
import gestor_json.registro

DATOS = Path(__file__).parent / "datos"
MODELOS = DATOS / "modelos"
FUSION = MODELOS / "fusion"
DOCUMENTOS = DATOS / "documentos"
CLASIFICACION = DATOS / "clasificacion"

FECHA = datetime(2026, 9, 29, 10, 0, 0)
FECHA_ISO = "2026-09-29T10:00:00"


class FechaFija:
    """Sustituye a ``datetime`` en el registro de tipos para que ``registrado`` sea siempre el mismo."""

    ahora = FECHA

    @classmethod
    def now(cls):
        return cls.ahora


@pytest.fixture
def cli(tmp_path, monkeypatch, capsys):
    """Ejecuta ``gestor_json.cli.main`` con los argumentos dados y devuelve (código, salida)."""
    monkeypatch.chdir(tmp_path)
    FechaFija.ahora = FECHA
    monkeypatch.setattr(gestor_json.registro, "datetime", FechaFija)
    monkeypatch.setattr(gestor_json.cli, "time", SimpleNamespace(perf_counter=lambda: 0.0))

    def ejecutar(*args):
        argv = [str(a) for a in args]
        monkeypatch.setattr(sys, "argv", ["main.py", *argv])
        codigo = gestor_json.cli.main(argv)
        return codigo, capsys.readouterr().out

    return ejecutar


def leer_esquemas():
    return json.loads(Path("esquemas.json").read_text(encoding="utf-8"))


def leer_csv(ruta):
    with open(ruta, encoding="utf-8", newline="") as archivo:
        return list(csv.reader(archivo))


def registrar(cli, tipo, patron, *modelos):
    args = ["registrar", "--tipo", tipo, "--patron", patron]
    for modelo in modelos:
        args += ["--modelo", modelo]
    codigo, salida = cli(*args)
    assert codigo == 0, salida


# --------------------------------------------------------------------------- esquemas esperados

TXT = {"t": "str", "nulo": False}
NUM = {"t": "num", "nulo": False}
BOOL = {"t": "bool", "nulo": False}
DESCONOCIDO = {"t": "unk", "nulo": False}


def req(esquema):
    return {"req": True, "esq": esquema}


def opc(esquema):
    return {"req": False, "esq": esquema}


def objeto(campos, nulo=False):
    return {"t": "obj", "nulo": nulo, "campos": campos}


def lista(item):
    return {"t": "list", "nulo": False, "item": item}


ESQUEMA_COMPLETO = objeto({
    "texto": req(TXT),
    "vacio": req(TXT),
    "entero": req(NUM),
    "decimal": req(NUM),
    "booleano": req(BOOL),
    "nulo": req({"t": "unk", "nulo": True}),
    "lista_vacia": req(lista(DESCONOCIDO)),
    "numeros": req(lista(NUM)),
    "objetos": req(lista(objeto({"a": req(NUM), "b": opc(TXT)}))),
    "anidado": req(objeto({"zona 1": req(objeto({"%grasa": req(NUM)}))})),
    "mixta": req(lista({"t": ["num", "str"], "nulo": False})),
})

ESQUEMA_BASE = objeto({
    "id": req(TXT),
    "codigo": req({"t": ["num", "str"], "nulo": False}),
    "cantidad": req(NUM),
    "activo": req(BOOL),
    "notas": req({"t": "str", "nulo": True}),
    "cliente": req(objeto({"nombre": req(TXT), "email": req(TXT), "telefono": opc(TXT)})),
    "lineas": req(lista(objeto({"sku": req(TXT), "precio": req(NUM)}))),
    "adjuntos": req(lista(DESCONOCIDO)),
    "pulso": req(objeto({"zona 1": req(NUM)})),
})


# --------------------------------------------------------------------------- inferencia

def test_registrar_infiere_todos_los_tipos_logicos(cli):
    codigo, salida = cli("registrar", "--tipo", "completo", "--patron", "c_*.json",
                         "--modelo", MODELOS / "completo.json")

    assert codigo == 0
    assert salida == "Tipo 'completo' registrado con 1 modelo(s) (patrón: c_*.json)\n"
    esperado = {"tipos": {"completo": {
        "patron": "c_*.json",
        "modelos_usados": 1,
        "registrado": FECHA_ISO,
        "esquema": ESQUEMA_COMPLETO,
    }}}
    # Contenido exacto del archivo: mismo orden de claves, sangría de 2 y UTF-8 sin escapar.
    assert Path("esquemas.json").read_text(encoding="utf-8") == json.dumps(
        esperado, indent=2, ensure_ascii=False)


def test_registrar_con_dos_modelos_fusiona_el_esquema(cli):
    registrar(cli, "base", "base_*.json", MODELOS / "base_1.json", MODELOS / "base_2.json")

    tipo = leer_esquemas()["tipos"]["base"]
    assert tipo["modelos_usados"] == 2
    assert tipo["esquema"] == ESQUEMA_BASE


# --------------------------------------------------------------------------- fusión

REGLAS_DE_FUSION = {
    "campo en un solo modelo pasa a opcional": (
        "opcional", objeto({"a": req(NUM), "b": opc(NUM), "c": opc(TXT)})),
    "desconocido + X da X": (
        "desconocido", objeto({"v": req(lista(TXT))})),
    "nulo + X da X admitiendo nulo": (
        "nulo", objeto({"v": req({"t": "str", "nulo": True})})),
    "tipos incompatibles dan una unión": (
        "union", objeto({"v": req({"t": ["num", "str"], "nulo": False})})),
    "unión con objeto conserva sus campos": (
        "union_objeto", objeto({"v": req({"t": ["obj", "str"], "nulo": False,
                                          "campos": {"x": req(NUM)}})})),
}


@pytest.mark.parametrize("par, esperado", REGLAS_DE_FUSION.values(), ids=REGLAS_DE_FUSION.keys())
@pytest.mark.parametrize("orden", [(1, 2), (2, 1)], ids=["orden_1_2", "orden_2_1"])
def test_reglas_de_fusion(cli, par, esperado, orden):
    modelos = [FUSION / f"{par}_{n}.json" for n in orden]
    registrar(cli, "t", "t_*.json", *modelos)

    assert leer_esquemas()["tipos"]["t"]["esquema"] == esperado


# --------------------------------------------------------------------------- actualizar y eliminar

def test_actualizar_fusiona_y_conserva_la_fecha_de_registro(cli):
    registrar(cli, "t", "t_*.json", FUSION / "opcional_1.json")
    FechaFija.ahora = datetime(2030, 1, 1)

    codigo, salida = cli("actualizar", "--tipo", "t", "--modelo", FUSION / "opcional_2.json",
                         "--modelo", MODELOS / "vacio.json")

    assert codigo == 0
    assert salida == "Tipo 't' actualizado: 3 modelo(s) en total\n"
    assert leer_esquemas() == {"tipos": {"t": {
        "patron": "t_*.json",
        "modelos_usados": 3,
        "registrado": FECHA_ISO,
        "esquema": objeto({"a": opc(NUM), "b": opc(NUM), "c": opc(TXT)}),
    }}}


def test_eliminar_borra_solo_ese_tipo(cli):
    registrar(cli, "uno", "uno_*.json", MODELOS / "vacio.json")
    registrar(cli, "dos", "dos_*.json", MODELOS / "vacio.json")

    codigo, salida = cli("eliminar", "--tipo", "uno")

    assert codigo == 0
    assert salida == "Tipo 'uno' eliminado\n"
    assert leer_esquemas() == {"tipos": {"dos": {
        "patron": "dos_*.json", "modelos_usados": 1, "registrado": FECHA_ISO,
        "esquema": objeto({}),
    }}}


def test_eliminar_el_ultimo_tipo_deja_el_registro_vacio(cli):
    registrar(cli, "uno", "uno_*.json", MODELOS / "vacio.json")
    cli("eliminar", "--tipo", "uno")

    assert Path("esquemas.json").read_text(encoding="utf-8") == '{\n  "tipos": {}\n}'


# --------------------------------------------------------------------------- tipos y mostrar

def test_tipos_sin_registro(cli):
    assert cli("tipos") == (0, "No hay tipos registrados\n")


def test_tipos_lista_los_tipos_en_orden_de_registro(cli):
    registrar(cli, "pedido", "pedido_*.json", MODELOS / "base_1.json", MODELOS / "base_2.json")
    registrar(cli, "sensor", "sensor_*.json", MODELOS / "vacio.json")

    codigo, salida = cli("tipos")

    assert codigo == 0
    assert salida == (
        f"{'TIPO':<20}{'PATRÓN':<22}{'MODELOS':>7}  REGISTRADO\n"
        f"{'pedido':<20}{'pedido_*.json':<22}{2:>7}  {FECHA_ISO}\n"
        f"{'sensor':<20}{'sensor_*.json':<22}{1:>7}  {FECHA_ISO}\n"
    )


def test_mostrar_imprime_el_esquema_como_arbol(cli):
    registrar(cli, "completo", "c_*.json", MODELOS / "completo.json")

    codigo, salida = cli("mostrar", "--tipo", "completo")

    assert codigo == 0
    assert salida == (
        "Tipo: completo\n"
        "Patrón: c_*.json\n"
        "Modelos usados: 1\n"
        f"Registrado: {FECHA_ISO}\n"
        "Esquema:\n"
        "$: objeto\n"
        "  texto: texto\n"
        "  vacio: texto\n"
        "  entero: numero\n"
        "  decimal: numero\n"
        "  booleano: booleano\n"
        "  nulo: desconocido | nulo\n"
        "  lista_vacia: lista\n"
        "    []: desconocido\n"
        "  numeros: lista\n"
        "    []: numero\n"
        "  objetos: lista\n"
        "    []: objeto\n"
        "      a: numero\n"
        "      b (opcional): texto\n"
        "  anidado: objeto\n"
        "    zona 1: objeto\n"
        "      %grasa: numero\n"
        "  mixta: lista\n"
        "    []: numero | texto\n"
    )


def test_mostrar_union_con_objeto_y_opcionales(cli):
    registrar(cli, "t", "t_*.json", FUSION / "union_objeto_1.json", FUSION / "union_objeto_2.json")
    registrar(cli, "base", "base_*.json", MODELOS / "base_1.json", MODELOS / "base_2.json")

    assert cli("mostrar", "--tipo", "t")[1].endswith(
        "$: objeto\n  v: objeto | texto\n    x: numero\n")
    assert cli("mostrar", "--tipo", "base")[1].endswith(
        "$: objeto\n"
        "  id: texto\n"
        "  codigo: numero | texto\n"
        "  cantidad: numero\n"
        "  activo: booleano\n"
        "  notas: texto | nulo\n"
        "  cliente: objeto\n"
        "    nombre: texto\n"
        "    email: texto\n"
        "    telefono (opcional): texto\n"
        "  lineas: lista\n"
        "    []: objeto\n"
        "      sku: texto\n"
        "      precio: numero\n"
        "  adjuntos: lista\n"
        "    []: desconocido\n"
        "  pulso: objeto\n"
        "    zona 1: numero\n"
    )


# --------------------------------------------------------------------------- errores de los comandos

VACIO = MODELOS / "vacio.json"
INVALIDO = DOCUMENTOS / "base_json_invalido.json"
MENSAJE_JSON_INVALIDO = "Expecting property name enclosed in double quotes: line 2 column 1 (char 29)"

ERRORES_DE_COMANDOS = {
    "sin comando": (
        [], "Uso: python main.py <comando> [opciones]\n"
            "Comandos: registrar, actualizar, tipos, mostrar, eliminar, validar\n"),
    "comando desconocido": (["borrar"], "Error: comando desconocido: borrar\n"),
    "registrar tipo existente": (
        ["registrar", "--tipo", "base", "--patron", "x_*.json", "--modelo", VACIO],
        "Error: el tipo 'base' ya existe\n"),
    "registrar patrón vacío": (
        ["registrar", "--tipo", "nuevo", "--patron", "  ", "--modelo", VACIO],
        "Error: el patrón no puede estar vacío\n"),
    "registrar sin patrón": (
        ["registrar", "--tipo", "nuevo", "--modelo", VACIO],
        "Error: el patrón no puede estar vacío\n"),
    "registrar sin modelos": (
        ["registrar", "--tipo", "nuevo", "--patron", "n_*.json"],
        "Error: hay que indicar al menos un --modelo\n"),
    "registrar sin tipo": (
        ["registrar", "--patron", "n_*.json", "--modelo", VACIO], "Error: falta --tipo\n"),
    "registrar argumento desconocido": (
        ["registrar", "--tipo", "nuevo", "--otro"], "Error: argumento no reconocido: --otro\n"),
    "registrar opción sin valor": (
        ["registrar", "--tipo"], "Error: argumento no reconocido: --tipo\n"),
    "registrar modelo inválido": (
        ["registrar", "--tipo", "nuevo", "--patron", "n_*.json", "--modelo", INVALIDO],
        f"Error: no se puede leer el modelo {INVALIDO}: {MENSAJE_JSON_INVALIDO}\n"),
    "actualizar tipo inexistente": (
        ["actualizar", "--tipo", "nada", "--modelo", VACIO], "Error: el tipo 'nada' no existe\n"),
    "actualizar sin tipo": (["actualizar", "--modelo", VACIO], "Error: falta --tipo\n"),
    "actualizar sin modelos": (
        ["actualizar", "--tipo", "base"], "Error: hay que indicar al menos un --modelo\n"),
    "actualizar argumento desconocido": (
        ["actualizar", "--patron", "x"], "Error: argumento no reconocido: --patron\n"),
    "actualizar modelo inválido": (
        ["actualizar", "--tipo", "base", "--modelo", INVALIDO],
        f"Error: no se puede leer el modelo {INVALIDO}: {MENSAJE_JSON_INVALIDO}\n"),
    "tipos con argumentos": (["tipos", "--todo"], "Error: argumento no reconocido: --todo\n"),
    "mostrar tipo inexistente": (["mostrar", "--tipo", "nada"], "Error: el tipo 'nada' no existe\n"),
    "mostrar sin tipo": (["mostrar"], "Error: falta --tipo\n"),
    "mostrar argumento desconocido": (["mostrar", "base"], "Error: argumento no reconocido: base\n"),
    "eliminar tipo inexistente": (["eliminar", "--tipo", "nada"], "Error: el tipo 'nada' no existe\n"),
    "eliminar sin tipo": (["eliminar"], "Error: falta --tipo\n"),
    "eliminar argumento desconocido": (["eliminar", "-t"], "Error: argumento no reconocido: -t\n"),
}


@pytest.mark.parametrize("args, mensaje", ERRORES_DE_COMANDOS.values(), ids=ERRORES_DE_COMANDOS.keys())
def test_errores_de_los_comandos_terminan_con_codigo_2(cli, args, mensaje):
    registrar(cli, "base", "base_*.json", MODELOS / "base_1.json", MODELOS / "base_2.json")
    antes = Path("esquemas.json").read_bytes()

    assert cli(*args) == (2, mensaje)
    assert Path("esquemas.json").read_bytes() == antes


def test_registrar_modelo_inexistente(cli):
    codigo, salida = cli("registrar", "--tipo", "t", "--patron", "t_*.json",
                         "--modelo", "no_existe.json")

    assert codigo == 2
    assert salida.startswith("Error: no se puede leer el modelo no_existe.json: [Errno 2]")
    assert not Path("esquemas.json").exists()


@pytest.mark.parametrize("args", [
    ["registrar", "--tipo", "t", "--patron", "t_*.json", "--modelo", VACIO],
    ["actualizar", "--tipo", "t", "--modelo", VACIO],
    ["tipos"],
    ["mostrar", "--tipo", "t"],
    ["eliminar", "--tipo", "t"],
    ["validar", DOCUMENTOS, "--salida", "salida"],
], ids=lambda args: args[0])
def test_esquemas_json_corrupto(cli, args):
    Path("esquemas.json").write_text("{roto", encoding="utf-8")

    codigo, salida = cli(*args)

    assert codigo == 2
    assert salida == ("Error: no se puede leer esquemas.json: Expecting property name enclosed "
                      "in double quotes: line 1 column 2 (char 1)\n")


# --------------------------------------------------------------------------- clasificación

CABECERA_INCIDENCIAS = ["archivo", "tipo", "nivel", "categoria", "ruta", "esperado", "encontrado",
                        "mensaje"]
CABECERA_RESUMEN = ["archivo", "tipo", "valido", "errores", "avisos"]
SIN_TIPO = "El nombre del archivo no encaja con ningún patrón registrado"


@pytest.fixture
def tipos_de_clasificacion(cli):
    """Tres tipos cuyos patrones se solapan: ``pedido_1.json`` empata y el borrador es más específico."""
    registrar(cli, "pedido", "pedido_*.json", VACIO)
    registrar(cli, "borrador", "*_borrador.json", VACIO)
    registrar(cli, "corto", "pedido_?.json", VACIO)


def test_clasificacion_por_patron(cli, tipos_de_clasificacion):
    codigo, _ = cli("validar", CLASIFICACION, "--salida", "salida")

    assert codigo == 0
    assert leer_csv("salida/incidencias.csv") == [
        CABECERA_INCIDENCIAS,
        ["informe_1.json", "", "aviso", "sin_tipo", "", "", "", SIN_TIPO],
        ["pedido_1.json", "pedido", "aviso", "varios_tipos", "", "pedido", "pedido, corto",
         "El nombre encaja con varios patrones (pedido, corto); se usa 'pedido'"],
        ["pedido_7_borrador.json", "borrador", "aviso", "varios_tipos", "", "borrador",
         "pedido, borrador",
         "El nombre encaja con varios patrones (pedido, borrador); se usa 'borrador'"],
    ]
    assert leer_csv("salida/resumen_archivos.csv") == [
        CABECERA_RESUMEN,
        ["informe_1.json", "", "no", "0", "1"],
        ["pedido_1.json", "pedido", "si", "0", "1"],
        ["pedido_12.json", "pedido", "si", "0", "0"],
        ["pedido_7_borrador.json", "borrador", "si", "0", "1"],
    ]


def test_formato_exacto_de_los_csv(cli, tipos_de_clasificacion):
    cli("validar", CLASIFICACION / "pedido_7_borrador.json", "--salida", "salida")

    assert Path("salida/incidencias.csv").read_bytes() == (
        "archivo,tipo,nivel,categoria,ruta,esperado,encontrado,mensaje\r\n"
        'pedido_7_borrador.json,borrador,aviso,varios_tipos,,borrador,"pedido, borrador",'
        "\"El nombre encaja con varios patrones (pedido, borrador); se usa 'borrador'\"\r\n"
    ).encode("utf-8")
    assert Path("salida/resumen_archivos.csv").read_bytes() == (
        b"archivo,tipo,valido,errores,avisos\r\n"
        b"pedido_7_borrador.json,borrador,si,0,1\r\n"
    )


def test_en_caso_de_empate_gana_el_tipo_registrado_primero(cli):
    registrar(cli, "corto", "pedido_?.json", VACIO)
    registrar(cli, "pedido", "pedido_*.json", VACIO)

    cli("validar", CLASIFICACION / "pedido_1.json", "--salida", "salida")

    assert leer_csv("salida/resumen_archivos.csv")[1] == ["pedido_1.json", "corto", "si", "0", "1"]
    assert leer_csv("salida/incidencias.csv")[1][5:7] == ["corto", "corto, pedido"]


def test_la_clasificacion_distingue_mayusculas(cli):
    registrar(cli, "pedido", "PEDIDO_*.json", VACIO)

    cli("validar", CLASIFICACION / "pedido_12.json", "--salida", "salida")

    assert leer_csv("salida/resumen_archivos.csv")[1] == ["pedido_12.json", "", "no", "0", "1"]


def test_sin_esquemas_todos_los_archivos_quedan_sin_tipo(cli):
    codigo, _ = cli("validar", CLASIFICACION, "--salida", "salida")

    assert codigo == 0
    assert [fila[3] for fila in leer_csv("salida/incidencias.csv")[1:]] == ["sin_tipo"] * 4
    resumen = json.loads(Path("salida/resumen_lote.json").read_text(encoding="utf-8"))
    assert resumen["sin_tipo"] == 4
    assert resumen["por_tipo"] == {}


# --------------------------------------------------------------------------- validación

@pytest.fixture
def tipo_base(cli):
    registrar(cli, "base", "base_*.json", MODELOS / "base_1.json", MODELOS / "base_2.json")


def validar_documento(cli, nombre, *opciones):
    """Valida un documento de ``tests/datos/documentos`` y devuelve (código, incidencias, resumen).

    Las incidencias se devuelven sin las columnas ``archivo`` y ``tipo``.
    """
    codigo, _ = cli("validar", DOCUMENTOS / nombre, "--salida", "salida", *opciones)
    incidencias = [tuple(fila[2:]) for fila in leer_csv("salida/incidencias.csv")[1:]]
    resumen = leer_csv("salida/resumen_archivos.csv")[1]
    return codigo, incidencias, resumen


def tipo_incorrecto(ruta, esperado, encontrado):
    return ("error", "tipo_incorrecto", ruta, esperado, encontrado,
            f"Tipo incorrecto: se esperaba {esperado} y se encontró {encontrado}")


def nulo_no_permitido(ruta, esperado):
    return ("error", "nulo_no_permitido", ruta, esperado, "nulo",
            f"Valor nulo no permitido: se esperaba {esperado}")


def falta_campo(ruta, campo, esperado):
    return ("error", "falta_campo", ruta, esperado, "ausente",
            f"Falta el campo obligatorio '{campo}'")


def campo_extra(ruta, campo, encontrado, nivel="aviso"):
    return (nivel, "campo_extra", ruta, "ausente", encontrado,
            f"Campo no previsto en el esquema: '{campo}'")


# Incidencias esperadas por documento, ordenadas por ruta (con los índices en orden numérico).
INCIDENCIAS_POR_DOCUMENTO = {
    "base_valido.json": [],
    "base_bom.json": [],
    "base_falta_campo.json": [
        falta_campo("$.cliente.email", "email", "texto"),
        falta_campo("$.lineas[1].precio", "precio", "numero"),
    ],
    "base_campo_extra.json": [
        campo_extra("$.cliente.vip", "vip", "booleano"),
        campo_extra("$.origen", "origen", "texto"),
    ],
    "base_tipo_incorrecto.json": [
        tipo_incorrecto("$.cantidad", "numero", "texto"),
        tipo_incorrecto("$.cliente", "objeto", "texto"),
        tipo_incorrecto("$.codigo", "numero | texto", "booleano"),
        tipo_incorrecto("$.lineas[0]", "objeto", "numero"),
        tipo_incorrecto("$.notas", "texto | nulo", "numero"),
    ],
    "base_bool_numero.json": [
        tipo_incorrecto("$.activo", "booleano", "numero"),
        tipo_incorrecto("$.cantidad", "numero", "booleano"),
    ],
    "base_nulo_no_permitido.json": [
        nulo_no_permitido("$.cliente", "objeto"),
        nulo_no_permitido("$.id", "texto"),
        nulo_no_permitido("$.lineas[0]", "objeto"),
    ],
    "base_clave_espacios.json": [
        tipo_incorrecto('$.pulso["zona 1"]', "numero", "texto"),
        campo_extra('$.pulso["zona 2"]', "zona 2", "numero"),
    ],
    "base_raiz_lista.json": [
        tipo_incorrecto("$", "objeto", "lista"),
    ],
    "base_json_invalido.json": [
        ("error", "json_invalido", "$", "", "",
         f"El archivo no es un JSON válido: {MENSAJE_JSON_INVALIDO}"),
    ],
}


@pytest.mark.parametrize("nombre, esperadas", INCIDENCIAS_POR_DOCUMENTO.items(),
                         ids=INCIDENCIAS_POR_DOCUMENTO.keys())
def test_incidencias_de_cada_documento(cli, tipo_base, nombre, esperadas):
    codigo, incidencias, resumen = validar_documento(cli, nombre)

    assert incidencias == esperadas
    errores = sum(1 for i in esperadas if i[0] == "error")
    avisos = len(esperadas) - errores
    valido = "si" if errores == 0 else "no"
    assert resumen == [nombre, "base", valido, str(errores), str(avisos)]
    assert codigo == (1 if errores else 0)


def test_documento_sin_tipo_no_se_valida(cli, tipo_base):
    codigo, incidencias, resumen = validar_documento(cli, "otro_nombre.json")

    assert codigo == 0
    assert incidencias == [("aviso", "sin_tipo", "", "", "", SIN_TIPO)]
    assert resumen == ["otro_nombre.json", "", "no", "0", "1"]


def test_modo_estricto_convierte_los_campos_extra_en_errores(cli, tipo_base):
    codigo, incidencias, resumen = validar_documento(cli, "base_campo_extra.json", "--estricto")

    assert codigo == 1
    assert incidencias == [
        campo_extra("$.cliente.vip", "vip", "booleano", nivel="error"),
        campo_extra("$.origen", "origen", "texto", nivel="error"),
    ]
    assert resumen == ["base_campo_extra.json", "base", "no", "2", "0"]


def test_por_defecto_se_truncan_a_200_incidencias(cli, tipo_base):
    codigo, incidencias, resumen = validar_documento(cli, "base_muchas_incidencias.json")

    assert codigo == 1
    assert len(incidencias) == 201
    assert incidencias[:200] == [
        falta_campo(f"$.lineas[{n}].sku", "sku", "texto") for n in range(200)]
    assert incidencias[200] == (
        "aviso", "incidencias_truncadas", "", "200", "250",
        "Se han encontrado 250 incidencias; solo se incluyen las primeras 200")
    assert resumen == ["base_muchas_incidencias.json", "base", "no", "200", "1"]


def test_max_incidencias_personalizado(cli, tipo_base):
    _, incidencias, resumen = validar_documento(cli, "base_tipo_incorrecto.json",
                                                "--max-incidencias", "3")

    assert incidencias == INCIDENCIAS_POR_DOCUMENTO["base_tipo_incorrecto.json"][:3] + [
        ("aviso", "incidencias_truncadas", "", "3", "5",
         "Se han encontrado 5 incidencias; solo se incluyen las primeras 3")]
    assert resumen == ["base_tipo_incorrecto.json", "base", "no", "3", "1"]


def test_sin_truncar_si_no_se_supera_el_maximo(cli, tipo_base):
    _, incidencias, _ = validar_documento(cli, "base_tipo_incorrecto.json",
                                          "--max-incidencias", "5")

    assert incidencias == INCIDENCIAS_POR_DOCUMENTO["base_tipo_incorrecto.json"]


# --------------------------------------------------------------------------- informes del lote

RESUMEN_LOTE_DOCUMENTOS = {
    "archivos_totales": 12,
    "por_tipo": {"base": 11},
    "validos": 3,
    "con_errores": 8,
    "sin_tipo": 1,
    "incidencias_por_categoria": {
        "campo_extra": 3,
        "falta_campo": 202,
        "incidencias_truncadas": 1,
        "json_invalido": 1,
        "nulo_no_permitido": 3,
        "sin_tipo": 1,
        "tipo_incorrecto": 9,
    },
    "rutas_mas_frecuentes": {"base": [
        {"ruta": "$.lineas[*].sku", "incidencias": 200},
        {"ruta": "$", "incidencias": 2},
        {"ruta": "$.cantidad", "incidencias": 2},
        {"ruta": "$.cliente", "incidencias": 2},
        {"ruta": "$.lineas[*]", "incidencias": 2},
        {"ruta": "$.activo", "incidencias": 1},
        {"ruta": "$.cliente.email", "incidencias": 1},
        {"ruta": "$.cliente.vip", "incidencias": 1},
        {"ruta": "$.codigo", "incidencias": 1},
        {"ruta": "$.id", "incidencias": 1},
    ]},
    "tiempo_s": 0.0,
}


def test_validar_carpeta_genera_los_tres_informes(cli, tipo_base):
    codigo, salida = cli("validar", DOCUMENTOS, "--salida", "salida")

    assert codigo == 1
    assert salida == (
        "Archivos procesados: 12\n"
        "  base: 11\n"
        "  sin tipo: 1\n"
        "Válidos: 3  Con errores: 8  Sin tipo: 1\n"
        "Incidencias: 220\n"
        "  campo_extra: 3\n"
        "  falta_campo: 202\n"
        "  incidencias_truncadas: 1\n"
        "  json_invalido: 1\n"
        "  nulo_no_permitido: 3\n"
        "  sin_tipo: 1\n"
        "  tipo_incorrecto: 9\n"
        "Informes en: salida\n"
        "Tiempo total: 0.0 s\n"
    )
    assert Path("salida/resumen_lote.json").read_text(encoding="utf-8") == json.dumps(
        RESUMEN_LOTE_DOCUMENTOS, indent=2, ensure_ascii=False)
    # Solo los .json de la carpeta (leeme.txt se ignora), en orden alfabético.
    assert [fila[0] for fila in leer_csv("salida/resumen_archivos.csv")[1:]] == sorted(
        p.name for p in DOCUMENTOS.glob("*.json"))
    assert len(leer_csv("salida/incidencias.csv")) == 1 + 220


def test_lote_sin_errores_termina_con_codigo_0(cli, tipo_base):
    codigo, salida = cli("validar", DOCUMENTOS / "base_valido.json", "--salida", "salida")

    assert codigo == 0
    assert "Válidos: 1  Con errores: 0  Sin tipo: 0\n" in salida
    assert leer_csv("salida/incidencias.csv") == [CABECERA_INCIDENCIAS]


def test_lote_de_ejemplo_identico_a_la_referencia(cli):
    """Caracterización global: registra los tres tipos de ``datos/ejemplos`` y valida su entrada.

    ``esquemas.json`` y los tres informes deben coincidir byte a byte con los de
    ``tests/datos/esperado/ejemplos``, generados con la versión legacy y revisados a mano.
    """
    ejemplos = Path(__file__).parent.parent / "datos" / "ejemplos"
    for tipo, patron, prefijo in [("pedido", "pedido_*.json", "pedido"),
                                  ("lectura_sensor", "sensor_*.json", "sensor"),
                                  ("actividad", "ruta_*.json", "ruta")]:
        modelos = [ejemplos / "modelos" / f"{prefijo}_modelo_{n}.json" for n in (1, 2, 3)]
        registrar(cli, tipo, patron, *modelos)

    codigo, _ = cli("validar", ejemplos / "entrada", "--salida", "salida")

    assert codigo == 1
    esperado = DATOS / "esperado" / "ejemplos"
    assert Path("esquemas.json").read_bytes() == (esperado / "esquemas.json").read_bytes()
    for informe in ("incidencias.csv", "resumen_archivos.csv", "resumen_lote.json"):
        assert (Path("salida") / informe).read_bytes() == (esperado / informe).read_bytes(), informe


# --------------------------------------------------------------------------- errores de validar

ERRORES_DE_VALIDAR = {
    "sin ruta": (["--salida", "s"], "Error: falta el archivo o la carpeta a validar\n"),
    "sin salida": ([DOCUMENTOS], "Error: falta --salida\n"),
    "ruta inexistente": (["no_existe", "--salida", "s"], "Error: no existe no_existe\n"),
    "máximo no numérico": (
        [DOCUMENTOS, "--salida", "s", "--max-incidencias", "diez"],
        "Error: --max-incidencias debe ser un número entero\n"),
    "máximo cero": (
        [DOCUMENTOS, "--salida", "s", "--max-incidencias", "0"],
        "Error: --max-incidencias debe ser al menos 1\n"),
    "máximo sin valor": (
        [DOCUMENTOS, "--salida", "s", "--max-incidencias"],
        "Error: argumento no reconocido: --max-incidencias\n"),
    "opción desconocida": ([DOCUMENTOS, "--rapido"], "Error: argumento no reconocido: --rapido\n"),
    "dos rutas": ([DOCUMENTOS, "otra"], "Error: argumento no reconocido: otra\n"),
}


@pytest.mark.parametrize("args, mensaje", ERRORES_DE_VALIDAR.values(), ids=ERRORES_DE_VALIDAR.keys())
def test_errores_de_validar_terminan_con_codigo_2(cli, args, mensaje):
    assert cli("validar", *args) == (2, mensaje)
    assert not Path("s").exists()


def test_salida_que_no_se_puede_crear(cli):
    Path("ocupado").write_text("soy un archivo", encoding="utf-8")

    codigo, salida = cli("validar", DOCUMENTOS, "--salida", "ocupado")

    assert codigo == 2
    assert salida.startswith("Error: no se pueden crear los informes en ocupado: ")


# --------------------------------------------------------------------------- diferencias con la versión legacy

# Casos extremos de argumentos que cambiaron al pasar a argparse (aceptados de forma explícita).
# La versión legacy rechazaba "--tipo=x" ("argumento no reconocido: --tipo=x") y, con
# "--tipo --patron x", tomaba "--patron" como nombre del tipo y fallaba con "x".

def test_diferencia_opcion_con_igual_se_acepta(cli):
    codigo, salida = cli("registrar", "--tipo=nuevo", "--patron=n_*.json", "--modelo", VACIO)

    assert codigo == 0
    assert salida == "Tipo 'nuevo' registrado con 1 modelo(s) (patrón: n_*.json)\n"
    assert list(leer_esquemas()["tipos"]) == ["nuevo"]


def test_diferencia_opcion_sin_valor_seguida_de_otra_opcion(cli):
    codigo, salida = cli("registrar", "--tipo", "--patron", "n_*.json", "--modelo", VACIO)

    assert (codigo, salida) == (2, "Error: argumento no reconocido: --tipo\n")
    assert not Path("esquemas.json").exists()
