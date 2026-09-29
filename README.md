# Gestor de tipos JSON

Herramienta de línea de comandos que deduce esquemas a partir de JSON modelo, clasifica archivos por su nombre y los valida contra el esquema de su tipo.

La especificación completa está en [docs/especificacion.md](docs/especificacion.md).

## Requisitos

- Python 3.10 o superior.
- Dependencias: `jsonschema` y `rfc3339-validator` ([requirements.txt](requirements.txt)).
- Para desarrollo, además: `pytest`, `pytest-cov`, `mypy`, `pyflakes` y `types-jsonschema`
  ([requirements-dev.txt](requirements-dev.txt), que incluye `requirements.txt`).

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

## Comandos

```
python main.py registrar --tipo <nombre> --patron "<patrón>" --modelo <archivo> [--modelo <archivo> ...]
python main.py actualizar --tipo <nombre> --modelo <archivo> [--modelo <archivo> ...]
python main.py tipos
python main.py mostrar --tipo <nombre>
python main.py eliminar --tipo <nombre>
python main.py validar <archivo_o_carpeta> --salida <carpeta> [--estricto] [--max-incidencias 200]
python main.py migrar-esquemas [--desde esquemas.json] [--hacia esquemas] [--verificar <archivo_o_carpeta>]
python main.py exportar-vscode [--esquemas esquemas] [--salida .vscode/settings.json]
```

