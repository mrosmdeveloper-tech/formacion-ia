"""Informes de la validación: dos CSV, el resumen del lote en JSON y el resumen por consola."""

from __future__ import annotations

import csv
import json
import os
from types import TracebackType

from gestor_json.config import ARCHIVO_INCIDENCIAS, ARCHIVO_RESUMEN_ARCHIVOS, ARCHIVO_RESUMEN_LOTE
from gestor_json.lote import ResumenLote
from gestor_json.modelos import ResultadoArchivo

CABECERA_INCIDENCIAS = ["archivo", "tipo", "nivel", "categoria", "ruta", "esperado", "encontrado",
                        "mensaje"]
CABECERA_RESUMEN_ARCHIVOS = ["archivo", "tipo", "valido", "errores", "avisos"]


class EscritorInformes:
    """Escribe ``incidencias.csv`` y ``resumen_archivos.csv`` archivo a archivo.

    Los archivos se crean al construir el objeto (así los errores de la carpeta de salida se
    detectan antes de validar nada) y se cierran al salir del bloque ``with``.
    """

    def __init__(self, carpeta: str) -> None:
        os.makedirs(carpeta, exist_ok=True)
        self._incidencias = open(os.path.join(carpeta, ARCHIVO_INCIDENCIAS), "w", newline="",
                                 encoding="utf-8")
        try:
            self._resumen = open(os.path.join(carpeta, ARCHIVO_RESUMEN_ARCHIVOS), "w", newline="",
                                 encoding="utf-8")
        except Exception:
            self._incidencias.close()
            raise
        self._csv_incidencias = csv.writer(self._incidencias)
        self._csv_resumen = csv.writer(self._resumen)
        self._csv_incidencias.writerow(CABECERA_INCIDENCIAS)
        self._csv_resumen.writerow(CABECERA_RESUMEN_ARCHIVOS)

    def __enter__(self) -> EscritorInformes:
        return self

    def __exit__(self, tipo: type[BaseException] | None, error: BaseException | None,
                 traza: TracebackType | None) -> None:
        self._incidencias.close()
        self._resumen.close()

    def escribir(self, resultado: ResultadoArchivo) -> None:
        """Añade las incidencias del archivo y su fila de resumen."""
        for incidencia in resultado.incidencias:
            self._csv_incidencias.writerow([
                resultado.archivo, resultado.tipo, incidencia.nivel, incidencia.categoria,
                incidencia.ruta, incidencia.esperado, incidencia.encontrado, incidencia.mensaje,
            ])
        self._csv_resumen.writerow([resultado.archivo, resultado.tipo,
                                    "si" if resultado.valido else "no",
                                    resultado.errores, resultado.avisos])


def escribir_resumen_lote(carpeta: str, resumen: ResumenLote, segundos: float) -> None:
    """Escribe ``resumen_lote.json`` con los totales, las categorías y las rutas más frecuentes."""
    datos = {
        "archivos_totales": resumen.archivos_totales,
        "por_tipo": resumen.por_tipo,
        "validos": resumen.validos,
        "con_errores": resumen.con_errores,
        "sin_tipo": resumen.sin_tipo,
        "incidencias_por_categoria": resumen.categorias_ordenadas(),
        "rutas_mas_frecuentes": {
            tipo: [{"ruta": ruta, "incidencias": total} for ruta, total in rutas]
            for tipo, rutas in resumen.rutas_mas_frecuentes().items()
        },
        "tiempo_s": segundos,
    }
    with open(os.path.join(carpeta, ARCHIVO_RESUMEN_LOTE), "w", encoding="utf-8") as archivo:
        json.dump(datos, archivo, indent=2, ensure_ascii=False)


def imprimir_resumen(carpeta: str, resumen: ResumenLote, segundos: float) -> None:
    """Muestra por consola el resumen del lote y el tiempo total."""
    print(f"Archivos procesados: {resumen.archivos_totales}")
    for tipo, total in resumen.por_tipo.items():
        print(f"  {tipo}: {total}")
    print(f"  sin tipo: {resumen.sin_tipo}")
    print(f"Válidos: {resumen.validos}  Con errores: {resumen.con_errores}  "
          f"Sin tipo: {resumen.sin_tipo}")
    print(f"Incidencias: {resumen.total_incidencias}")
    for categoria, total in resumen.categorias_ordenadas().items():
        print(f"  {categoria}: {total}")
    print(f"Informes en: {carpeta}")
    print(f"Tiempo total: {segundos} s")
