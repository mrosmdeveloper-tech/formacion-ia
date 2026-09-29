"""Benchmark del gestor de tipos JSON: registro y validación de lotes completos.

Para cada lote (una carpeta con ``modelos/`` y ``entrada/``, como las que crea
``generar_datos.py``) y cada formato de esquema, lanza un **subproceso nuevo** que, en una carpeta
temporal vacía, registra los tres tipos con sus modelos y valida todos los archivos de entrada.
Mide dentro del subproceso (sin contar el arranque del intérprete) el tiempo de registro y el de
validación, y cuenta las incidencias. Repite cada medición y se queda con la mediana.

Uso::

    python scripts/benchmark.py datos/generados/lote_1000 datos/generados/lote_5000 \
        --formatos propio --repeticiones 3 --salida docs/benchmark.md
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# (tipo, patrón, prefijo de los modelos) de los lotes de generar_datos.py
TIPOS = (
    ("pedido", "pedido_*.json", "pedido"),
    ("lectura_sensor", "sensor_*.json", "sensor"),
    ("actividad", "ruta_*.json", "ruta"),
)

# Argumentos que selecciona cada formato de esquema en la línea de comandos.
FORMATOS: dict[str, list[str]] = {
    "propio": ["--formato", "propio"],
    "jsonschema": ["--formato", "jsonschema"],
}

# Código que ejecuta cada subproceso: recibe la configuración en JSON y devuelve las medidas.
_MEDICION = """
import contextlib, io, json, sys, time
sys.path.insert(0, {raiz!r})
from gestor_json.cli import main

cfg = json.loads(sys.argv[1])
with contextlib.redirect_stdout(io.StringIO()):
    inicio = time.perf_counter()
    for args in cfg["registros"]:
        assert main(args) == 0, args
    registro = time.perf_counter() - inicio
    inicio = time.perf_counter()
    codigo = main(cfg["validacion"])
    validacion = time.perf_counter() - inicio
assert codigo in (0, 1), codigo
resumen = json.load(open("salida/resumen_lote.json", encoding="utf-8"))
print(json.dumps({{
    "registro": registro,
    "validacion": validacion,
    "archivos": resumen["archivos_totales"],
    "incidencias": sum(resumen["incidencias_por_categoria"].values()),
}}))
"""


@dataclass
class Resultado:
    lote: str
    formato: str
    archivos: int
    registro_s: float
    validacion_s: float
    incidencias: int

    @property
    def archivos_por_segundo(self) -> float:
        return self.archivos / self.validacion_s


def _configuracion(lote: Path, formato: str) -> dict:
    opciones = FORMATOS[formato]
    registros = []
    for tipo, patron, prefijo in TIPOS:
        args = ["registrar", "--tipo", tipo, "--patron", patron, *opciones]
        for n in (1, 2, 3):
            args += ["--modelo", str(lote / "modelos" / f"{prefijo}_modelo_{n}.json")]
        registros.append(args)
    validacion = ["validar", str(lote / "entrada"), "--salida", "salida", *opciones]
    return {"registros": registros, "validacion": validacion}


def medir_una_vez(lote: Path, formato: str) -> dict:
    """Ejecuta registro y validación en un subproceso nuevo y en una carpeta vacía."""
    codigo = _MEDICION.format(raiz=str(RAIZ))
    configuracion = json.dumps(_configuracion(lote, formato))
    with tempfile.TemporaryDirectory(prefix="benchmark_") as carpeta:
        proceso = subprocess.run([sys.executable, "-c", codigo, configuracion], cwd=carpeta,
                                 capture_output=True, text=True, encoding="utf-8")
    if proceso.returncode != 0:
        raise RuntimeError(f"Falló la medición de {lote} ({formato}):\n{proceso.stderr}")
    return json.loads(proceso.stdout)


def medir(lote: Path, formato: str, repeticiones: int) -> Resultado:
    """Mediana de ``repeticiones`` mediciones; las incidencias deben coincidir en todas."""
    medidas = [medir_una_vez(lote, formato) for _ in range(repeticiones)]
    incidencias = {m["incidencias"] for m in medidas}
    if len(incidencias) != 1:
        raise RuntimeError(f"Las incidencias no coinciden entre repeticiones: {incidencias}")
    return Resultado(
        lote=lote.name,
        formato=formato,
        archivos=medidas[0]["archivos"],
        registro_s=statistics.median(m["registro"] for m in medidas),
        validacion_s=statistics.median(m["validacion"] for m in medidas),
        incidencias=incidencias.pop(),
    )


def tabla(resultados: list[Resultado]) -> str:
    filas = [
        "| Lote | Formato | Archivos | Registro (s) | Validación (s) | Archivos/s | Incidencias |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for r in resultados:
        filas.append(f"| {r.lote} | {r.formato} | {r.archivos} | {r.registro_s:.3f} | "
                     f"{r.validacion_s:.2f} | {r.archivos_por_segundo:.0f} | {r.incidencias} |")
    return "\n".join(filas)


def _tamano_mb(lote: Path) -> float:
    entrada = lote / "entrada"
    return sum(f.stat().st_size for f in entrada.iterdir()) / 1_048_576


def informe(resultados: list[Resultado], lotes: list[Path], repeticiones: int) -> str:
    tamanos = ", ".join(f"{lote.name}: {_tamano_mb(lote):.0f} MB" for lote in lotes)
    return f"""# Benchmark

Medido el {date.today().isoformat()} con `scripts/benchmark.py`.

- **Qué se mide:** en un subproceso nuevo y en una carpeta vacía, el registro de los tres tipos
  (3 modelos cada uno) y la validación de todos los archivos del lote, llamando a la CLI dentro
  del proceso (sin contar el arranque del intérprete). Mediana de {repeticiones} repeticiones.
- **Lotes:** generados con `scripts/generar_datos.py --semilla 42 --tasa-errores 0.1`
  ({tamanos} de entrada).
- **Máquina:** {platform.system()} {platform.release()}, {platform.processor() or platform.machine()},
  {os.cpu_count()} CPU lógicas, Python {platform.python_version()}.

{tabla(resultados)}
"""


def _parsear_argumentos(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark de registro y validación de lotes.")
    parser.add_argument("lotes", nargs="+", type=lambda r: Path(r).resolve(),
                        help="carpetas con modelos/ y entrada/")
    parser.add_argument("--formatos", nargs="+", choices=list(FORMATOS), default=["propio"])
    parser.add_argument("--repeticiones", type=int, default=3)
    parser.add_argument("--salida", type=Path, help="archivo Markdown donde guardar el informe")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parsear_argumentos(argv)
    resultados = []
    for lote in args.lotes:
        for formato in args.formatos:
            print(f"Midiendo {lote.name} con formato {formato}...", file=sys.stderr, flush=True)
            resultados.append(medir(lote, formato, args.repeticiones))
    texto = informe(resultados, args.lotes, args.repeticiones)
    print(tabla(resultados))
    if args.salida:
        args.salida.write_text(texto, encoding="utf-8")
        print(f"\nInforme guardado en {args.salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