- El punto de entrada es `main.py`; el programa está en el paquete `gestor_json/`.
- Los seis primeros comandos aceptan `--formato jsonschema|propio` (por defecto, `jsonschema`;
  ver [Formatos de esquema](#formatos-de-esquema)).
- Cada archivo se clasifica por su nombre con el patrón de cada tipo (estilo `fnmatch`). Si encaja
  con varios, gana el patrón más específico.
- `validar` escribe en la carpeta de salida `incidencias.csv`, `resumen_archivos.csv` y
  `resumen_lote.json`, y termina con código 0 (todo válido), 1 (hay errores) o 2 (fallo de ejecución).

## Ejemplo completo

1. Generar un lote de 1000 archivos inventados (con un 10 % de errores inyectados):

   ```powershell
   python scripts/generar_datos.py --archivos 1000 --salida datos/generados/lote_1000 --semilla 42 --tasa-errores 0.1
   ```

   Se crean `datos/generados/lote_1000/modelos/` (3 modelos por tipo) y
   `datos/generados/lote_1000/entrada/` (los archivos a validar).

2. Registrar los tres tipos con sus modelos:

   ```powershell
   $m = "datos/generados/lote_1000/modelos"
   python main.py registrar --tipo pedido --patron "pedido_*.json" --modelo $m/pedido_modelo_1.json --modelo $m/pedido_modelo_2.json --modelo $m/pedido_modelo_3.json
   python main.py registrar --tipo lectura_sensor --patron "sensor_*.json" --modelo $m/sensor_modelo_1.json --modelo $m/sensor_modelo_2.json --modelo $m/sensor_modelo_3.json
   python main.py registrar --tipo actividad --patron "ruta_*.json" --modelo $m/ruta_modelo_1.json --modelo $m/ruta_modelo_2.json --modelo $m/ruta_modelo_3.json
   ```

   (En Git Bash, la primera línea es `m="datos/generados/lote_1000/modelos"`.)

3. Consultar los tipos y el esquema deducido:

   ```powershell
   python main.py tipos
   python main.py mostrar --tipo pedido
   ```

4. Validar el lote:

   ```powershell
   python main.py validar datos/generados/lote_1000/entrada --salida salida/lote_1000
   ```

Para una prueba rápida, en `datos/ejemplos/` hay modelos de los tres tipos y 14 archivos pequeños
(válidos y con errores) versionados en el repositorio.

## Formatos de esquema

### JSON Schema (por defecto)

Los esquemas deducidos se guardan como **JSON Schema draft 2020-12**, un archivo por tipo, y se
validan con la librería `jsonschema` (decisión: [ADR 0001](docs/adr/0001-json-schema.md)):

```
esquemas/
  registro.json               # índice: tipo, patrón, archivo, modelos usados y fecha, en orden de registro
  pedido.schema.json
  lectura_sensor.schema.json
  actividad.schema.json
```

Además de tipos, campos obligatorios y nulos, el esquema admite las reglas estándar de JSON Schema
(`minimum`/`maximum`, `pattern`, `enum`, `format`, `minItems`…). Un valor que las incumple da una
incidencia `regla_incumplida` (nivel error).

### Añadir una regla a mano

El esquema deducido se puede enriquecer editando su `.schema.json`. Por ejemplo, para exigir que la
cantidad de cada línea de un pedido sea al menos 1, en `esquemas/pedido.schema.json`:

```json
"cantidad": {
  "type": "number",
  "minimum": 1
}
```

Al validar, una línea con `"cantidad": 0` da:

```
pedido_0042.json,pedido,error,regla_incumplida,$.lineas[3].cantidad,minimum: 1,0,Regla 'minimum' incumplida: debe ser mayor o igual que 1
```

Las reglas añadidas a mano **se conservan** cuando el esquema se vuelve a generar (por ejemplo, con
`actualizar`). Lo que se regenera a partir de los modelos es la estructura: `type`, `properties`,
`required`, `additionalProperties` e `items`.

Los formatos se comprueban de verdad (`email`, `date-time`…). `date-time` sigue el RFC 3339 y
**exige zona horaria** (`2026-09-29T10:00:00Z` o `…+02:00`): las fechas del generador de datos no
la llevan, así que esa regla las marcaría todas como incumplidas.

### Formato propio (`--formato propio`)

El formato original, en un único `esquemas.json`. Solo describe tipos, obligatorios, nulos y
uniones (ver [docs/capacidades.md](docs/capacidades.md)). Se mantiene para comparar y para migrar.

### Migrar del formato propio

```powershell
python main.py migrar-esquemas --desde esquemas.json --hacia esquemas --verificar datos/ejemplos/entrada
```

Copia todos los tipos (con su patrón, sus modelos usados, su fecha y el orden de registro) y, con
`--verificar`, valida esos archivos con los dos formatos y comprueba que dan las mismas incidencias.

### Validación en VS Code

```powershell
python main.py exportar-vscode
```

Genera `.vscode/settings.json` con `json.schemas`, que asocia cada patrón con su esquema: al abrir
en VS Code un `pedido_*.json`, el editor subraya los errores mientras se escribe. Si el archivo ya
existe, conserva el resto de la configuración.

## Estructura

```
main.py                    # punto de entrada
gestor_json/
  cli.py                   # argumentos (argparse), orquestación y códigos de salida
  registro.py              # alta, actualización, baja y clasificación de tipos por patrón
  almacenamiento.py        # interfaz AlmacenEsquemas y formato propio (esquemas.json)
  jsonschema_formato.py    # JSON Schema: conversión, almacén, validador y exportación a VS Code
  migracion.py             # migración del formato propio a JSON Schema y su verificación
  inferencia.py            # deducción del esquema a partir de un modelo
  fusion.py                # fusión de esquemas de varios modelos
  validacion.py            # interfaz Validador y validador del formato propio
  lote.py                  # validación de un archivo o carpeta y estadísticas del lote
  informes.py              # CSV, resumen_lote.json y resumen por consola
  modelos.py               # estructuras de datos (esquema, tipo, incidencia, resultado)
  rutas.py                 # rutas JSONPath de las incidencias
  tipos_logicos.py         # tipos lógicos y clasificación de valores
  config.py                # constantes
scripts/generar_datos.py   # generador de datos sintéticos
scripts/benchmark.py       # benchmark de registro y validación por formato
tests/                     # tests de caracterización, unitarios, de JSON Schema y de migración
docs/                      # especificación, plan de refactorización, ADR, benchmark, capacidades, registro de IA
```

El programa nació como un único archivo, `gestor.py`, con estilo legacy deliberado, y se
refactorizó a este paquete sin cambiar su comportamiento: ver
[docs/plan-refactorizacion.md](docs/plan-refactorizacion.md).

## Tests

```powershell
python -m pytest
python -m pytest --cov=gestor_json --cov-report=term-missing --cov-report=html
```

- `tests/test_caracterizacion.py`: ejecutan los comandos de principio a fin con el formato propio y
  comparan `esquemas.json`, los informes (byte a byte), la consola y los códigos de salida. Se
  escribieron sobre la versión legacy antes de refactorizarla.
- `tests/test_jsonschema_formato.py`: conversión, almacén y validador de JSON Schema; equivalencia
  de los informes con los dos formatos; reglas añadidas a mano (`minimum`, `pattern`, `format`,
  `enum`…).
- `tests/test_migracion.py`: migración, verificación y exportación a VS Code.
- `tests/test_<módulo>.py`: tests unitarios del resto de módulos.

## Calidad

Cada pull request y cada push a `main` ejecutan el workflow
[`.github/workflows/calidad.yml`](.github/workflows/calidad.yml): los tests con cobertura en Linux
(`coverage.xml`) y el análisis en
[SonarQube Cloud](https://sonarcloud.io/project/overview?id=mrosmdeveloper-tech_formacion-ia), que
importa esa cobertura. El token de SonarQube está en el secreto `SONAR_TOKEN` del repositorio, no
en ningún archivo.

Resultado del análisis del PR #2 (JSON Schema), sobre `gestor_json/` (668 líneas de código):

| Métrica | Resultado |
|---|---|
| Quality gate (Sonar way) | ✅ Passed |
| Cobertura | 99,2 % global; 100 % del código nuevo (igual que pytest-cov) |
| Bugs | 0 (fiabilidad A) |
| Vulnerabilidades | 0 (seguridad A) |
| Code smells | 0 (mantenibilidad A) |
| Security hotspots | 0 |
| Duplicaciones | 0 % |

Revisión de los avisos de seguridad:

- **Corregido:** en el formato JSON Schema, un nombre de tipo como `../fuera` escribía su esquema
  fuera de `esquemas/`. Ahora se rechazan los nombres que no sirven como nombre de archivo, y un
  índice editado a mano no puede apuntar a archivos fuera de la carpeta.
- **Falsos positivos**, marcados como tales en SonarQube Cloud con su justificación:
  - `pythonsecurity:S8707` (×2), *path traversal* en `exportar-vscode --salida`: es la ruta de
    destino que elige el usuario, como en `validar --salida`; el programa se ejecuta con sus
    permisos y no cruza ninguna frontera de privilegios.
  - `python:S2245` (×2), generador pseudoaleatorio en `scripts/generar_datos.py`: el azar solo
    decide qué datos inventados se generan y el lote tiene que ser reproducible con una semilla,
    algo que `secrets` no permite. Además, `scripts/` queda fuera del análisis
    (`sonar.sources=gestor_json`).

## Benchmark

```powershell
python scripts/benchmark.py datos/generados/lote_1000 datos/generados/lote_5000 --formatos propio jsonschema --salida docs/benchmark.md
```

Mide, en un subproceso nuevo por repetición, el registro y la validación de cada lote con cada
formato. Resultados: [docs/benchmark.md](docs/benchmark.md).

## Generador de datos

```
python scripts/generar_datos.py --archivos <n> --salida <carpeta> [--semilla 42] [--tasa-errores 0.1] [--pequenos]
```

Genera pedidos (`pedido_<n>.json`), lecturas de sensor (`sensor_<n>.json`), actividades GPS
(`ruta_<n>.json`) y alrededor de un 3 % de archivos sin tipo. Los errores inyectados son: falta un
campo obligatorio, campo extra, número guardado como texto, texto en lugar de objeto, `null` no
permitido, elemento de lista con otra forma y JSON mal formado. Es reproducible con la misma semilla.
Los lotes grandes van a `datos/generados/`, que no se versiona.
