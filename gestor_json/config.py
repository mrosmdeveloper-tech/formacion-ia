"""Constantes del programa: archivos, límites, niveles y categorías de incidencia."""

ARCHIVO_ESQUEMAS = "esquemas.json"
"""Archivo donde se guardan los tipos registrados en el formato propio (en la carpeta de trabajo)."""

CARPETA_ESQUEMAS = "esquemas"
"""Carpeta donde se guardan los tipos registrados en JSON Schema (en la carpeta de trabajo)."""

ARCHIVO_REGISTRO = "registro.json"
"""Índice de los tipos registrados en JSON Schema, dentro de ``CARPETA_ESQUEMAS``."""

EXTENSION_ESQUEMA = ".schema.json"

CONFIGURACION_VSCODE = ".vscode/settings.json"
"""Configuración del proyecto en VS Code donde ``exportar-vscode`` asocia patrones y esquemas."""

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
    REGLA_INCUMPLIDA = "regla_incumplida"
    """Una regla de JSON Schema distinta de tipo, obligatorio o campo extra (minimum, pattern…)."""
