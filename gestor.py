import sys
import os
import json
from datetime import datetime


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


def main():
    if len(sys.argv) < 2:
        print("Uso: python gestor.py <comando> [opciones]")
        print("Comandos: registrar")
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
        if os.path.exists("esquemas.json"):
            try:
                f = open("esquemas.json", encoding="utf-8-sig")
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
        f = open("esquemas.json", "w", encoding="utf-8")
        json.dump(d, f, indent=2, ensure_ascii=False)
        f.close()
        print("Tipo '" + tipo + "' registrado con " + str(len(mods)) + " modelo(s) (patrón: " + pat + ")")
    else:
        print("Error: comando desconocido: " + cmd)
        sys.exit(2)


if __name__ == "__main__":
    main()
