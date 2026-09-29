# CLAUDE.md

## Proyecto

Gestor de tipos JSON: herramienta de línea de comandos que registra tipos a partir de JSON modelo,
deduce su esquema, clasifica archivos por su nombre (patrón `fnmatch`) y los valida contra el
esquema de su tipo, generando informes de incidencias. Los esquemas se guardan como JSON Schema
(draft 2020-12) y admiten reglas añadidas a mano; también se puede usar el formato propio original.
La especificación está en [docs/especificacion.md](docs/especificacion.md) y la decisión de usar
JSON Schema, en [docs/adr/0001-json-schema.md](docs/adr/0001-json-schema.md).

## Estructura

```
main.py                  # punto de entrada: python main.py <comando> [opciones]
gestor_json/
  config.py              # constantes: límites, categorías, niveles, nombres de archivo
  tipos_logicos.py       # enum TipoLogico y clasificar_valor (bool antes que número)
  modelos.py             # dataclasses: NodoEsquema, CampoEsquema, TipoRegistrado, Incidencia,
                         #   ResultadoArchivo, y la excepción ErrorGestor
  rutas.py               # rutas JSONPath, su orden y su normalización ([*])
  inferencia.py          # deducir el esquema de un documento (función pura)
  fusion.py              # fusionar dos esquemas (función pura)
  validacion.py          # interfaz Validador y ValidadorPropio (devuelve incidencias)
  registro.py            # RegistroTipos y clasificación de archivos por patrón
  almacenamiento.py      # interfaz AlmacenEsquemas y AlmacenEsquemasPropio (esquemas.json)
  jsonschema_formato.py  # JSON Schema: conversión (ida y vuelta), AlmacenEsquemasJsonSchema,
                         #   ValidadorJsonSchema (traduce errores a incidencias) y exportar a VS Code
  migracion.py           # migrar esquemas.json a esquemas/ y verificar que las incidencias coinciden
  lote.py                # ValidadorLote (un archivo o una carpeta) y ResumenLote
  informes.py            # CSV, resumen_lote.json y resumen por consola
  cli.py                 # argparse con subcomandos, orquestación y códigos de salida
scripts/
  generar_datos.py       # generador de datos sintéticos (reproducible con --semilla)
  benchmark.py           # benchmark de registro y validación por formato (docs/benchmark.md)
tests/
  conftest.py              # fixture ejecutar: la CLI en una carpeta temporal, fecha y reloj fijos
  test_caracterizacion.py  # de principio a fin con el formato propio (esquemas.json, informes,
                           #   consola, códigos)
  test_jsonschema_formato.py  # conversión, almacén, validador, equivalencia y reglas a mano
  test_migracion.py        # migración, verificación y exportación a VS Code
  test_<módulo>.py         # tests unitarios del resto de módulos
  datos/                   # JSON mínimos diseñados a mano y referencias (esperado/)
datos/ejemplos/          # datos pequeños versionados
datos/generados/         # lotes grandes generados (no versionado)
docs/                    # especificación, ADR, plan de refactorización, benchmark, capacidades,
                         #   registro de IA
esquemas/                # tipos registrados en JSON Schema (formato por defecto; no versionado)
esquemas.json            # tipos registrados en el formato propio (no versionado)
.github/workflows/calidad.yml  # tests con cobertura en Linux y análisis en SonarQube Cloud
sonar-project.properties       # configuración del análisis
```

Diseño: el registro, el lote y los informes solo dependen de las interfaces `Validador` y
`AlmacenEsquemas`. Hay dos formatos de esquema, que se eligen con `--formato` (`cli.FORMATOS`):
`jsonschema` (por defecto; `jsonschema_formato.py`) y `propio` (`almacenamiento.py` y
`validacion.py`). Los códigos `"str"`, `"num"`… solo existen en `almacenamiento.py`.

JSON Schema: la inferencia y la fusión trabajan con `NodoEsquema`; se convierte al guardar.
`TipoRegistrado.esquema_json` guarda el documento tal como está en disco, con las reglas añadidas
a mano, que se conservan al regenerar y son las que usa el validador. Lo que se regenera es la
estructura (`type`, `properties`, `required`, `additionalProperties`, `items`). Un desconocido que
procede de un `null` se marca con `"examples": [null]`. El nombre de un tipo es el nombre de su
archivo, así que no puede contener separadores de carpeta ni `..`.

