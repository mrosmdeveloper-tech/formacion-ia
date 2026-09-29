# CLAUDE.md

## Proyecto

Gestor de tipos JSON: herramienta de línea de comandos que registra tipos a partir de JSON modelo,
deduce su esquema, clasifica archivos por su nombre (patrón `fnmatch`) y los valida contra el
esquema de su tipo, generando informes de incidencias. La especificación completa está en
[docs/especificacion.md](docs/especificacion.md).

Es un proyecto de formación en desarrollo con IA. **Sigue `ROADMAP_GESTOR_JSON.md` fase a fase**:
ejecuta solo la fase que indique el usuario y detente en cada ⏸ PARADA (el archivo está en
`.gitignore` y no se versiona).

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
  lote.py                # ValidadorLote (un archivo o una carpeta) y ResumenLote
  informes.py            # CSV, resumen_lote.json y resumen por consola
  cli.py                 # argparse con subcomandos, orquestación y códigos de salida
scripts/generar_datos.py # generador de datos sintéticos
datos/ejemplos/          # datos pequeños versionados
datos/generados/         # lotes grandes generados (no versionado)
tests/
  test_caracterizacion.py  # tests de principio a fin (esquemas.json, informes, consola, códigos)
  test_<módulo>.py         # tests unitarios de cada módulo
  datos/                   # JSON mínimos diseñados a mano y referencia (esperado/) del lote de ejemplo
docs/                    # especificación, registro de IA, plan de refactorización, ADR, benchmark
```

Diseño: el registro, el lote y los informes solo dependen de las interfaces `Validador` y
`AlmacenEsquemas`; el formato del esquema (hoy el propio de `esquemas.json`) queda encerrado en
`validacion.py` y `almacenamiento.py`. Los códigos `"str"`, `"num"`… solo existen en
`almacenamiento.py`.

## Comandos

Entorno (Windows, PowerShell):
```
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

Ejecutar:
```
python main.py registrar --tipo pedido --patron "pedido_*.json" --modelo <archivo>
python main.py validar <archivo_o_carpeta> --salida salida/
```

Tests y cobertura:
```
python -m pytest
python -m pytest --cov=gestor_json --cov-report=term-missing --cov-report=html
```

## Reglas

- Python 3.10+. Hasta la Fase 4, solo biblioteca estándar (en desarrollo, `pytest` y `pytest-cov`).
- Nunca usar `input()`: todo por argumentos y archivos.
- **Ejecuta los tests antes de cada commit.** No hagas commit con tests en rojo.
- Commits pequeños, en español, formato *Conventional Commits* (`feat:`, `fix:`, `test:`,
  `refactor:`, `perf:`, `docs:`, `chore:`).
- Nunca reescribir el historial (`rebase -i`, `--amend` sobre commits subidos, `push --force`).
- Nunca versionar datos generados grandes (van a `datos/generados/`), ni tokens o contraseñas.
- Todos los datos son inventados por el generador del proyecto.
- Mantener `docs/registro-ia.md` al final de cada fase, sin inventar tiempos.
- `tests/test_caracterizacion.py` fija el comportamiento observable (mensajes, informes byte a
  byte, códigos de salida): un cambio de comportamiento debe ser deliberado y actualizar la
  referencia de forma explícita.
- Los mensajes de error de la CLI son los del programa original; `cli.py` no deja que `argparse`
  imprima los suyos.

## Trampas conocidas

- `bool` es subclase de `int`: comprueba **siempre** `bool` antes que número.
- `int` y `float` son el mismo tipo lógico: **número**.
- `null` y `[]` en un modelo → **desconocido** (acepta cualquier cosa) hasta que otro modelo lo concrete.
- `""` es **texto**.
- Claves con espacios o símbolos: rutas sin ambigüedad (`$.pulso["zona 1"]`).
- Leer siempre con `encoding="utf-8-sig"` (puede haber BOM).
