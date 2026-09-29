"""Tests de caracterización de ``gestor.py`` (versión legacy).

Fijan el comportamiento actual del programa ejecutando sus comandos de principio a fin: el
contenido exacto de ``esquemas.json`` y de los informes, la salida por consola y el código de
salida. Sirven de red de seguridad para la refactorización: tras ella, todos deben seguir en verde.

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

import gestor

DATOS = Path(__file__).parent / "datos"
MODELOS = DATOS / "modelos"
FUSION = MODELOS / "fusion"
DOCUMENTOS = DATOS / "documentos"
CLASIFICACION = DATOS / "clasificacion"

FECHA = datetime(2026, 9, 29, 10, 0, 0)
FECHA_ISO = "2026-09-29T10:00:00"


class FechaFija:
    """Sustituye a ``datetime`` en ``gestor`` para que ``registrado`` sea siempre el mismo."""

    ahora = FECHA

    @classmethod
    def now(cls):
        return cls.ahora


@pytest.fixture
def cli(tmp_path, monkeypatch, capsys):
    """Ejecuta ``gestor.main()`` con los argumentos dados y devuelve (código, salida).

    Los comandos que terminan bien sin llamar a ``sys.exit`` devuelven código 0, que es el
    código con el que termina el proceso real.
    """
    monkeypatch.chdir(tmp_path)
    FechaFija.ahora = FECHA
    monkeypatch.setattr(gestor, "datetime", FechaFija)
    monkeypatch.setattr(gestor, "time", SimpleNamespace(perf_counter=lambda: 0.0))

    def ejecutar(*args):
        monkeypatch.setattr(sys, "argv", ["gestor.py", *[str(a) for a in args]])
        codigo = 0
        try:
            gestor.main()
        except SystemExit as salida:
            codigo = salida.code
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
        [], "Uso: python gestor.py <comando> [opciones]\n"
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
