# Especificación funcional – Gestor de tipos JSON

Herramienta de línea de comandos para gestionar tipos de JSON:

1. El usuario **registra un tipo** a partir de uno o varios JSON modelo, le da un nombre y un
   patrón de nombre de archivo (por ejemplo `pedido_*.json` o `ruta_*.json`).
2. La herramienta **deduce el esquema** del tipo a partir de los modelos y lo guarda (por defecto,
   como JSON Schema).
3. Después, cada JSON que se le pasa **se clasifica por su nombre de archivo** y **se valida** contra
   el esquema de su tipo, generando un informe de incidencias.

El programa **nunca** es interactivo: todo se controla con argumentos de línea de comandos y archivos.

## Comandos

```
python main.py registrar --tipo <nombre> --patron "<patrón>" --modelo <archivo> [--modelo <archivo> ...]
python main.py actualizar --tipo <nombre> --modelo <archivo> [--modelo <archivo> ...]
python main.py tipos
python main.py mostrar --tipo <nombre>
python main.py eliminar --tipo <nombre>
python main.py validar <archivo_o_carpeta> --salida <carpeta> [--estricto] [--max-incidencias 200]
python main.py migrar-esquemas [--desde esquemas.json] [--hacia esquemas] [--verificar <archivo_o_carpeta>]
python main.py exportar-vscode [--esquemas esquemas] [--salida .vscode/settings.json]
```

