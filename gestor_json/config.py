"""Constantes del programa: archivos, límites, niveles y categorías de incidencia."""

ARCHIVO_ESQUEMAS = "esquemas.json"
"""Archivo donde se guardan los tipos registrados (en la carpeta de trabajo)."""

MAX_INCIDENCIAS_POR_DEFECTO = 200
"""Incidencias que se guardan como máximo por archivo si no se indica otro límite."""

TOP_RUTAS = 10
"""Número de rutas con más incidencias que se incluyen por tipo en el resumen del lote."""

EXTENSION_JSON = ".json"

ARCHIVO_INCIDENCIAS = "incidencias.csv"
ARCHIVO_RESUMEN_ARCHIVOS = "resumen_archivos.csv"
ARCHIVO_RESUMEN_LOTE = "resumen_lote.json"


class Nivel:
    """Gravedad de una incidencia."""

    ERROR = "error"
    AVISO = "aviso"


class Categoria:
    """Categorías de incidencia que aparecen en los informes."""

    JSON_INVALIDO = "json_invalido"
    FALTA_CAMPO = "falta_campo"
    CAMPO_EXTRA = "campo_extra"
    TIPO_INCORRECTO = "tipo_incorrecto"
    NULO_NO_PERMITIDO = "nulo_no_permitido"
    VARIOS_TIPOS = "varios_tipos"
    SIN_TIPO = "sin_tipo"
    INCIDENCIAS_TRUNCADAS = "incidencias_truncadas"
