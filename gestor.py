import sys
import os
import time

from gestor_json.almacenamiento import AlmacenEsquemasPropio
from gestor_json.config import MAX_INCIDENCIAS_POR_DEFECTO
from gestor_json.informes import EscritorInformes, escribir_resumen_lote, imprimir_resumen
from gestor_json.lote import ResumenLote, ValidadorLote, listar_archivos
from gestor_json.modelos import ErrorGestor
from gestor_json.registro import RegistroTipos
from gestor_json.tipos_logicos import TipoLogico


def imprimir(e, nombre, nivel):
    print("  " * nivel + nombre + ": " + e.describir())
    if TipoLogico.OBJETO in e.tipos:
        for k in e.campos:
            if e.campos[k].obligatorio:
                imprimir(e.campos[k].esquema, k, nivel + 1)
            else:
                imprimir(e.campos[k].esquema, k + " (opcional)", nivel + 1)
    if TipoLogico.LISTA in e.tipos:
        imprimir(e.item, "[]", nivel + 1)


def main():
    try:
        comando()
    except ErrorGestor as ex:
        print("Error: " + str(ex))
        sys.exit(2)


def comando():
    registro = RegistroTipos(AlmacenEsquemasPropio())
    if len(sys.argv) < 2:
        print("Uso: python gestor.py <comando> [opciones]")
        print("Comandos: registrar, actualizar, tipos, mostrar, eliminar, validar")
        sys.exit(2)
    cmd = sys.argv[1]
    args = sys.argv[2:]
    if cmd == "registrar":
        tipo = None
        pat = None
        mods = []
        i = 0
        while i < len(args):
            if args[i] == "--tipo" and i + 1 < len(args):
                tipo = args[i + 1]
                i = i + 2
            elif args[i] == "--patron" and i + 1 < len(args):
                pat = args[i + 1]
                i = i + 2
            elif args[i] == "--modelo" and i + 1 < len(args):
                mods.append(args[i + 1])
                i = i + 2
            else:
                print("Error: argumento no reconocido: " + args[i])
                sys.exit(2)
        if tipo is None or tipo.strip() == "":
            print("Error: falta --tipo")
            sys.exit(2)
        if pat is None or pat.strip() == "":
            print("Error: el patrón no puede estar vacío")
            sys.exit(2)
        if len(mods) == 0:
            print("Error: hay que indicar al menos un --modelo")
            sys.exit(2)
        registro.registrar(tipo, pat, mods)
        print("Tipo '" + tipo + "' registrado con " + str(len(mods)) + " modelo(s) (patrón: " + pat + ")")
    elif cmd == "actualizar":
        tipo = None
        mods = []
        i = 0
        while i < len(args):
            if args[i] == "--tipo" and i + 1 < len(args):
                tipo = args[i + 1]
                i = i + 2
            elif args[i] == "--modelo" and i + 1 < len(args):
                mods.append(args[i + 1])
                i = i + 2
            else:
                print("Error: argumento no reconocido: " + args[i])
                sys.exit(2)
        if tipo is None:
            print("Error: falta --tipo")
            sys.exit(2)
        if len(mods) == 0:
            print("Error: hay que indicar al menos un --modelo")
            sys.exit(2)
        t = registro.actualizar(tipo, mods)
        print("Tipo '" + tipo + "' actualizado: " + str(t.modelos_usados) + " modelo(s) en total")
    elif cmd == "tipos":
        if len(args) > 0:
            print("Error: argumento no reconocido: " + args[0])
            sys.exit(2)
        d = registro.tipos()
        if len(d) == 0:
            print("No hay tipos registrados")
        else:
            print("TIPO".ljust(20) + "PATRÓN".ljust(22) + "MODELOS".rjust(7) + "  REGISTRADO")
            for n in d:
                print(n.ljust(20) + d[n].patron.ljust(22) + str(d[n].modelos_usados).rjust(7) + "  " + d[n].registrado)
    elif cmd == "mostrar":
        tipo = None
        i = 0
        while i < len(args):
            if args[i] == "--tipo" and i + 1 < len(args):
                tipo = args[i + 1]
                i = i + 2
            else:
                print("Error: argumento no reconocido: " + args[i])
                sys.exit(2)
        if tipo is None:
            print("Error: falta --tipo")
            sys.exit(2)
        t = registro.obtener(tipo)
        print("Tipo: " + tipo)
        print("Patrón: " + t.patron)
        print("Modelos usados: " + str(t.modelos_usados))
        print("Registrado: " + t.registrado)
        print("Esquema:")
        imprimir(t.esquema, "$", 0)
    elif cmd == "eliminar":
        tipo = None
        i = 0
        while i < len(args):
            if args[i] == "--tipo" and i + 1 < len(args):
                tipo = args[i + 1]
                i = i + 2
            else:
                print("Error: argumento no reconocido: " + args[i])
                sys.exit(2)
        if tipo is None:
            print("Error: falta --tipo")
            sys.exit(2)
        registro.eliminar(tipo)
        print("Tipo '" + tipo + "' eliminado")
    elif cmd == "validar":
        ruta = None
        sal = None
        est = False
        mx = MAX_INCIDENCIAS_POR_DEFECTO
        i = 0
        while i < len(args):
            if args[i] == "--salida" and i + 1 < len(args):
                sal = args[i + 1]
                i = i + 2
            elif args[i] == "--estricto":
                est = True
                i = i + 1
            elif args[i] == "--max-incidencias" and i + 1 < len(args):
                try:
                    mx = int(args[i + 1])
                except ValueError:
                    print("Error: --max-incidencias debe ser un número entero")
                    sys.exit(2)
                if mx < 1:
                    print("Error: --max-incidencias debe ser al menos 1")
                    sys.exit(2)
                i = i + 2
            elif args[i].startswith("--"):
                print("Error: argumento no reconocido: " + args[i])
                sys.exit(2)
            elif ruta is None:
                ruta = args[i]
                i = i + 1
            else:
                print("Error: argumento no reconocido: " + args[i])
                sys.exit(2)
        if ruta is None:
            print("Error: falta el archivo o la carpeta a validar")
            sys.exit(2)
        if sal is None:
            print("Error: falta --salida")
            sys.exit(2)
        if not os.path.exists(ruta):
            print("Error: no existe " + ruta)
            sys.exit(2)
        t0 = time.perf_counter()
        tipos = registro.tipos()
        archivos = listar_archivos(ruta)
        try:
            informes = EscritorInformes(sal)
        except Exception as ex:
            print("Error: no se pueden crear los informes en " + sal + ": " + str(ex))
            sys.exit(2)
        validador = ValidadorLote(tipos, est, mx)
        resumen = ResumenLote.para(tipos)
        with informes:
            for archivo in archivos:
                resultado = validador.validar_archivo(archivo)
                informes.escribir(resultado)
                resumen.agregar(resultado)
        seg = round(time.perf_counter() - t0, 3)
        escribir_resumen_lote(sal, resumen, seg)
        imprimir_resumen(sal, resumen, seg)
        if resumen.con_errores > 0:
            sys.exit(1)
        sys.exit(0)
    else:
        print("Error: comando desconocido: " + cmd)
        sys.exit(2)


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        print("Error inesperado: " + str(ex))
        sys.exit(2)
