"""Generador de datos sintéticos para el gestor de tipos JSON.

Genera en la carpeta de salida:

- ``modelos/``: tres modelos válidos por tipo, que se diferencian en los campos
  opcionales y en algún campo que es ``null`` en unos y tiene valor en otros.
- ``entrada/``: los archivos a validar, repartidos entre los tipos, con un
  pequeño porcentaje de archivos sin tipo.

Todos los datos son inventados. La generación es reproducible (``--semilla``) y
se escribe archivo a archivo, sin acumular el lote en memoria.

Uso::

    python scripts/generar_datos.py --archivos 1000 --salida datos/generados/lote_1000 \
        --semilla 42 --tasa-errores 0.1
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

FECHA_BASE = datetime(2026, 1, 1)
MINUTOS_EN_UN_ANIO = 365 * 24 * 60
PROPORCION_SIN_TIPO = 0.03
PREFIJOS_SIN_TIPO = ("informe", "exportacion", "copia")

NOMBRES = (
    "Lucía", "Hugo", "Martina", "Mateo", "Sofía", "Leo", "Valeria", "Daniel",
    "Paula", "Pablo", "Julia", "Álvaro", "Carmen", "Adrián", "Irene", "Marcos",
)
APELLIDOS = (
    "García", "Martínez", "López", "Sánchez", "Pérez", "Gómez", "Fernández",
    "Ruiz", "Díaz", "Moreno", "Álvarez", "Romero", "Navarro", "Torres",
)
CALLES = (
    "Calle Mayor", "Avenida de la Constitución", "Calle del Sol", "Paseo de la Estación",
    "Calle Real", "Plaza Nueva", "Calle de la Luna", "Ronda Norte",
)
CIUDADES = (
    ("Madrid", "28"), ("Barcelona", "08"), ("Valencia", "46"), ("Sevilla", "41"),
    ("Zaragoza", "50"), ("Bilbao", "48"), ("Málaga", "29"), ("Valladolid", "47"),
)
PRODUCTOS = (
    "Taza de cerámica", "Cuaderno A5", "Bolígrafo azul", "Lámpara de escritorio",
    "Mochila urbana", "Botella térmica", "Auriculares", "Cargador USB",
    "Funda de móvil", "Alfombrilla", "Teclado inalámbrico", "Ratón óptico",
)
ACABADOS = ("negro", "blanco", "gris", "azul marino", "verde oliva", "edición limitada")
ETIQUETAS = ("urgente", "regalo", "fragil", "recogida", "internacional", "cliente_vip")
NOTAS = (
    "Entregar por la tarde", "Dejar en conserjería", "Llamar antes de subir",
    "Envolver para regalo", "",
)

MAGNITUDES = (
    ("temperatura", "°C", -5.0, 40.0),
    ("humedad", "%", 10.0, 95.0),
    ("presion", "hPa", 980.0, 1040.0),
    ("co2", "ppm", 380.0, 2000.0),
    ("luz", "lux", 0.0, 1200.0),
)
ALERTAS = ("bateria_baja", "temperatura_alta", "sin_conexion", "calibracion_pendiente")

# Deporte → (velocidad mínima, velocidad máxima en km/h, segundos entre puntos, fc base)
DEPORTES = {
    "carrera": (8.0, 14.0, (1, 3), 150),
    "ciclismo": (18.0, 32.0, (1, 2), 135),
    "senderismo": (3.0, 5.5, (3, 6), 115),
}
PENDIENTES = {"subida": (0.03, 0.09), "llano": (-0.01, 0.01), "bajada": (-0.09, -0.03)}
PUNTOS_DE_SALIDA = (
    (40.4168, -3.7038), (41.3874, 2.1686), (39.4699, -0.3763), (37.3891, -5.9845),
    (43.2630, -2.9350), (42.8125, -1.6458), (40.9701, -5.6635), (42.8782, -8.5448),
)
NOMBRES_TRAMO = ("Salida", "Collado", "Ribera", "Pinar", "Mirador", "Puente", "Vega", "Llegada")
ALIAS = ("trotamundos", "pedalero", "montanera", "liebre", "senderista", "cumbrera", "rodador")
MODELOS_DISPOSITIVO = ("Rastreador GX-2", "Pulsera Trek 5", "Ciclocomputador C300", "Reloj Sendero S")
SENSORES_EXTRA = ("barometro", "potencia", "brujula")
UMBRALES_ZONAS_FC = (115, 135, 155, 170)  # límite superior de las zonas 1 a 4
RADIO_TIERRA_M = 6_371_000.0
METROS_POR_GRADO = 111_320.0


@dataclass(frozen=True)
class TipoDocumento:
    """Tipo de documento que sabe generar el script."""

    nombre: str
    prefijo: str
    peso: float
    generar: Callable[..., dict[str, Any]]
    generar_modelos: Callable[[random.Random], list[dict[str, Any]]]


@dataclass
class Estadisticas:
    """Recuento de lo generado, para el resumen final."""

    por_tipo: Counter
    total_bytes: int = 0


# --------------------------------------------------------------------------- utilidades

def _decidir(rng: random.Random, forzado: bool | None, probabilidad: float) -> bool:
    """Devuelve ``forzado`` si se indica; si no, decide al azar con la probabilidad dada."""
    return forzado if forzado is not None else rng.random() < probabilidad


def _sin_acentos(texto: str) -> str:
    normalizado = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in normalizado if not unicodedata.combining(c))


def _fecha_aleatoria(rng: random.Random) -> str:
    return (FECHA_BASE + timedelta(minutes=rng.randint(0, MINUTOS_EN_UN_ANIO))).isoformat()


# --------------------------------------------------------------------------- pedido

def generar_pedido(
    rng: random.Random,
    indice: int,
    *,
    pequeno: bool = False,
    con_telefono: bool | None = None,
    con_descuento: bool | None = None,
    con_notas: bool | None = None,
    con_etiquetas: bool | None = None,
) -> dict[str, Any]:
    """Genera un pedido de una tienda online."""
    nombre = f"{rng.choice(NOMBRES)} {rng.choice(APELLIDOS)}"
    ciudad, prefijo_cp = rng.choice(CIUDADES)
    cliente: dict[str, Any] = {
        "id": f"CLI-{rng.randint(1, 99999):05d}",
        "nombre": nombre,
        "email": _sin_acentos(nombre).lower().replace(" ", ".") + "@correo.example",
    }
    if _decidir(rng, con_telefono, 0.6):
        cliente["telefono"] = f"6{rng.randint(10_000_000, 99_999_999)}"
    cliente["direccion"] = {
        "calle": f"{rng.choice(CALLES)}, {rng.randint(1, 150)}",
        "cp": f"{prefijo_cp}{rng.randint(1, 999):03d}",
        "ciudad": ciudad,
    }

    num_lineas = rng.randint(2, 4) if pequeno else rng.randint(15, 110)
    lineas = [
        {
            "sku": f"SKU-{rng.randint(1000, 9999)}-{rng.choice('ABCDEFGH')}{rng.choice('XYZ')}",
            "descripcion": f"{rng.choice(PRODUCTOS)} ({rng.choice(ACABADOS)})",
            "cantidad": rng.randint(1, 10),
            "precio": round(rng.uniform(1.5, 250.0), 2),
        }
        for _ in range(num_lineas)
    ]

    pedido: dict[str, Any] = {
        "id": f"PED-{indice:06d}",
        "fecha": _fecha_aleatoria(rng),
        "cliente": cliente,
        "lineas": lineas,
    }
    if _decidir(rng, con_descuento, 0.3):
        pedido["descuento"] = rng.choice([5, 10, 12.5, 15, 20])
    pedido["notas"] = rng.choice(NOTAS) if _decidir(rng, con_notas, 0.4) else None
    pedido["pagado"] = rng.random() < 0.8
    pedido["etiquetas"] = (
        rng.sample(ETIQUETAS, rng.randint(1, 3)) if _decidir(rng, con_etiquetas, 0.6) else []
    )
    return pedido


def modelos_pedido(rng: random.Random) -> list[dict[str, Any]]:
    """Tres pedidos válidos que cubren los campos opcionales y los que admiten ``null``."""
    return [
        generar_pedido(rng, 1, pequeno=True, con_telefono=True, con_descuento=True,
                       con_notas=True, con_etiquetas=True),
        generar_pedido(rng, 2, pequeno=True, con_telefono=False, con_descuento=False,
                       con_notas=False, con_etiquetas=False),
        generar_pedido(rng, 3, pequeno=True, con_telefono=True, con_descuento=False,
                       con_notas=False, con_etiquetas=True),
    ]


# --------------------------------------------------------------------------- lectura de sensor

def generar_lectura_sensor(
    rng: random.Random,
    indice: int,
    *,
    pequeno: bool = False,
    planta: str | None = None,
    con_bateria: bool | None = None,
    con_alertas: bool | None = None,
) -> dict[str, Any]:
    """Genera las lecturas de un sensor ambiental.

    ``planta`` puede ser ``"valor"``, ``"nulo"`` o ``"ausente"`` (al azar si es ``None``).
    """
    ubicacion: dict[str, Any] = {
        "lat": round(rng.uniform(36.0, 43.5), 6),
        "lon": round(rng.uniform(-9.0, 3.0), 6),
    }
    planta = planta or rng.choice(["valor", "valor", "nulo", "ausente"])
    if planta == "valor":
        ubicacion["planta"] = rng.randint(-1, 8)
    elif planta == "nulo":
        ubicacion["planta"] = None

    num_lecturas = rng.randint(3, 6) if pequeno else rng.randint(8, 45)
    lecturas = []
    for _ in range(num_lecturas):
        magnitud, unidad, minimo, maximo = rng.choice(MAGNITUDES)
        lecturas.append({
            "magnitud": magnitud,
            "valor": round(rng.uniform(minimo, maximo), 2),
            "unidad": unidad,
        })

    lectura: dict[str, Any] = {
        "sensor_id": f"SEN-{rng.randint(1, 500):04d}",
        "timestamp": _fecha_aleatoria(rng),
        "ubicacion": ubicacion,
        "lecturas": lecturas,
    }
    if _decidir(rng, con_bateria, 0.7):
        lectura["bateria"] = rng.randint(0, 100)
    lectura["firmware"] = f"v{rng.randint(1, 3)}.{rng.randint(0, 9)}.{rng.randint(0, 20)}"
    lectura["alertas"] = (
        rng.sample(ALERTAS, rng.randint(1, 2)) if _decidir(rng, con_alertas, 0.15) else []
    )
    return lectura


def modelos_lectura_sensor(rng: random.Random) -> list[dict[str, Any]]:
    """Tres lecturas válidas: planta con valor, nula y ausente; batería opcional."""
    return [
        generar_lectura_sensor(rng, 1, pequeno=True, planta="valor", con_bateria=True,
                               con_alertas=True),
        generar_lectura_sensor(rng, 2, pequeno=True, planta="nulo", con_bateria=False,
                               con_alertas=False),
        generar_lectura_sensor(rng, 3, pequeno=True, planta="ausente", con_bateria=True,
                               con_alertas=False),
    ]


# --------------------------------------------------------------------------- actividad

def _distancia_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia en metros entre dos coordenadas (fórmula del haversine)."""
    fi1, fi2 = math.radians(lat1), math.radians(lat2)
    delta_fi = fi2 - fi1
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_fi / 2) ** 2 + math.cos(fi1) * math.cos(fi2) * math.sin(delta_lambda / 2) ** 2
    return 2 * RADIO_TIERRA_M * math.asin(math.sqrt(a))


