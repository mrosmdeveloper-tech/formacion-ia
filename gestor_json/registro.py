"""Registro de tipos: alta, actualización, baja, consulta y clasificación de archivos por nombre."""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from datetime import datetime
from functools import reduce

from gestor_json.almacenamiento import AlmacenEsquemas, leer_json
from gestor_json.fusion import fusionar
from gestor_json.inferencia import inferir_de_modelos, inferir_esquema
from gestor_json.modelos import ErrorGestor, TipoRegistrado

_COMODINES = "*?"


@dataclass
class Clasificacion:
    """Tipo que corresponde a un nombre de archivo y todos los tipos cuyo patrón encaja."""

    tipo: TipoRegistrado | None
    candidatos: list[str] = field(default_factory=list)

    @property
    def ambigua(self) -> bool:
        """Si el nombre encaja con más de un patrón."""
        return len(self.candidatos) > 1


def especificidad(patron: str) -> int:
    """Número de caracteres literales del patrón (los que no son comodines)."""
    return sum(1 for caracter in patron if caracter not in _COMODINES)


def clasificar_archivo(nombre_archivo: str, tipos: dict[str, TipoRegistrado]) -> Clasificacion:
    """Busca el tipo de un archivo por su nombre (sin ruta), distinguiendo mayúsculas.

    Si encajan varios patrones gana el más específico; si empatan, el registrado primero.
    """
    candidatos = [t for t in tipos.values() if fnmatch.fnmatchcase(nombre_archivo, t.patron)]
    if not candidatos:
        return Clasificacion(None)
    # max() devuelve el primero de los empatados, que es el registrado antes.
    elegido = max(candidatos, key=lambda t: especificidad(t.patron))
    return Clasificacion(elegido, [t.nombre for t in candidatos])


def _ahora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _leer_modelos(rutas: list[str]) -> list[object]:
    modelos = []
    for ruta in rutas:
        try:
            modelos.append(leer_json(ruta))
        except Exception as error:  # noqa: BLE001 - cualquier fallo de lectura se informa igual
            raise ErrorGestor(f"no se puede leer el modelo {ruta}: {error}") from error
    return modelos


class RegistroTipos:
    """Operaciones sobre los tipos registrados. Solo depende de la interfaz :class:`AlmacenEsquemas`."""

    def __init__(self, almacen: AlmacenEsquemas) -> None:
        self._almacen = almacen

    def tipos(self) -> dict[str, TipoRegistrado]:
        """Tipos registrados, en orden de registro."""
        return self._almacen.cargar()

    def obtener(self, nombre: str) -> TipoRegistrado:
        """Devuelve el tipo o lanza :class:`ErrorGestor` si no existe."""
        return self._existente(self.tipos(), nombre)

    def registrar(self, nombre: str, patron: str, rutas_modelos: list[str]) -> TipoRegistrado:
        """Crea un tipo con el esquema deducido de los modelos."""
        tipos = self.tipos()
        if nombre in tipos:
            raise ErrorGestor(f"el tipo '{nombre}' ya existe")
        esquema = inferir_de_modelos(_leer_modelos(rutas_modelos))
        tipo = TipoRegistrado(nombre, patron, len(rutas_modelos), _ahora(), esquema)
        tipos[nombre] = tipo
        self._almacen.guardar(tipos)
        return tipo

    def actualizar(self, nombre: str, rutas_modelos: list[str]) -> TipoRegistrado:
        """Añade modelos a un tipo existente y fusiona su esquema (conserva la fecha de registro)."""
        tipos = self.tipos()
        tipo = self._existente(tipos, nombre)
        modelos = _leer_modelos(rutas_modelos)
        tipo.esquema = reduce(fusionar, map(inferir_esquema, modelos), tipo.esquema)
        tipo.modelos_usados += len(modelos)
        self._almacen.guardar(tipos)
        return tipo

    def eliminar(self, nombre: str) -> None:
        """Borra el tipo o lanza :class:`ErrorGestor` si no existe."""
        tipos = self.tipos()
        self._existente(tipos, nombre)
        del tipos[nombre]
        self._almacen.guardar(tipos)

    @staticmethod
    def _existente(tipos: dict[str, TipoRegistrado], nombre: str) -> TipoRegistrado:
        if nombre not in tipos:
            raise ErrorGestor(f"el tipo '{nombre}' no existe")
        return tipos[nombre]
