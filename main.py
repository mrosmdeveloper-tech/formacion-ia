"""Punto de entrada del gestor de tipos JSON: ``python main.py <comando> [opciones]``."""

import sys

from gestor_json.cli import main

if __name__ == "__main__":
    sys.exit(main())