def _zona_fc(fc: int) -> int:
    for zona, limite in enumerate(UMBRALES_ZONAS_FC, start=1):
        if fc < limite:
            return zona
    return len(UMBRALES_ZONAS_FC) + 1


def _repartir_puntos(rng: random.Random, total: int) -> list[int]:
    """Divide ``total`` puntos (al menos 10) en entre 1 y 6 segmentos consecutivos."""
    num_segmentos = rng.randint(1, max(1, min(6, total // 5)))
    cortes = sorted(rng.sample(range(5, total - 4), num_segmentos - 1)) if num_segmentos > 1 else []
    limites = [0, *cortes, total]
    return [fin - inicio for inicio, fin in zip(limites, limites[1:])]


def generar_actividad(
    rng: random.Random,
    indice: int,
    *,
    pequeno: bool = False,
    deporte: str | None = None,
    con_fc: bool | None = None,
    con_cadencia: bool | None = None,
    con_fotos: bool | None = None,
    con_grasa: bool | None = None,
    con_comentario: bool | None = None,
    peso_decimal: bool | None = None,
) -> dict[str, Any]:
    """Genera una actividad deportiva registrada con GPS.

    Los puntos forman un recorrido continuo (``t`` creciente y coordenadas cercanas) y el
    resumen se calcula a partir de ellos.
    """
    deporte = deporte or rng.choice(list(DEPORTES))
    velocidad_min, velocidad_max, (paso_min, paso_max), fc_base = DEPORTES[deporte]
    con_fc = _decidir(rng, con_fc, 0.7)
    con_cadencia = deporte != "senderismo" and _decidir(rng, con_cadencia, 0.6)
    num_puntos = rng.randint(10, 30) if pequeno else int(rng.triangular(200, 5000, 900))

    salida_lat, salida_lon = rng.choice(PUNTOS_DE_SALIDA)
    lat = salida_lat + rng.uniform(-0.05, 0.05)
    lon = salida_lon + rng.uniform(-0.05, 0.05)
    alt = rng.uniform(20.0, 1200.0)
    rumbo = rng.uniform(0.0, 2 * math.pi)
    velocidad_ms = rng.uniform(velocidad_min, velocidad_max) / 3.6
    t = 0
    distancia_m = 0.0
    desnivel_m = 0.0
    segundos_por_zona = [0] * (len(UMBRALES_ZONAS_FC) + 1)

    segmentos = []
    for numero, puntos_del_segmento in enumerate(_repartir_puntos(rng, num_puntos), start=1):
        tipo_tramo = rng.choice(list(PENDIENTES))
        pendiente = rng.uniform(*PENDIENTES[tipo_tramo])
        puntos = []
        for _ in range(puntos_del_segmento):
            if puntos or segmentos:
                paso_s = rng.randint(paso_min, paso_max)
                avance_m = velocidad_ms * paso_s * rng.uniform(0.8, 1.2)
                rumbo += rng.gauss(0.0, 0.2)
                nueva_lat = lat + avance_m * math.cos(rumbo) / METROS_POR_GRADO
                nueva_lon = lon + avance_m * math.sin(rumbo) / (
                    METROS_POR_GRADO * math.cos(math.radians(lat)))
                nueva_alt = max(0.0, alt + avance_m * pendiente + rng.gauss(0.0, 0.3))
                distancia_m += _distancia_m(lat, lon, nueva_lat, nueva_lon)
                desnivel_m += max(0.0, nueva_alt - alt)
                lat, lon, alt, t = nueva_lat, nueva_lon, nueva_alt, t + paso_s
            else:
                paso_s = 0
            punto: dict[str, Any] = {
                "lat": round(lat, 6),
                "lon": round(lon, 6),
                "alt": round(alt, 1),
                "t": t,
            }
            # El pulsómetro pierde la señal en algún punto suelto.
            if con_fc and rng.random() > 0.03:
                fc = int(min(195, max(70, rng.gauss(fc_base + 150 * pendiente, 6))))
                punto["fc"] = fc
                segundos_por_zona[_zona_fc(fc) - 1] += paso_s
            if con_cadencia:
                punto["cadencia"] = rng.randint(75, 95) if deporte == "ciclismo" else rng.randint(160, 185)
            puntos.append(punto)
        segmentos.append({
            "nombre": f"{rng.choice(NOMBRES_TRAMO)} {numero}",
            "tipo": tipo_tramo,
            "puntos": puntos,
        })

    sensores = ["pulsometro"] if con_fc else []
    if con_cadencia:
        sensores.append("cadencia")
    if rng.random() < 0.4:
        sensores.append(rng.choice(SENSORES_EXTRA))

    usuario: dict[str, Any] = {
        "id": f"USR-{rng.randint(1, 9999):04d}",
        "alias": f"{rng.choice(ALIAS)}{rng.randint(1, 99)}",
        "peso_kg": (round(rng.uniform(50.0, 95.0), 1) if _decidir(rng, peso_decimal, 0.5)
                    else rng.randint(50, 95)),
    }
    if _decidir(rng, con_grasa, 0.4):
        usuario["%grasa"] = round(rng.uniform(8.0, 30.0), 1)

    duracion_s = t
    actividad: dict[str, Any] = {
        "id": f"ACT-{indice:06d}",
        "deporte": deporte,
        "inicio": _fecha_aleatoria(rng),
        "privada": rng.random() < 0.2,
        "usuario": usuario,
        "dispositivo": {
            "modelo": rng.choice(MODELOS_DISPOSITIVO),
            "firmware": f"{rng.randint(2, 5)}.{rng.randint(0, 30)}.0",
            "sensores": sensores,
        },
        "segmentos": segmentos,
        "resumen": {
            "distancia_km": round(distancia_m / 1000, 2),
            "duracion_s": duracion_s,
            "desnivel_m": round(desnivel_m, 1),
            "velocidad_media": round(distancia_m / 1000 / (duracion_s / 3600), 2) if duracion_s else 0,
        },
    }
    if con_fc:
        actividad["pulso"] = {f"zona {n}": s for n, s in enumerate(segundos_por_zona, start=1)}
    if _decidir(rng, con_fotos, 0.3):
        todos_los_puntos = [p for s in segmentos for p in s["puntos"]]
        actividad["fotos"] = [
            {"archivo": f"IMG_{rng.randint(1000, 9999)}.jpg", "lat": p["lat"], "lon": p["lon"]}
            for p in rng.sample(todos_los_puntos, rng.randint(1, 4))
        ]
    actividad["comentario"] = (
        rng.choice(["Buenas sensaciones", "Mucho viento", "Ritmo suave", "Día de calor"])
        if _decidir(rng, con_comentario, 0.4) else None
    )
    return actividad


def modelos_actividad(rng: random.Random) -> list[dict[str, Any]]:
    """Tres actividades válidas que cubren los campos opcionales y los que admiten ``null``."""
    return [
        generar_actividad(rng, 1, pequeno=True, deporte="carrera", con_fc=True, con_cadencia=True,
                          con_fotos=True, con_grasa=True, con_comentario=True, peso_decimal=False),
        generar_actividad(rng, 2, pequeno=True, deporte="ciclismo", con_fc=True, con_cadencia=True,
                          con_fotos=False, con_grasa=False, con_comentario=False, peso_decimal=True),
        generar_actividad(rng, 3, pequeno=True, deporte="senderismo", con_fc=False,
                          con_fotos=True, con_grasa=False, con_comentario=False, peso_decimal=True),
    ]


# --------------------------------------------------------------------------- sin tipo

def generar_sin_tipo(rng: random.Random, indice: int, *, pequeno: bool = False) -> dict[str, Any]:
    """Documento cualquiera cuyo nombre no encaja con ningún patrón."""
    return {
        "titulo": f"Informe {indice}",
        "generado": _fecha_aleatoria(rng),
        "valores": [rng.randint(0, 100) for _ in range(rng.randint(3, 10))],
    }


# --------------------------------------------------------------------------- lote

TIPOS = (
    TipoDocumento("pedido", "pedido", 0.45, generar_pedido, modelos_pedido),
    TipoDocumento("lectura_sensor", "sensor", 0.40, generar_lectura_sensor,
                  modelos_lectura_sensor),
    # Las actividades son mucho más grandes: menos archivos para que el lote no se dispare.
    TipoDocumento("actividad", "ruta", 0.12, generar_actividad, modelos_actividad),
)


def _escribir_json(ruta: Path, documento: Any) -> int:
    """Escribe el documento y devuelve el número de bytes escritos."""
    datos = json.dumps(documento, ensure_ascii=False, indent=2).encode("utf-8")
    ruta.write_bytes(datos)
    return len(datos)


def _elegir_tipo(rng: random.Random) -> TipoDocumento | None:
    """Elige el tipo del siguiente archivo; ``None`` significa sin tipo."""
    if rng.random() < PROPORCION_SIN_TIPO:
        return None
    return rng.choices(TIPOS, weights=[t.peso for t in TIPOS])[0]


def generar_lote(
    salida: Path, archivos: int, semilla: int, tasa_errores: float, pequenos: bool
) -> Estadisticas:
    """Genera los modelos y los archivos de entrada del lote."""
    carpeta_modelos = salida / "modelos"
    carpeta_entrada = salida / "entrada"
    carpeta_modelos.mkdir(parents=True, exist_ok=True)
    carpeta_entrada.mkdir(parents=True, exist_ok=True)

    estadisticas = Estadisticas(por_tipo=Counter())
    rng_modelos = random.Random(semilla)
    for tipo in TIPOS:
        for numero, modelo in enumerate(tipo.generar_modelos(rng_modelos), start=1):
            ruta = carpeta_modelos / f"{tipo.prefijo}_modelo_{numero}.json"
            estadisticas.total_bytes += _escribir_json(ruta, modelo)

    rng = random.Random(semilla + 1)
    ancho = max(4, len(str(archivos)))
    for indice in range(1, archivos + 1):
        tipo = _elegir_tipo(rng)
        if tipo is None:
            prefijo = rng.choice(PREFIJOS_SIN_TIPO)
            documento = generar_sin_tipo(rng, indice, pequeno=pequenos)
            estadisticas.por_tipo["sin tipo"] += 1
        else:
            prefijo = tipo.prefijo
            documento = tipo.generar(rng, indice, pequeno=pequenos)
            estadisticas.por_tipo[tipo.nombre] += 1
        ruta = carpeta_entrada / f"{prefijo}_{indice:0{ancho}d}.json"
        estadisticas.total_bytes += _escribir_json(ruta, documento)
    return estadisticas


def _mostrar_resumen(salida: Path, archivos: int, estadisticas: Estadisticas, segundos: float) -> None:
    print(f"Lote generado en {salida}")
    print(f"  Modelos: {3 * len(TIPOS)} (3 por tipo) en modelos/")
    print(f"  Archivos de entrada: {archivos}")
    for nombre in [t.nombre for t in TIPOS] + ["sin tipo"]:
        print(f"    {nombre:<18}{estadisticas.por_tipo[nombre]:>7}")
    print(f"  Tamaño total: {estadisticas.total_bytes / 1_048_576:.1f} MB")
    print(f"  Tiempo: {segundos:.1f} s")


def _parsear_argumentos(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Genera lotes de JSON sintéticos.")
    parser.add_argument("--archivos", type=int, required=True, help="número de archivos de entrada")
    parser.add_argument("--salida", type=Path, required=True, help="carpeta del lote")
    parser.add_argument("--semilla", type=int, default=42, help="semilla aleatoria (reproducible)")
    parser.add_argument("--tasa-errores", type=float, default=0.1,
                        help="proporción de archivos con errores inyectados (0 a 1)")
    parser.add_argument("--pequenos", action="store_true",
                        help="documentos pequeños, para ejemplos y pruebas rápidas")
    args = parser.parse_args(argv)
    if args.archivos < 1:
        parser.error("--archivos debe ser al menos 1")
    if not 0.0 <= args.tasa_errores <= 1.0:
        parser.error("--tasa-errores debe estar entre 0 y 1")
    return args


def main(argv: list[str] | None = None) -> int:
    args = _parsear_argumentos(argv)
    inicio = time.perf_counter()
    estadisticas = generar_lote(args.salida, args.archivos, args.semilla, args.tasa_errores,
                                args.pequenos)
    _mostrar_resumen(args.salida, args.archivos, estadisticas, time.perf_counter() - inicio)
    return 0


if __name__ == "__main__":
    sys.exit(main())
