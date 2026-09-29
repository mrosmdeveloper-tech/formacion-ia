import sys
import os
import json
import fnmatch
import re
import csv
import time
from datetime import datetime

from gestor_json.config import (
    ARCHIVO_ESQUEMAS,
    ARCHIVO_INCIDENCIAS,
    ARCHIVO_RESUMEN_ARCHIVOS,
    ARCHIVO_RESUMEN_LOTE,
    EXTENSION_JSON,
    MAX_INCIDENCIAS_POR_DEFECTO,
    TOP_RUTAS,
    Categoria,
    Nivel,
)
from gestor_json.tipos_logicos import TipoLogico

# Códigos de tipo del formato propio de esquemas.json
CODIGOS = {
    "bool": TipoLogico.BOOLEANO,
    "list": TipoLogico.LISTA,
    "num": TipoLogico.NUMERO,
    "obj": TipoLogico.OBJETO,
    "str": TipoLogico.TEXTO,
    "unk": TipoLogico.DESCONOCIDO,
}

incidencias = []


def inferir(v):
    if v is None:
        return {"t": "unk", "nulo": True}
    if type(v) == bool:
        return {"t": "bool", "nulo": False}
    if type(v) == int or type(v) == float:
        return {"t": "num", "nulo": False}
    if type(v) == str:
        return {"t": "str", "nulo": False}
    if type(v) == dict:
        r = {"t": "obj", "nulo": False, "campos": {}}
        for k in v:
            r["campos"][k] = {"req": True, "esq": inferir(v[k])}
        return r
    if type(v) == list:
        r = {"t": "list", "nulo": False, "item": {"t": "unk", "nulo": False}}
        if len(v) > 0:
            tmp = inferir(v[0])
            for i in range(1, len(v)):
                tmp = fusionar(tmp, inferir(v[i]))
            r["item"] = tmp
        return r
    return {"t": "unk", "nulo": False}


def fusionar(a, b):
    if type(a["t"]) == list:
        ta = a["t"]
    else:
        ta = [a["t"]]
    if type(b["t"]) == list:
        tb = b["t"]
    else:
        tb = [b["t"]]
    tt = []
    for x in ta:
        if x not in tt:
            tt.append(x)
    for x in tb:
        if x not in tt:
            tt.append(x)
    if "unk" in tt and len(tt) > 1:
        tt.remove("unk")
    tt.sort()
    r = {"t": None, "nulo": a["nulo"] or b["nulo"]}
    if len(tt) == 1:
        r["t"] = tt[0]
    else:
        r["t"] = tt
    if "obj" in tt:
        if "obj" in ta and "obj" in tb:
            aux = {}
            for k in a["campos"]:
                if k in b["campos"]:
                    aux[k] = {
                        "req": a["campos"][k]["req"] and b["campos"][k]["req"],
                        "esq": fusionar(a["campos"][k]["esq"], b["campos"][k]["esq"]),
                    }
                else:
                    aux[k] = {"req": False, "esq": a["campos"][k]["esq"]}
            for k in b["campos"]:
                if k not in a["campos"]:
                    aux[k] = {"req": False, "esq": b["campos"][k]["esq"]}
            r["campos"] = aux
        else:
            if "obj" in ta:
                r["campos"] = a["campos"]
            else:
                r["campos"] = b["campos"]
    if "list" in tt:
        if "list" in ta and "list" in tb:
            r["item"] = fusionar(a["item"], b["item"])
        else:
            if "list" in ta:
                r["item"] = a["item"]
            else:
                r["item"] = b["item"]
    return r


def desc(e):
    if type(e["t"]) == list:
        tt = e["t"]
    else:
        tt = [e["t"]]
    s = ""
    for x in tt:
        n = CODIGOS[x].value
        if s != "":
            s = s + " | "
        s = s + n
    if e["nulo"]:
        s = s + " | nulo"
    return s


def imprimir(e, nombre, nivel):
    print("  " * nivel + nombre + ": " + desc(e))
    if type(e["t"]) == list:
        tt = e["t"]
    else:
        tt = [e["t"]]
    if "obj" in tt:
        for k in e["campos"]:
            if e["campos"][k]["req"]:
                imprimir(e["campos"][k]["esq"], k, nivel + 1)
            else:
                imprimir(e["campos"][k]["esq"], k + " (opcional)", nivel + 1)
    if "list" in tt:
        imprimir(e["item"], "[]", nivel + 1)


