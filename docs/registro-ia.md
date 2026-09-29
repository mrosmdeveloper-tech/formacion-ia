# Registro de uso de IA

| Fase | Qué hizo la IA | Qué decidió/revisó el usuario | Tiempo real | Tiempo estimado sin IA |
|------|----------------|-------------------------------|-------------|------------------------|
| 0 – Preparación | Creó `.gitignore`, `requirements-dev.txt`, el entorno `.venv`, `docs/especificacion.md` (a partir del roadmap), `CLAUDE.md`, `README.md` y este registro; comprobó Docker (no disponible); hizo los commits y el push | Definió el roadmap, revisó la preparación y pidió añadir esta fila | <rellenar> | <rellenar> |
| 1 – Generador y legacy | Escribió `scripts/generar_datos.py` (3 tipos con modelos, recorridos GPS coherentes, 7 clases de errores inyectados, formatos variados, reproducible); generó `datos/ejemplos/` buscando una semilla que cubriera todos los tipos y errores; implementó `gestor.py` en estilo legacy deliberado en 7 pasos; comprobó que el validador detecta exactamente los errores inyectados; escribió el README | Revisó la fase, el reparto de tipos del lote (pedido 45 %, sensor 40 %, actividad 12 %, sin tipo 3 %) y los detalles de formato elegidos por la IA | <rellenar> | <rellenar> |
