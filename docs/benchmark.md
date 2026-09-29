# Benchmark: formato propio frente a JSON Schema

Medido el 2026-09-29 con `scripts/benchmark.py`.

- **Qué se mide:** en un subproceso nuevo y en una carpeta vacía, el registro de los tres tipos
  (3 modelos cada uno) y la validación de todos los archivos del lote, llamando a la CLI dentro
  del proceso (sin contar el arranque del intérprete). Mediana de 3 repeticiones.
- **Lotes:** generados con `scripts/generar_datos.py --semilla 42 --tasa-errores 0.1`
  (lote_1000: 33 MB, lote_5000: 172 MB, lote_10000: 336 MB de entrada).
- **Máquina:** Windows 11, Intel64 Family 6 Model 183 Stepping 1, GenuineIntel,
  24 CPU lógicas, Python 3.12.10; `jsonschema` 4.26.0.
- **Comando:**
  `python scripts/benchmark.py datos/generados/lote_1000 datos/generados/lote_5000 datos/generados/lote_10000 --formatos propio jsonschema`

## Comparativa

| Lote | Formato | Archivos | Registro (s) | Validación (s) | Archivos/s | Incidencias |
|---|---|---:|---:|---:|---:|---:|
| lote_1000 | propio | 1000 | 0.013 | 1.02 | 977 | 141 |
| lote_1000 | jsonschema | 1000 | 0.015 | 4.82 | 207 | 141 |
| lote_5000 | propio | 5000 | 0.013 | 5.32 | 939 | 722 |
| lote_5000 | jsonschema | 5000 | 0.016 | 25.63 | 195 | 722 |
| lote_10000 | propio | 10000 | 0.014 | 10.46 | 956 | 1427 |
| lote_10000 | jsonschema | 10000 | 0.016 | 50.49 | 198 | 1427 |

Las filas del formato propio coinciden con la medición inicial, hecha antes de introducir JSON
Schema (1.02 s, 5.41 s y 10.34 s de validación): la refactorización para admitir dos formatos no ha
cambiado su rendimiento.

## Análisis

**Los resultados son los mismos.** Las incidencias coinciden en los tres lotes (141, 722 y 1427),
y los tests de equivalencia comprueban además que los tres informes son idénticos byte a byte.

**JSON Schema es unas 4,8 veces más lento validando.** Pasa de unos 950 archivos/s a unos 200
archivos/s, en los tres tamaños: las dos versiones escalan de forma lineal. El registro no cambia
(la conversión a JSON Schema se hace una vez por tipo y cuesta 1-3 ms).

**Dónde se va el tiempo.** Validando el lote de 1000 por tipo de documento, el formato propio
procesa entre 40 y 53 MB/s y `jsonschema` entre 7 y 9 MB/s, sin diferencias entre tipos: el coste
es proporcional al número de valores recorridos. Las actividades GPS (hasta 5000 puntos por
archivo) son el 85 % de los bytes y, por tanto, del tiempo. El validador propio está hecho a
medida (una comprobación de tipo y de campos por nodo); `jsonschema` es una implementación general
del estándar en Python puro, que resuelve cada palabra clave del esquema por separado y construye
un objeto de error rico (ruta, esquema, instancia) por cada fallo.

**¿Compensa?** Sí, para el uso de esta herramienta:

- La validación es por lotes, no interactiva: 10 000 archivos (336 MB) en menos de un minuto es
  aceptable. En el editor, la validación la hace VS Code, no este programa.
- A cambio se ganan las 9 capacidades que faltaban (ver [capacidades.md](capacidades.md)): reglas
  sobre los valores que se añaden a mano sin programar, validación en VS Code, esquemas
  reutilizables y un validador mantenido y probado contra la suite oficial.
- El formato propio sigue disponible con `--formato propio` si en algún caso el tiempo importa más
  que las reglas.

**Si el rendimiento llegara a ser un problema**, hay margen sin renunciar a JSON Schema:

1. **Validar en paralelo por archivos:** cada archivo es independiente y la máquina tiene 24 CPU
   lógicas; con un `ProcessPoolExecutor` el tiempo bajaría casi en proporción a los núcleos.
2. **Filtro rápido previo:** comprobar primero con `fastjsonschema` (el mismo esquema compilado a
   código) si el documento es válido, y usar `jsonschema` solo para detallar las incidencias de
   los inválidos (alrededor del 10 % en estos lotes).

No se ha implementado ninguna de las dos porque el rendimiento actual es suficiente.