def validar(v, e, ruta, est):
    global incidencias
    if type(e["t"]) == list:
        tt = e["t"]
    else:
        tt = [e["t"]]
    if "unk" in tt:
        return
    if v is None:
        if e["nulo"] == False:
            incidencias.append({
                "nivel": Nivel.ERROR,
                "categoria": Categoria.NULO_NO_PERMITIDO,
                "ruta": ruta,
                "esperado": desc(e),
                "encontrado": "nulo",
                "mensaje": "Valor nulo no permitido: se esperaba " + desc(e),
            })
        return
    if type(v) == bool:
        tv = "bool"
    elif type(v) == int or type(v) == float:
        tv = "num"
    elif type(v) == str:
        tv = "str"
    elif type(v) == dict:
        tv = "obj"
    elif type(v) == list:
        tv = "list"
    else:
        tv = "unk"
    if tv not in tt:
        incidencias.append({
            "nivel": Nivel.ERROR,
            "categoria": Categoria.TIPO_INCORRECTO,
            "ruta": ruta,
            "esperado": desc(e),
            "encontrado": desc({"t": tv, "nulo": False}),
            "mensaje": "Tipo incorrecto: se esperaba " + desc(e) + " y se encontró " + desc({"t": tv, "nulo": False}),
        })
        return
    if tv == "obj":
        for k in e["campos"]:
            if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", k):
                r = ruta + "." + k
            else:
                r = ruta + "[" + json.dumps(k, ensure_ascii=False) + "]"
            if k in v:
                validar(v[k], e["campos"][k]["esq"], r, est)
            else:
                if e["campos"][k]["req"]:
                    incidencias.append({
                        "nivel": Nivel.ERROR,
                        "categoria": Categoria.FALTA_CAMPO,
                        "ruta": r,
                        "esperado": desc(e["campos"][k]["esq"]),
                        "encontrado": "ausente",
                        "mensaje": "Falta el campo obligatorio '" + k + "'",
                    })
        for k in v:
            if k not in e["campos"]:
                if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", k):
                    r = ruta + "." + k
                else:
                    r = ruta + "[" + json.dumps(k, ensure_ascii=False) + "]"
                if v[k] is None:
                    aux = "nulo"
                elif type(v[k]) == bool:
                    aux = "booleano"
                elif type(v[k]) == int or type(v[k]) == float:
                    aux = "numero"
                elif type(v[k]) == str:
                    aux = "texto"
                elif type(v[k]) == dict:
                    aux = "objeto"
                else:
                    aux = "lista"
                if est:
                    tmp = Nivel.ERROR
                else:
                    tmp = Nivel.AVISO
                incidencias.append({
                    "nivel": tmp,
                    "categoria": Categoria.CAMPO_EXTRA,
                    "ruta": r,
                    "esperado": "ausente",
                    "encontrado": aux,
                    "mensaje": "Campo no previsto en el esquema: '" + k + "'",
                })
    if tv == "list":
        for i in range(len(v)):
            validar(v[i], e["item"], ruta + "[" + str(i) + "]", est)


def clave_orden(x):
    aux = []
    for m in re.finditer(r'\.([A-Za-z_][A-Za-z0-9_]*)|\[(\d+)\]|\[("(?:[^"\\]|\\.)*")\]', x["ruta"]):
        if m.group(1) is not None:
            aux.append((0, m.group(1)))
        elif m.group(2) is not None:
            aux.append((1, int(m.group(2))))
        else:
            aux.append((0, json.loads(m.group(3))))
    return aux