Los seis primeros comandos aceptan **`--formato jsonschema|propio`** (por defecto, `jsonschema`),
que elige dónde se guardan los tipos y con qué se validan (ver [Formatos de esquema](#formatos-de-esquema)).

- **`registrar`:** crea un tipo nuevo a partir de uno o varios modelos. Error si el tipo ya existe,
  si el patrón está vacío o si algún modelo no es JSON válido. Con JSON Schema, además, si el
  nombre no sirve como nombre de archivo (ver [Almacenamiento en JSON Schema](#almacenamiento-en-json-schema)).
- **`actualizar`:** añade modelos a un tipo existente y **fusiona** el esquema. Conserva la fecha de
  registro y, con JSON Schema, las reglas añadidas a mano.
- **`tipos`:** lista los tipos registrados con su patrón, número de modelos usados y fecha de registro.
- **`mostrar`:** imprime el esquema deducido de un tipo en forma de árbol legible.
- **`eliminar`:** borra un tipo (con JSON Schema, también su archivo de esquema).
- **`validar`:** valida un archivo o todos los `.json` de una carpeta (sin entrar en subcarpetas) y
  escribe los informes. Con `--estricto`, los campos no previstos cuentan como error en vez de aviso.
- **`migrar-esquemas`:** copia todos los tipos del formato propio (`--desde`) a JSON Schema
  (`--hacia`), con su patrón, sus modelos usados, su fecha y el orden de registro. No sobrescribe una
  carpeta que ya tenga tipos. Con `--verificar`, valida esos archivos con los dos formatos (en modo
  normal y estricto) y comprueba que dan las mismas incidencias: código 0 si coinciden y 1 si no.
- **`exportar-vscode`:** escribe en `--salida` la configuración `json.schemas` de VS Code, que asocia
  cada patrón (en cualquier carpeta, `**/<patrón>`) con su esquema, para que el editor valide los JSON
  mientras se escriben. Si el archivo existe, conserva el resto de la configuración.

## Clasificación por nombre de archivo

- Cada tipo tiene un **patrón** estilo `fnmatch` sobre el nombre del archivo (sin la ruta),
  distinguiendo mayúsculas: `pedido_*.json`, `sensor_*.json`, `ruta_*.json`, `*_borrador.json`…
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

La inferencia y la fusión son las mismas con los dos formatos: el esquema se deduce en memoria y se
convierte al formato elegido al guardarlo.

## Validación de un documento contra su esquema

Categorías de incidencia:

| Categoría | Nivel | Cuándo |
|---|---|---|
| `json_invalido` | error | El archivo no es JSON válido o no se puede leer |
| `falta_campo` | error | Falta un campo obligatorio |
| `campo_extra` | aviso (error con `--estricto`) | Hay un campo que el esquema no contempla |
| `tipo_incorrecto` | error | El valor no es de ninguno de los tipos permitidos |
| `nulo_no_permitido` | error | El valor es `null` y el esquema no admite nulo |
| `regla_incumplida` | error | Solo con JSON Schema: el valor incumple otra regla del esquema (`minimum`, `pattern`, `enum`, `format`, `minItems`…) |
| `varios_tipos` | aviso | El nombre del archivo encaja con varios patrones |
| `sin_tipo` | aviso | El nombre del archivo no encaja con ningún patrón |
| `incidencias_truncadas` | aviso | El archivo tiene más incidencias que `--max-incidencias` |

- Las listas se validan **elemento a elemento** contra el esquema de elemento.
- `desconocido` acepta cualquier valor.
- Cada incidencia lleva su **ruta** en notación JSONPath: `$.cliente.email`, `$.lineas[3].precio`,
  `$.pulso["zona 1"]`. Las incidencias de un archivo se ordenan por ruta (con los índices en orden
  numérico).
- Máximo `--max-incidencias` por archivo (por defecto 200). Si se superan, se añade una única
  incidencia de aviso `incidencias_truncadas` con el total real.
- Con los dos formatos se obtienen **las mismas incidencias** (categoría, nivel, ruta, esperado,
  encontrado y mensaje) para un mismo esquema deducido. `regla_incumplida` solo aparece si se han
  añadido reglas a mano al JSON Schema.

## Formatos de esquema

### Almacenamiento en JSON Schema

Formato por defecto (`--formato jsonschema`): **JSON Schema draft 2020-12**, validado con la librería
`jsonschema` y su comprobación de formatos. Un archivo por tipo en `esquemas/`, más un índice:

```
esquemas/
  registro.json          # {"tipos": [{"tipo", "patron", "archivo", "modelos_usados", "registrado"}, ...]}
  pedido.schema.json
  ...
```

- El índice guarda los tipos **en orden de registro** (el orden decide los empates de clasificación).
- El nombre del tipo es el nombre de su archivo (`<tipo>.schema.json`): solo admite letras,
  números, `_`, `-` y `.`, y no puede contener `..`. Las entradas del índice tampoco pueden apuntar
  fuera de la carpeta.

Conversión del esquema deducido:

| Esquema deducido | JSON Schema |
|---|---|
| texto, número, booleano | `"type": "string"`, `"number"`, `"boolean"` |
| objeto | `"type": "object"` con `properties`, `required` y `additionalProperties: false` |
| lista | `"type": "array"` con `items` |
| desconocido | `{}`; si procede de un `null`, `{"examples": [null]}` (no afecta a la validación) |
| admite nulo | `"null"` en `type` |
| unión | `type` como lista (`["number", "string"]`) |

Cada esquema lleva además `$schema`, `title` (el nombre del tipo) y una `description`.

**Reglas añadidas a mano.** El `.schema.json` se puede editar para añadir cualquier regla de JSON
Schema (`minimum`, `pattern`, `enum`, `format`, `$defs`/`$ref`, `description`…). Se respetan al
validar y **se conservan** cuando el esquema se vuelve a generar (por ejemplo, con `actualizar`). Lo
que se regenera a partir de los modelos es la estructura: `type`, `properties`, `required`,
`additionalProperties` e `items` (por eso un cambio a mano de `number` a `integer` se pierde al
actualizar). `date-time` sigue el RFC 3339 y exige zona horaria.

### Almacenamiento en el formato propio

Formato original (`--formato propio`). Todo se guarda en un único `esquemas.json`:
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
        "codigo": {"req": true, "esq": {"t": ["num", "str"], "nulo": false}},
        "notas": {"req": false, "esq": {"t": "str", "nulo": true}}
      }}
    }
  }
}
```

`t` es un código (`str`, `num`, `bool`, `obj`, `list`, `unk`) o una lista de códigos si es una unión.
Solo describe tipos, obligatorios, nulos y uniones: no admite reglas sobre los valores, y una clave
añadida a mano se ignora al validar y se pierde al guardar.

## Salidas de `validar` (en la carpeta indicada con `--salida`)

- `incidencias.csv`: archivo, tipo, nivel, categoría, ruta, esperado, encontrado y mensaje.
- `resumen_archivos.csv`: una fila por archivo con tipo, válido (`si`/`no`), número de errores y de
  avisos. Un archivo sin tipo sale como no válido, aunque no cuenta como error.
- `resumen_lote.json`: archivos totales, por tipo, válidos, con errores, sin tipo, incidencias por
  categoría, las 10 rutas con más incidencias por tipo (con los índices agrupados como `[*]`) y el
  tiempo de ejecución.
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
