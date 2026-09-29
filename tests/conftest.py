"""Fixtures comunes de los tests."""

import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

import gestor_json.cli
import gestor_json.registro

DATOS = Path(__file__).parent / "datos"
EJEMPLOS = Path(__file__).parent.parent / "datos" / "ejemplos"


class _FechaFija:
    @staticmethod
    def now():
        return datetime(2026, 9, 29, 10, 0, 0)


@pytest.fixture
def ejecutar(tmp_path, monkeypatch, capsys):
    """Ejecuta la CLI en una carpeta temporal y devuelve (código, salida).

    Fija la fecha de registro y el cronómetro para que los resultados sean deterministas. Usa el
    formato por defecto del programa (JSON Schema) salvo que se pase ``--formato``.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(gestor_json.registro, "datetime", _FechaFija)
    monkeypatch.setattr(gestor_json.cli, "time", SimpleNamespace(perf_counter=lambda: 0.0))

    def cli(*args):
        argv = [str(a) for a in args]
        monkeypatch.setattr(sys, "argv", ["main.py", *argv])
        codigo = gestor_json.cli.main(argv)
        return codigo, capsys.readouterr().out

    return cli