def main():
    global incidencias
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
        if os.path.exists(ARCHIVO_ESQUEMAS):
            try:
                f = open(ARCHIVO_ESQUEMAS, encoding="utf-8-sig")
                d = json.load(f)
                f.close()
            except Exception as ex:
                print("Error: no se puede leer esquemas.json: " + str(ex))
                sys.exit(2)
        else:
            d = {"tipos": {}}
        if tipo in d["tipos"]:
            print("Error: el tipo '" + tipo + "' ya existe")
            sys.exit(2)
        e = None
        for m in mods:
            try:
                f = open(m, encoding="utf-8-sig")
                v = json.load(f)
                f.close()
            except Exception as ex:
                print("Error: no se puede leer el modelo " + m + ": " + str(ex))
                sys.exit(2)
            if e is None:
                e = inferir(v)
            else:
                e = fusionar(e, inferir(v))
        d["tipos"][tipo] = {
            "patron": pat,
            "modelos_usados": len(mods),
            "registrado": datetime.now().isoformat(timespec="seconds"),
            "esquema": e,
        }
        f = open(ARCHIVO_ESQUEMAS, "w", encoding="utf-8")
        json.dump(d, f, indent=2, ensure_ascii=False)
        f.close()
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
        if os.path.exists(ARCHIVO_ESQUEMAS):
            try:
                f = open(ARCHIVO_ESQUEMAS, encoding="utf-8-sig")
                d = json.load(f)
                f.close()
            except Exception as ex:
                print("Error: no se puede leer esquemas.json: " + str(ex))
                sys.exit(2)
        else:
            d = {"tipos": {}}
        if tipo not in d["tipos"]:
            print("Error: el tipo '" + tipo + "' no existe")
            sys.exit(2)
        e = d["tipos"][tipo]["esquema"]
        for m in mods:
            try:
                f = open(m, encoding="utf-8-sig")
                v = json.load(f)
                f.close()
            except Exception as ex:
                print("Error: no se puede leer el modelo " + m + ": " + str(ex))
                sys.exit(2)
            e = fusionar(e, inferir(v))
        d["tipos"][tipo]["esquema"] = e
        d["tipos"][tipo]["modelos_usados"] = d["tipos"][tipo]["modelos_usados"] + len(mods)
        f = open(ARCHIVO_ESQUEMAS, "w", encoding="utf-8")
        json.dump(d, f, indent=2, ensure_ascii=False)
        f.close()
        print("Tipo '" + tipo + "' actualizado: " + str(d["tipos"][tipo]["modelos_usados"]) + " modelo(s) en total")
    elif cmd == "tipos":
        if len(args) > 0:
            print("Error: argumento no reconocido: " + args[0])
            sys.exit(2)
        if os.path.exists(ARCHIVO_ESQUEMAS):
            try:
                f = open(ARCHIVO_ESQUEMAS, encoding="utf-8-sig")
                d = json.load(f)
                f.close()
            except Exception as ex:
                print("Error: no se puede leer esquemas.json: " + str(ex))
                sys.exit(2)
        else:
            d = {"tipos": {}}
        if len(d["tipos"]) == 0:
            print("No hay tipos registrados")
        else:
            print("TIPO".ljust(20) + "PATRÓN".ljust(22) + "MODELOS".rjust(7) + "  REGISTRADO")
            for n in d["tipos"]:
                tmp = d["tipos"][n]
                print(n.ljust(20) + tmp["patron"].ljust(22) + str(tmp["modelos_usados"]).rjust(7) + "  " + tmp["registrado"])
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
        if os.path.exists(ARCHIVO_ESQUEMAS):
            try:
                f = open(ARCHIVO_ESQUEMAS, encoding="utf-8-sig")
                d = json.load(f)
                f.close()
            except Exception as ex:
                print("Error: no se puede leer esquemas.json: " + str(ex))
                sys.exit(2)
        else:
            d = {"tipos": {}}
        if tipo not in d["tipos"]:
            print("Error: el tipo '" + tipo + "' no existe")
            sys.exit(2)
        print("Tipo: " + tipo)
        print("Patrón: " + d["tipos"][tipo]["patron"])
        print("Modelos usados: " + str(d["tipos"][tipo]["modelos_usados"]))
        print("Registrado: " + d["tipos"][tipo]["registrado"])
        print("Esquema:")
        imprimir(d["tipos"][tipo]["esquema"], "$", 0)
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
        if os.path.exists(ARCHIVO_ESQUEMAS):
            try:
                f = open(ARCHIVO_ESQUEMAS, encoding="utf-8-sig")
                d = json.load(f)
                f.close()
            except Exception as ex:
                print("Error: no se puede leer esquemas.json: " + str(ex))
                sys.exit(2)
        else:
            d = {"tipos": {}}
        if tipo not in d["tipos"]:
            print("Error: el tipo '" + tipo + "' no existe")
            sys.exit(2)
        del d["tipos"][tipo]
        f = open(ARCHIVO_ESQUEMAS, "w", encoding="utf-8")
        json.dump(d, f, indent=2, ensure_ascii=False)
        f.close()
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
        if os.path.exists(ARCHIVO_ESQUEMAS):
            try:
                f = open(ARCHIVO_ESQUEMAS, encoding="utf-8-sig")
                d = json.load(f)
                f.close()
            except Exception as ex:
                print("Error: no se puede leer esquemas.json: " + str(ex))
                sys.exit(2)
        else:
            d = {"tipos": {}}
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
        for n in d["tipos"]:
            por_tipo[n] = 0
        cats = {}
        rutas = {}
        for p in arch:
            nom = os.path.basename(p)
            incidencias = []
            cands = []
            for n in d["tipos"]:
                if fnmatch.fnmatchcase(nom, d["tipos"][n]["patron"]):
                    cands.append(n)
            tipo = ""
            if len(cands) == 0:
                incidencias.append({
                    "nivel": Nivel.AVISO,
                    "categoria": Categoria.SIN_TIPO,
                    "ruta": "",
                    "esperado": "",
                    "encontrado": "",
                    "mensaje": "El nombre del archivo no encaja con ningún patrón registrado",
                })
            else:
                tipo = cands[0]
                if len(cands) > 1:
                    best = -1
                    for c in cands:
                        lit = 0
                        for ch in d["tipos"][c]["patron"]:
                            if ch != "*" and ch != "?":
                                lit = lit + 1
                        if lit > best:
                            best = lit
                            tipo = c
                    incidencias.append({
                        "nivel": Nivel.AVISO,
                        "categoria": Categoria.VARIOS_TIPOS,
                        "ruta": "",
                        "esperado": tipo,
                        "encontrado": ", ".join(cands),
                        "mensaje": "El nombre encaja con varios patrones (" + ", ".join(cands) + "); se usa '" + tipo + "'",
                    })
                try:
                    f = open(p, encoding="utf-8-sig")
                    doc = json.load(f)
                    f.close()
                    ok = True
                except Exception as ex:
                    incidencias.append({
                        "nivel": Nivel.ERROR,
                        "categoria": Categoria.JSON_INVALIDO,
                        "ruta": "$",
                        "esperado": "",
                        "encontrado": "",
                        "mensaje": "El archivo no es un JSON válido: " + str(ex),
                    })
                    ok = False
                if ok:
                    aux = len(incidencias)
                    validar(doc, d["tipos"][tipo]["esquema"], "$", est)
                    tmp = incidencias[aux:]
                    tmp.sort(key=clave_orden)
                    incidencias = incidencias[:aux] + tmp
            if len(incidencias) > mx:
                aux = len(incidencias)
                incidencias = incidencias[:mx]
                incidencias.append({
                    "nivel": Nivel.AVISO,
                    "categoria": Categoria.INCIDENCIAS_TRUNCADAS,
                    "ruta": "",
                    "esperado": str(mx),
                    "encontrado": str(aux),
                    "mensaje": "Se han encontrado " + str(aux) + " incidencias; solo se incluyen las primeras " + str(mx),
                })
            ne = 0
            na = 0
            for x in incidencias:
                if x["nivel"] == Nivel.ERROR:
                    ne = ne + 1
                else:
                    na = na + 1
                w1.writerow([nom, tipo, x["nivel"], x["categoria"], x["ruta"], x["esperado"], x["encontrado"], x["mensaje"]])
                if x["categoria"] in cats:
                    cats[x["categoria"]] = cats[x["categoria"]] + 1
                else:
                    cats[x["categoria"]] = 1
                if tipo != "" and x["ruta"] != "":
                    r = re.sub(r"\[\d+\]", "[*]", x["ruta"])
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
        for t in d["tipos"]:
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
