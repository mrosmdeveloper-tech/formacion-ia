# Gestor de tipos JSON

Herramienta de línea de comandos que deduce esquemas a partir de JSON modelo, clasifica archivos por su nombre y los valida contra el esquema de su tipo.

La especificación completa está en [docs/especificacion.md](docs/especificacion.md).

## Requisitos

- Python 3.10 o superior (solo biblioteca estándar).
- Para desarrollo: `pytest` y `pytest-cov`.

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
```

- El punto de entrada es `main.py`; el programa está en el paquete `gestor_json/`.
- Los esquemas se guardan en `esquemas.json`, en la carpeta desde la que se ejecuta el programa.
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

## Estructura

```
main.py                  # punto de entrada
gestor_json/
  cli.py                 # argumentos (argparse), orquestación y códigos de salida
  registro.py            # alta, actualización, baja y clasificación de tipos por patrón
  almacenamiento.py      # lectura y escritura de esquemas.json
  inferencia.py          # deducción del esquema a partir de un modelo
  fusion.py              # fusión de esquemas de varios modelos
  validacion.py          # validación de un documento contra su esquema
  lote.py                # validación de un archivo o carpeta y estadísticas del lote
  informes.py            # CSV, resumen_lote.json y resumen por consola
  modelos.py             # estructuras de datos (esquema, tipo, incidencia, resultado)
  rutas.py               # rutas JSONPath de las incidencias
  tipos_logicos.py       # tipos lógicos y clasificación de valores
  config.py              # constantes
scripts/generar_datos.py # generador de datos sintéticos
tests/                   # tests de caracterización y unitarios
docs/                    # especificación, plan de refactorización, registro de IA
```

El programa nació como un único archivo, `gestor.py`, con estilo legacy deliberado, y se
refactorizó a este paquete sin cambiar su comportamiento: ver
[docs/plan-refactorizacion.md](docs/plan-refactorizacion.md).

## Tests

```powershell
python -m pytest
python -m pytest --cov=gestor_json --cov-report=term-missing --cov-report=html
```

- `tests/test_caracterizacion.py`: ejecutan los comandos de principio a fin y comparan
  `esquemas.json`, los informes (byte a byte), la consola y los códigos de salida. Se escribieron
  sobre la versión legacy antes de refactorizarla.
- `tests/test_<módulo>.py`: tests unitarios de cada módulo.

## Generador de datos

```
python scripts/generar_datos.py --archivos <n> --salida <carpeta> [--semilla 42] [--tasa-errores 0.1] [--pequenos]
```

Genera pedidos (`pedido_<n>.json`), lecturas de sensor (`sensor_<n>.json`), actividades GPS
(`ruta_<n>.json`) y alrededor de un 3 % de archivos sin tipo. Los errores inyectados son: falta un
campo obligatorio, campo extra, número guardado como texto, texto en lugar de objeto, `null` no
permitido, elemento de lista con otra forma y JSON mal formado. Es reproducible con la misma semilla.
Los lotes grandes van a `datos/generados/`, que no se versiona.
