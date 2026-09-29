"""Estructuras de datos del programa: esquemas, tipos registrados, incidencias y resultados."""

from __future__ import annotations

from dataclasses import dataclass, field

from gestor_json.config import Categoria, Nivel
from gestor_json.tipos_logicos import TipoLogico

RUTA_RAIZ = "$"


@dataclass
class NodoEsquema:
    """Esquema de un valor: tipos admitidos, si admite ``null`` y la estructura interna.

    ``tipos`` está siempre ordenado según la declaración de :class:`TipoLogico`. ``campos`` solo
    tiene sentido si admite objetos, e ``item`` (el esquema de los elementos) si admite listas.
    """

    tipos: tuple[TipoLogico, ...]
    admite_nulo: bool = False
    campos: dict[str, CampoEsquema] = field(default_factory=dict)
    item: NodoEsquema | None = None

    @property
    def acepta_cualquier_valor(self) -> bool:
        return TipoLogico.DESCONOCIDO in self.tipos

    def describir(self) -> str:
        """Texto legible de los tipos admitidos, por ejemplo ``"texto | nulo"``."""
        nombres = [tipo.value for tipo in self.tipos]
        if self.admite_nulo:
            nombres.append(TipoLogico.NULO.value)
        return " | ".join(nombres)


@dataclass
class CampoEsquema:
    """Campo de un objeto: si es obligatorio y el esquema de su valor."""

    obligatorio: bool
    esquema: NodoEsquema


@dataclass
class TipoRegistrado:
    """Tipo registrado por el usuario."""

    nombre: str
    patron: str
    modelos_usados: int
    registrado: str
    """Fecha y hora de registro en formato ISO, sin fracciones de segundo."""
    esquema: NodoEsquema


@dataclass(frozen=True)
class Incidencia:
    """Problema encontrado en un archivo, tal como aparece en ``incidencias.csv``."""

    nivel: str
    categoria: str
    ruta: str
    esperado: str
    encontrado: str
    mensaje: str

    @property
    def es_error(self) -> bool:
        return self.nivel == Nivel.ERROR

    @classmethod
    def json_invalido(cls, detalle: str) -> Incidencia:
        return cls(Nivel.ERROR, Categoria.JSON_INVALIDO, RUTA_RAIZ, "", "",
                   f"El archivo no es un JSON válido: {detalle}")

    @classmethod
    def falta_campo(cls, ruta: str, campo: str, esperado: str) -> Incidencia:
        return cls(Nivel.ERROR, Categoria.FALTA_CAMPO, ruta, esperado, "ausente",
                   f"Falta el campo obligatorio '{campo}'")

    @classmethod
    def campo_extra(cls, ruta: str, campo: str, encontrado: str, estricto: bool) -> Incidencia:
        nivel = Nivel.ERROR if estricto else Nivel.AVISO
        return cls(nivel, Categoria.CAMPO_EXTRA, ruta, "ausente", encontrado,
                   f"Campo no previsto en el esquema: '{campo}'")

    @classmethod
    def tipo_incorrecto(cls, ruta: str, esperado: str, encontrado: str) -> Incidencia:
        return cls(Nivel.ERROR, Categoria.TIPO_INCORRECTO, ruta, esperado, encontrado,
                   f"Tipo incorrecto: se esperaba {esperado} y se encontró {encontrado}")

    @classmethod
    def nulo_no_permitido(cls, ruta: str, esperado: str) -> Incidencia:
        return cls(Nivel.ERROR, Categoria.NULO_NO_PERMITIDO, ruta, esperado,
                   TipoLogico.NULO.value, f"Valor nulo no permitido: se esperaba {esperado}")

    @classmethod
    def varios_tipos(cls, elegido: str, candidatos: list[str]) -> Incidencia:
        lista = ", ".join(candidatos)
        return cls(Nivel.AVISO, Categoria.VARIOS_TIPOS, "", elegido, lista,
                   f"El nombre encaja con varios patrones ({lista}); se usa '{elegido}'")

    @classmethod
    def sin_tipo(cls) -> Incidencia:
        return cls(Nivel.AVISO, Categoria.SIN_TIPO, "", "", "",
                   "El nombre del archivo no encaja con ningún patrón registrado")

    @classmethod
    def incidencias_truncadas(cls, maximo: int, total: int) -> Incidencia:
        return cls(Nivel.AVISO, Categoria.INCIDENCIAS_TRUNCADAS, "", str(maximo), str(total),
                   f"Se han encontrado {total} incidencias; solo se incluyen las primeras {maximo}")


@dataclass
class ResultadoArchivo:
    """Resultado de validar un archivo. ``tipo`` es ``""`` si no encaja con ningún patrón."""

    archivo: str
    tipo: str
    incidencias: list[Incidencia]

    @property
    def errores(self) -> int:
        return sum(1 for incidencia in self.incidencias if incidencia.es_error)

    @property
    def avisos(self) -> int:
        return len(self.incidencias) - self.errores

    @property
    def tiene_tipo(self) -> bool:
        return self.tipo != ""

    @property
    def valido(self) -> bool:
        """Válido si se ha validado contra un tipo y no tiene errores."""
        return self.tiene_tipo and self.errores == 0