## Comandos

Entorno:
```bash
# Git Bash
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements-dev.txt
```
```powershell
# PowerShell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

Ejecutar (igual en Git Bash y en PowerShell):
```
python main.py registrar --tipo pedido --patron "pedido_*.json" --modelo <archivo> [--modelo <archivo> ...]
python main.py validar <archivo_o_carpeta> --salida salida/ [--estricto] [--formato jsonschema|propio]
python main.py migrar-esquemas --desde esquemas.json --hacia esquemas --verificar datos/ejemplos/entrada
python main.py exportar-vscode
python scripts/generar_datos.py --archivos 1000 --salida datos/generados/lote_1000 --semilla 42
python scripts/benchmark.py datos/generados/lote_1000 --formatos propio jsonschema
```

Tests, cobertura y comprobaciones (igual en los dos):
```
python -m pytest
python -m pytest --cov=gestor_json --cov-report=term-missing --cov-report=html --cov-report=xml
python -m mypy --disallow-untyped-defs gestor_json main.py
python -m pyflakes gestor_json scripts tests
```

En Git Bash, no encadenes un commit detrás de una tubería (`pytest | tail`): la tubería devuelve
el código de `tail`, no el de pytest. Usa `python -m pytest -q && git commit ...`.

## Reglas

- Python 3.10+. Dependencias de ejecución: `jsonschema` y `rfc3339-validator` (`requirements.txt`);
  de desarrollo, `requirements-dev.txt` (`mypy --disallow-untyped-defs` y `pyflakes` sin avisos).
- Nunca usar `input()`: todo por argumentos y archivos.
- **Ejecuta los tests antes de cada commit.** No hagas commit con tests en rojo.
- Commits pequeños, en español, formato *Conventional Commits* (`feat:`, `fix:`, `test:`,
  `refactor:`, `perf:`, `docs:`, `chore:`).
- Nunca reescribir el historial (`rebase -i`, `--amend` sobre commits subidos, `push --force`).
- Todos los datos son inventados por el generador del proyecto; no se usan JSON externos.
- Nunca versionar datos generados grandes (van a `datos/generados/`), ni tokens o contraseñas
  (el token de SonarQube está en el secreto `SONAR_TOKEN` de GitHub).
- Mantener `docs/registro-ia.md` al terminar cada bloque de trabajo con IA, sin inventar tiempos.
- `tests/test_caracterizacion.py` fija el comportamiento observable (mensajes, informes byte a
  byte, códigos de salida) con el formato propio: un cambio de comportamiento debe ser deliberado
  y actualizar la referencia de forma explícita. Los informes con JSON Schema deben ser idénticos
  (lo comprueban los tests de equivalencia).
- Los mensajes de error de la CLI son los del programa original; `cli.py` no deja que `argparse`
  imprima los suyos.
- Los tests deben pasar en Windows y en Linux: los JSON se comparan con las referencias
  normalizando el salto de línea (`conftest.contenido_comparable`); los CSV, byte a byte.
- **Calidad:** cada pull request y cada push a `main` pasan por el workflow `calidad.yml`, que
  ejecuta los tests con cobertura y analiza `gestor_json/` en SonarQube Cloud
  (proyecto `mrosmdeveloper-tech_formacion-ia`; el plan Free analiza `main` y los pull requests).
  El quality gate debe estar en verde. Un aviso de seguridad se corrige o, si es un falso
  positivo, se justifica, comprobando antes su traza.

## Trampas conocidas

- `bool` es subclase de `int`: comprueba **siempre** `bool` antes que número.
- `int` y `float` son el mismo tipo lógico: **número**.
- `null` y `[]` en un modelo → **desconocido** (acepta cualquier cosa) hasta que otro modelo lo concrete.
- `""` es **texto**.
- Claves con espacios o símbolos: rutas sin ambigüedad (`$.pulso["zona 1"]`).
- Leer siempre con `encoding="utf-8-sig"` (puede haber BOM).
- `date-time` (JSON Schema) exige zona horaria (RFC 3339); las fechas del generador no la llevan.
- Los JSON se escriben en modo texto: CRLF en Windows y LF en Linux.
