# Benchmark

Medido el 2026-09-29 con `scripts/benchmark.py`.

- **Qué se mide:** en un subproceso nuevo y en una carpeta vacía, el registro de los tres tipos
  (3 modelos cada uno) y la validación de todos los archivos del lote, llamando a la CLI dentro
  del proceso (sin contar el arranque del intérprete). Mediana de 3 repeticiones.
- **Lotes:** generados con `scripts/generar_datos.py --semilla 42 --tasa-errores 0.1`
  (lote_1000: 33 MB, lote_5000: 172 MB, lote_10000: 336 MB de entrada).
- **Máquina:** Windows 11, Intel64 Family 6 Model 183 Stepping 1, GenuineIntel,
  24 CPU lógicas, Python 3.12.10.

## Situación inicial: formato propio

Antes de introducir JSON Schema. La validación escala de forma lineal con el número de archivos
(unos 950 archivos/s); el registro es despreciable (los modelos son pequeños).

| Lote | Formato | Archivos | Registro (s) | Validación (s) | Archivos/s | Incidencias |
|---|---|---:|---:|---:|---:|---:|
| lote_1000 | propio | 1000 | 0.021 | 1.02 | 977 | 141 |
| lote_5000 | propio | 5000 | 0.017 | 5.41 | 924 | 722 |
| lote_10000 | propio | 10000 | 0.017 | 10.34 | 967 | 1427 |
