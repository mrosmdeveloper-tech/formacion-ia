"""Validación de un archivo o de todos los JSON de una carpeta, y agregación de resultados."""

from __future__ import annotations

import os
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from gestor_json.almacenamiento import leer_json
from gestor_json.config import EXTENSION_JSON, TOP_RUTAS
from gestor_json.modelos import Incidencia, ResultadoArchivo, TipoRegistrado
from gestor_json.registro import clasificar_archivo
from gestor_json.rutas import normalizar
from gestor_json.validacion import FabricaValidador, Validador, crear_validador_propio


def listar_archivos(ruta: str | Path) -> list[Path]:
    """El propio archivo o los ``.json`` de la carpeta (sin subcarpetas), por orden alfabético."""
    ruta = Path(ruta)
    if not ruta.is_dir():
        return [ruta]
    return [ruta / nombre for nombre in sorted(os.listdir(ruta))
            if (ruta / nombre).is_file() and nombre.lower().endswith(EXTENSION_JSON)]


class ValidadorLote:
    """Clasifica y valida archivos. Crea un validador por tipo y lo reutiliza en todo el lote."""

    def __init__(self, tipos: dict[str, TipoRegistrado], estricto: bool, max_incidencias: int,
                 fabrica_validador: FabricaValidador = crear_validador_propio) -> None:
        self._tipos = tipos
        self._estricto = estricto
        self._max_incidencias = max_incidencias
        self._fabrica_validador = fabrica_validador
        self._validadores: dict[str, Validador] = {}

    def validar_archivo(self, ruta: Path) -> ResultadoArchivo:
        """Clasifica el archivo por su nombre y, si tiene tipo, lo valida contra su esquema."""
        clasificacion = clasificar_archivo(ruta.name, self._tipos)
        tipo = clasificacion.tipo
        if tipo is None:
            return ResultadoArchivo(ruta.name, "", [Incidencia.sin_tipo()])

        incidencias = []
        if clasificacion.ambigua:
            incidencias.append(Incidencia.varios_tipos(tipo.nombre, clasificacion.candidatos))
        try:
            documento = leer_json(ruta)
        except Exception as error:  # noqa: BLE001 - un archivo ilegible es una incidencia más
            incidencias.append(Incidencia.json_invalido(str(error)))
        else:
            incidencias.extend(self._validador(tipo).validar(documento))
        return ResultadoArchivo(ruta.name, tipo.nombre, self._truncar(incidencias))

    def _validador(self, tipo: TipoRegistrado) -> Validador:
        if tipo.nombre not in self._validadores:
            self._validadores[tipo.nombre] = self._fabrica_validador(tipo, self._estricto)
        return self._validadores[tipo.nombre]

    def _truncar(self, incidencias: list[Incidencia]) -> list[Incidencia]:
        if len(incidencias) <= self._max_incidencias:
            return incidencias
        return incidencias[:self._max_incidencias] + [
            Incidencia.incidencias_truncadas(self._max_incidencias, len(incidencias))]


@dataclass
class ResumenLote:
    """Estadísticas acumuladas de un lote."""

    por_tipo: dict[str, int]
    archivos_totales: int = 0
    validos: int = 0
    con_errores: int = 0
    sin_tipo: int = 0
    incidencias_por_categoria: Counter = field(default_factory=Counter)
    rutas_por_tipo: dict[str, Counter] = field(default_factory=dict)

    @classmethod
    def para(cls, tipos: dict[str, TipoRegistrado]) -> ResumenLote:
        """Resumen vacío con un contador a cero por cada tipo, en orden de registro."""
        return cls(por_tipo=dict.fromkeys(tipos, 0))

    def agregar(self, resultado: ResultadoArchivo) -> None:
        """Suma el resultado de un archivo a las estadísticas."""
        self.archivos_totales += 1
        for incidencia in resultado.incidencias:
            self.incidencias_por_categoria[incidencia.categoria] += 1
            if resultado.tiene_tipo and incidencia.ruta:
                rutas = self.rutas_por_tipo.setdefault(resultado.tipo, Counter())
                rutas[normalizar(incidencia.ruta)] += 1
        if not resultado.tiene_tipo:
            self.sin_tipo += 1
            return
        self.por_tipo[resultado.tipo] += 1
        if resultado.valido:
            self.validos += 1
        else:
            self.con_errores += 1

    @property
    def total_incidencias(self) -> int:
        """Incidencias de todos los archivos (las escritas en ``incidencias.csv``)."""
        return sum(self.incidencias_por_categoria.values())

    def categorias_ordenadas(self) -> dict[str, int]:
        """Incidencias por categoría, en orden alfabético."""
        return dict(sorted(self.incidencias_por_categoria.items()))

    def rutas_mas_frecuentes(self) -> dict[str, list[tuple[str, int]]]:
        """Por tipo (en orden de registro), las rutas con más incidencias; a igualdad, por ruta."""
        return {
            tipo: sorted(self.rutas_por_tipo[tipo].items(), key=lambda par: (-par[1], par[0]))[:TOP_RUTAS]
            for tipo in self.por_tipo if tipo in self.rutas_por_tipo
        }
