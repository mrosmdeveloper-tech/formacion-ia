"""Envoltorio temporal: el programa está en ``gestor_json``; el punto de entrada es ``main.py``."""

import sys

from gestor_json.cli import main as _main


def main():
    sys.exit(_main(sys.argv[1:]))


if __name__ == "__main__":
    main()
