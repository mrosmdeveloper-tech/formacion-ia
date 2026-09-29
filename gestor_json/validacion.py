"""Validación de documentos contra el esquema de su tipo."""

from __future__ import annotations

from typing import Any, Callable, Protocol

from gestor_json.modelos import Incidencia, NodoEsquema, TipoRegistrado
from gestor_json.rutas import RUTA_RAIZ, clave_orden, ruta_campo, ruta_elemento
from gestor_json.tipos_logicos import TipoLogico, clasificar_valor


class Validador(Protocol):
    """Valida documentos de un tipo. Aísla al resto del programa del formato del esquema."""

    def validar(self, documento: Any) -> list[Incidencia]:
        """Devuelve las incidencias del documento, ordenadas por ruta (vacía si es válido)."""
        ...


class ValidadorPropio:
    """Validador del formato de esquema propio (:class:`NodoEsquema`)."""

    def __init__(self, esquema: NodoEsquema, estricto: bool = False) -> None:
        """``estricto``: los campos no previstos cuentan como error en lugar de como aviso."""
        self._esquema = esquema
        self._estricto = estricto

    def validar(self, documento: Any) -> list[Incidencia]:
        """Valida el documento completo desde la raíz (``$``)."""
        incidencias: list[Incidencia] = []
        self._validar_valor(documento, self._esquema, RUTA_RAIZ, incidencias)
        return sorted(incidencias, key=lambda incidencia: clave_orden(incidencia.ruta))

    def _validar_valor(self, valor: Any, esquema: NodoEsquema, ruta: str,
                       incidencias: list[Incidencia]) -> None:
        if esquema.acepta_cualquier_valor:
            return
        tipo = clasificar_valor(valor)
        if tipo is TipoLogico.NULO:
            if not esquema.admite_nulo:
                incidencias.append(Incidencia.nulo_no_permitido(ruta, esquema.describir()))
        elif tipo not in esquema.tipos:
            incidencias.append(Incidencia.tipo_incorrecto(ruta, esquema.describir(), tipo.value))
        elif tipo is TipoLogico.OBJETO:
            self._validar_objeto(valor, esquema, ruta, incidencias)
        elif tipo is TipoLogico.LISTA:
            for posicion, elemento in enumerate(valor):
                self._validar_valor(elemento, esquema.elementos, ruta_elemento(ruta, posicion),
                                    incidencias)

    def _validar_objeto(self, objeto: dict[str, Any], esquema: NodoEsquema, ruta: str,
                        incidencias: list[Incidencia]) -> None:
        for clave, campo in esquema.campos.items():
            ruta_hijo = ruta_campo(ruta, clave)
            if clave in objeto:
                self._validar_valor(objeto[clave], campo.esquema, ruta_hijo, incidencias)
            elif campo.obligatorio:
                incidencias.append(
                    Incidencia.falta_campo(ruta_hijo, clave, campo.esquema.describir()))
        for clave, valor in objeto.items():
            if clave not in esquema.campos:
                incidencias.append(Incidencia.campo_extra(
                    ruta_campo(ruta, clave), clave, clasificar_valor(valor).value,
                    self._estricto))


FabricaValidador = Callable[[TipoRegistrado, bool], Validador]
"""Crea el validador de un tipo: recibe el tipo y si la validación es estricta."""


def crear_validador_propio(tipo: TipoRegistrado, estricto: bool) -> Validador:
    """Fábrica de validadores del formato propio (la que se usa por defecto)."""
    return ValidadorPropio(tipo.esquema, estricto)
