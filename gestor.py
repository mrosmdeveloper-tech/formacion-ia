import sys
import os
import csv
import time

from gestor_json.config import (
    ARCHIVO_INCIDENCIAS,
    ARCHIVO_RESUMEN_ARCHIVOS,
    ARCHIVO_RESUMEN_LOTE,
    EXTENSION_JSON,
    MAX_INCIDENCIAS_POR_DEFECTO,
    TOP_RUTAS,
)
from gestor_json.almacenamiento import AlmacenEsquemasPropio, leer_json
from gestor_json.modelos import ErrorGestor, Incidencia
from gestor_json.registro import RegistroTipos, clasificar_archivo
from gestor_json.rutas import normalizar
from gestor_json.tipos_logicos import TipoLogico
from gestor_json.validacion import ValidadorPropio
import json


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
        d = registro.tipos()
        if os.path.isdir(ruta):
            arch = []
            for n in sorted(os.listdir(ruta)):
                if os.path.isfile(os.path.join(ruta, n)) and n.lower().endswith(EXTENSION_JSON):
                    arch.append(os.path.join(ruta, n))
        else:
            arch = [ruta]
        try:
            os.makedirs(sal, exist_ok=True)
            f1 = open(os.path.join(sal, ARCHIVO_INCIDENCIAS), "w", newline="", encoding="utf-8")
            w1 = csv.writer(f1)
            w1.writerow(["archivo", "tipo", "nivel", "categoria", "ruta", "esperado", "encontrado", "mensaje"])
            f2 = open(os.path.join(sal, ARCHIVO_RESUMEN_ARCHIVOS), "w", newline="", encoding="utf-8")
            w2 = csv.writer(f2)
            w2.writerow(["archivo", "tipo", "valido", "errores", "avisos"])
        except Exception as ex:
            print("Error: no se pueden crear los informes en " + sal + ": " + str(ex))
            sys.exit(2)
        tot = 0
        val = 0
        cerr = 0
        stip = 0
        por_tipo = {}
        for n in d:
            por_tipo[n] = 0
        cats = {}
        rutas = {}
        for p in arch:
            nom = os.path.basename(p)
            incidencias = []
            clasif = clasificar_archivo(nom, d)
            tipo = ""
            if clasif.tipo is None:
                incidencias.append(Incidencia.sin_tipo())
            else:
                tipo = clasif.tipo.nombre
                if clasif.ambigua:
                    incidencias.append(Incidencia.varios_tipos(tipo, clasif.candidatos))
                try:
                    doc = leer_json(p)
                    ok = True
                except Exception as ex:
                    incidencias.append(Incidencia.json_invalido(str(ex)))
                    ok = False
                if ok:
                    incidencias = incidencias + ValidadorPropio(clasif.tipo.esquema, est).validar(doc)
            if len(incidencias) > mx:
                aux = len(incidencias)
                incidencias = incidencias[:mx]
                incidencias.append(Incidencia.incidencias_truncadas(mx, aux))
            ne = 0
            na = 0
            for x in incidencias:
                if x.es_error:
                    ne = ne + 1
                else:
                    na = na + 1
                w1.writerow([nom, tipo, x.nivel, x.categoria, x.ruta, x.esperado, x.encontrado, x.mensaje])
                if x.categoria in cats:
                    cats[x.categoria] = cats[x.categoria] + 1
                else:
                    cats[x.categoria] = 1
                if tipo != "" and x.ruta != "":
                    r = normalizar(x.ruta)
                    if tipo not in rutas:
                        rutas[tipo] = {}
                    if r in rutas[tipo]:
                        rutas[tipo][r] = rutas[tipo][r] + 1
                    else:
                        rutas[tipo][r] = 1
            tot = tot + 1
            if tipo == "":
                stip = stip + 1
                w2.writerow([nom, "", "no", ne, na])
            else:
                por_tipo[tipo] = por_tipo[tipo] + 1
                if ne == 0:
                    val = val + 1
                    w2.writerow([nom, tipo, "si", ne, na])
                else:
                    cerr = cerr + 1
                    w2.writerow([nom, tipo, "no", ne, na])
        f1.close()
        f2.close()
        top = {}
        for t in d:
            if t in rutas:
                tmp = sorted(rutas[t].items(), key=lambda x: (-x[1], x[0]))
                top[t] = []
                for x in tmp[:TOP_RUTAS]:
                    top[t].append({"ruta": x[0], "incidencias": x[1]})
        aux = {}
        for c in sorted(cats):
            aux[c] = cats[c]
        seg = round(time.perf_counter() - t0, 3)
        res = {
            "archivos_totales": tot,
            "por_tipo": por_tipo,
            "validos": val,
            "con_errores": cerr,
            "sin_tipo": stip,
            "incidencias_por_categoria": aux,
            "rutas_mas_frecuentes": top,
            "tiempo_s": seg,
        }
        f = open(os.path.join(sal, ARCHIVO_RESUMEN_LOTE), "w", encoding="utf-8")
        json.dump(res, f, indent=2, ensure_ascii=False)
        f.close()
        print("Archivos procesados: " + str(tot))
        for t in por_tipo:
            print("  " + t + ": " + str(por_tipo[t]))
        print("  sin tipo: " + str(stip))
        print("Válidos: " + str(val) + "  Con errores: " + str(cerr) + "  Sin tipo: " + str(stip))
        n = 0
        for c in aux:
            n = n + aux[c]
        print("Incidencias: " + str(n))
        for c in aux:
            print("  " + c + ": " + str(aux[c]))
        print("Informes en: " + sal)
        print("Tiempo total: " + str(seg) + " s")
        if cerr > 0:
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
