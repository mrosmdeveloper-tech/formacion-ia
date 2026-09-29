# Especificación funcional – Gestor de tipos JSON

Herramienta de línea de comandos para gestionar tipos de JSON:

1. El usuario **registra un tipo** a partir de uno o varios JSON modelo, le da un nombre y un
   patrón de nombre de archivo (por ejemplo `pedido_*.json` o `ruta_*.json`).
2. La herramienta **deduce el esquema** del tipo a partir de los modelos y lo guarda.
3. Después, cada JSON que se le pasa **se clasifica por su nombre de archivo** y **se valida** contra
   el esquema de su tipo, generando un informe de incidencias.

El programa **nunca** es interactivo: todo se controla con argumentos de línea de comandos y archivos.

## Comandos

```
python gestor.py registrar --tipo <nombre> --patron "<patrón>" --modelo <archivo> [--modelo <archivo> ...]
python gestor.py actualizar --tipo <nombre> --modelo <archivo> [--modelo <archivo> ...]
python gestor.py tipos
python gestor.py mostrar --tipo <nombre>
python gestor.py eliminar --tipo <nombre>
python gestor.py validar <archivo_o_carpeta> --salida <carpeta> [--estricto] [--max-incidencias 200]
```

- **`registrar`:** crea un tipo nuevo a partir de uno o varios modelos. Error si el tipo ya existe,
  si el patrón está vacío o si algún modelo no es JSON válido.
- **`actualizar`:** añade modelos a un tipo existente y **fusiona** el esquema.
- **`tipos`:** lista los tipos registrados con su patrón, número de modelos usados y fecha de registro.
- **`mostrar`:** imprime el esquema de un tipo en forma de árbol legible.
- **`eliminar`:** borra un tipo.
- **`validar`:** valida un archivo o todos los `.json` de una carpeta (sin entrar en subcarpetas) y
  escribe los informes. Con `--estricto`, los campos no previstos cuentan como error en vez de aviso.

## Clasificación por nombre de archivo

- Cada tipo tiene un **patrón** estilo `fnmatch` sobre el nombre del archivo (sin la ruta):
  `pedido_*.json`, `sensor_*.json`, `ruta_*.json`, `*_borrador.json`…
- Si un archivo encaja con **varios** patrones, se elige el **más específico** (el que tiene más
  caracteres literales, es decir, que no son `*` ni `?`) y se registra un aviso. Si hay empate,
  gana el tipo registrado primero.
- Si no encaja con ninguno, el archivo se marca como **sin tipo** y no se valida.

## Deducción del esquema (inferencia)

Tipos lógicos: `texto`, `numero`, `booleano`, `nulo`, `objeto`, `lista`, `desconocido`.

A partir de **un modelo**:
- Un objeto → `objeto` con cada una de sus claves como campo **obligatorio**, con su esquema deducido.
- Una lista con elementos → `lista`, cuyo esquema de elemento es la **fusión** de los esquemas de todos
  sus elementos. Una lista vacía → `lista` de `desconocido`.
- `null` → `desconocido` **admitiendo nulo**.
- `int` o `float` → `numero`; `str` → `texto`; `bool` → `booleano`.

**Fusión** de dos esquemas (entre varios modelos o entre los elementos de una lista):
- Mismo tipo → se queda ese tipo; en objetos y listas, se fusiona recursivamente.
- Objetos: un campo presente en **todos** es obligatorio; un campo presente solo en algunos pasa a
  **opcional**.
- `desconocido` + cualquier tipo X → X (y si el desconocido admitía nulo, X admite nulo).
- `nulo` + X → X admitiendo nulo.
- Tipos distintos e incompatibles (por ejemplo, `texto` + `numero`) → **unión** de ambos tipos.

## Validación de un documento contra su esquema

Categorías de incidencia:

| Categoría | Nivel | Cuándo |
|---|---|---|
| `json_invalido` | error | El archivo no es JSON válido o no se puede leer |
| `falta_campo` | error | Falta un campo obligatorio |
| `campo_extra` | aviso (error con `--estricto`) | Hay un campo que el esquema no contempla |
| `tipo_incorrecto` | error | El valor no es de ninguno de los tipos permitidos |
| `nulo_no_permitido` | error | El valor es `null` y el esquema no admite nulo |
| `varios_tipos` | aviso | El nombre del archivo encaja con varios patrones |
| `sin_tipo` | aviso | El nombre del archivo no encaja con ningún patrón |

- Las listas se validan **elemento a elemento** contra el esquema de elemento.
- `desconocido` acepta cualquier valor.
- Cada incidencia lleva su **ruta** en notación JSONPath: `$.cliente.email`, `$.lineas[3].precio`,
  `$.pulso["zona 1"]`.
- Máximo `--max-incidencias` por archivo (por defecto 200). Si se superan, se añade una única
  incidencia de aviso `incidencias_truncadas` con el total real.

## Almacenamiento de esquemas (versión inicial, formato propio)

Todo se guarda en un único `esquemas.json`:
```json
{
  "tipos": {
    "pedido": {
      "patron": "pedido_*.json",
      "modelos_usados": 3,
      "registrado": "2026-09-29T10:00:00",
      "esquema": {"t": "obj", "nulo": false, "campos": {
        "id": {"req": true, "esq": {"t": "str", "nulo": false}},
        "lineas": {"req": true, "esq": {"t": "list", "nulo": false,
                   "item": {"t": "obj", "nulo": false, "campos": {"...": "..."}}}},
        "notas": {"req": false, "esq": {"t": ["str"], "nulo": true}}
      }}
    }
  }
}
```

## Salidas de `validar` (en la carpeta indicada con `--salida`)

- `incidencias.csv`: archivo, tipo, nivel, categoría, ruta, esperado, encontrado y mensaje.
- `resumen_archivos.csv`: una fila por archivo con tipo, válido (`si`/`no`), número de errores y de avisos.
- `resumen_lote.json`: archivos totales, por tipo, válidos, con errores, sin tipo, incidencias por
  categoría, las 10 rutas con más incidencias por tipo y el tiempo de ejecución.
- Por consola: resumen del lote y tiempo total. **Código de salida** 0 si todo es válido, 1 si hay
  errores y 2 si falla la ejecución.

## Trampas conocidas

- En Python, `bool` es subclase de `int`: `isinstance(True, int)` es `True`. Comprueba **siempre**
  `bool` antes que número.
- `int` y `float` se tratan como el mismo tipo lógico: **número** (`150` y `9.2` son compatibles).
- Un valor vacío en el modelo (`null`, `[]`) no dice qué tipo debería tener: se trata como
  **desconocido** (acepta cualquier cosa) hasta que otro modelo lo concrete.
- `""` sí es texto: el tipo es **texto**.
- Las claves JSON pueden tener espacios o símbolos (`"zona 1"`, `"%grasa"`): las rutas de las
  incidencias deben representarlas sin ambigüedad (`$.pulso["zona 1"]`).
- Los archivos pueden venir con BOM de UTF-8 (usa `encoding="utf-8-sig"` al leer).
