# Registro de uso de IA

| Fase | Qué hizo la IA | Qué decidió/revisó el usuario | Tiempo real | Tiempo estimado sin IA |
|------|----------------|-------------------------------|-------------|------------------------|
| 0 – Preparación | Creó `.gitignore`, `requirements-dev.txt`, el entorno `.venv`, `docs/especificacion.md` (a partir del roadmap), `CLAUDE.md`, `README.md` y este registro; comprobó Docker (no disponible); hizo los commits y el push | Definió el roadmap, revisó la preparación y pidió añadir esta fila | 20 min | 45-60 min |
| 1 – Generador y legacy | Escribió `scripts/generar_datos.py` (3 tipos con modelos, recorridos GPS coherentes, 7 clases de errores inyectados, formatos variados, reproducible); generó `datos/ejemplos/` buscando una semilla que cubriera todos los tipos y errores; implementó `gestor.py` en estilo legacy deliberado en 7 pasos; comprobó que el validador detecta exactamente los errores inyectados; escribió el README | Revisé y acepté las decisiones de diseño (reparto de tipos, formato de uniones, agrupación de rutas, flag --pequenos); ejecuté el generador y el gestor, y verifiqué los informes de salida | 40 min (de 17:41 a 18:21) | 8-12 h |
