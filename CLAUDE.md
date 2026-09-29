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
gestor.py                # programa legacy (v0), un único archivo (Fase 1)
scripts/generar_datos.py # generador de datos sintéticos (Fase 1)
datos/ejemplos/          # datos pequeños versionados
datos/generados/         # lotes grandes generados (no versionado)
tests/                   # tests con pytest (tests/datos/ con JSON mínimos)
docs/                    # especificación, registro de IA, plan, ADR, benchmark
```

## Comandos

Entorno (Windows, PowerShell):
```
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

Ejecutar:
```
python gestor.py registrar --tipo pedido --patron "pedido_*.json" --modelo <archivo>
python gestor.py validar <archivo_o_carpeta> --salida salida/
```

Tests y cobertura:
```
python -m pytest
python -m pytest --cov=gestor --cov-report=term-missing --cov-report=html
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
- `gestor.py` tiene estilo legacy **a propósito** (Fase 1): no mejorarlo hasta la Fase 3.

## Trampas conocidas

- `bool` es subclase de `int`: comprueba **siempre** `bool` antes que número.
- `int` y `float` son el mismo tipo lógico: **número**.
- `null` y `[]` en un modelo → **desconocido** (acepta cualquier cosa) hasta que otro modelo lo concrete.
- `""` es **texto**.
- Claves con espacios o símbolos: rutas sin ambigüedad (`$.pulso["zona 1"]`).
- Leer siempre con `encoding="utf-8-sig"` (puede haber BOM).
