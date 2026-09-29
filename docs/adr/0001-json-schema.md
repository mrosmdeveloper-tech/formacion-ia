# ADR 0001: Adoptar JSON Schema (draft 2020-12) como formato de esquema

- **Estado:** Propuesto
- **Fecha:** 2026-09-29

## Contexto

El gestor deduce el esquema de cada tipo a partir de sus modelos y lo guarda en `esquemas.json`
con un **formato propio** (`{"t": "num", "nulo": false, "campos": {...}}`) que solo entiende esta
herramienta. La validación la hace un **validador escrito a mano** (`ValidadorPropio`).

Este formato tiene tres límites:

1. **Solo describe la forma de los datos.** No admite las reglas habituales sobre los valores:
   rangos, patrones, enumerados, formatos ni longitudes. Admite 4 de las 13 reglas y usos
   analizados ([docs/capacidades.md](../capacidades.md)):

   | Regla o uso | Formato propio |
   |---|:---:|
   | Tipos, obligatorios, nulos, uniones | ✅ |
   | Rangos (`minimum`/`maximum`), enteros (`integer`) | ❌ |
   | Patrones (`pattern`), enumerados (`enum`), formatos (`email`, `date-time`) | ❌ |
   | Longitud de listas (`minItems`), subesquemas reutilizables (`$ref`) | ❌ |
   | Edición en otras herramientas (VS Code, APIs), documentación (`description`) | ❌ |

2. **No se puede enriquecer a mano.** Comprobado: si se añade `"minimum": 1` a un campo de
   `esquemas.json`, `validar` lo ignora (un `-5` sale válido) y el siguiente guardado lo borra sin
   avisar. Cualquier regla de negocio exigiría programarla en el validador.

3. **No se puede reutilizar.** El esquema no sirve para validar en el editor mientras se escribe
   un JSON, ni para documentar una API, ni para validar los mismos datos en otro sistema. Y el
   validador propio hay que mantenerlo a mano.

**Rendimiento actual** (formato propio, [docs/benchmark.md](../benchmark.md); mediana de 3
repeticiones, lotes con un 10 % de errores inyectados):

| Lote | Registro (s) | Validación (s) | Archivos/s | Incidencias |
|---|---:|---:|---:|---:|
| 1000 archivos (33 MB) | 0.021 | 1.02 | 977 | 141 |
| 5000 archivos (172 MB) | 0.017 | 5.41 | 924 | 722 |
| 10 000 archivos (336 MB) | 0.017 | 10.34 | 967 | 1427 |

La refactorización previa (PR #1) dejó el formato encapsulado tras dos interfaces, `Validador` y
`AlmacenEsquemas`, de las que dependen el registro, el lote y los informes. Cambiar de formato
solo exige nuevas implementaciones de esas dos interfaces.

## Decisión

Generar los esquemas como **JSON Schema draft 2020-12** y validar con la librería
**`jsonschema`**.

- **Almacenamiento:** un archivo por tipo, `esquemas/<tipo>.schema.json`, más un índice
  `esquemas/registro.json` con el tipo, el patrón, el archivo, los modelos usados y la fecha de
  registro, en orden de registro (el orden decide los empates de clasificación). Lo implementa
  `AlmacenEsquemasJsonSchema`.
- **Conversión del esquema deducido:**

  | Esquema deducido | JSON Schema |
  |---|---|
  | texto, número, booleano | `"type": "string"`, `"number"`, `"boolean"` |
  | objeto | `"type": "object"` con `properties`, `required` y `additionalProperties: false` |
  | lista | `"type": "array"` con `items` |
  | desconocido | `{}` (acepta cualquier valor) |
  | admite nulo | se añade `"null"` a `type` |
  | unión | `type` como lista (`["number", "string"]`) |

  Cada esquema lleva `$schema`, `title` (el nombre del tipo) y una `description` generada. La
  inferencia y la fusión **no cambian**: se sigue deduciendo el esquema en memoria y se convierte
  al guardar. Al cargar, las reglas que el usuario haya añadido a mano se **conservan**.
- **Validación:** `ValidadorJsonSchema` (implementa `Validador`) usa `Draft202012Validator`,
  **compilado una vez por tipo** y reutilizado en todo el lote, con el `FormatChecker` de
  `jsonschema`: sin él, `format` es solo una anotación y `email` o `date-time` no se comprueban.
  Se añade la dependencia `rfc3339-validator`, sin la cual `jsonschema` no comprueba `date-time`
  y lo ignora sin avisar, que es justo el defecto que se critica del formato propio.
  Recorre `iter_errors` y traduce cada error a las **mismas incidencias de siempre**, de modo
  que los informes no cambian:

  | Error de `jsonschema` | Incidencia |
  |---|---|
  | `required` | `falta_campo`, una por cada campo que falte, con la ruta del campo |
  | `additionalProperties` | `campo_extra`, una por campo; aviso, o error con `--estricto` |
  | `type` con valor `null` | `nulo_no_permitido` |
  | `type` con otro valor | `tipo_incorrecto` |
  | cualquier otra regla (`minimum`, `pattern`, `enum`, `format`…) | **nueva** categoría `regla_incumplida`, nivel error |

  Las rutas salen de `absolute_path` con el mismo formato JSONPath (`rutas.py`), y las
  incidencias se ordenan por ruta como en el validador propio. Los textos `esperado` y
  `encontrado` usan los mismos nombres de tipo (`texto | nulo`…).
- **Selección del formato:** opción `--formato jsonschema|propio`, por defecto `jsonschema`. El
  formato propio se mantiene para comparar y para migrar.
- **Migración:** comando `migrar-esquemas --desde esquemas.json --hacia esquemas/`, que al
  terminar comprueba que validar los datos de ejemplo con los dos formatos da las mismas
  incidencias.
- **Editor:** comando `exportar-vscode`, que genera `.vscode/settings.json` con `json.schemas`
  (cada patrón asociado a su esquema) para que VS Code valide los JSON mientras se editan.

## Alternativas consideradas

- **Mantener el formato y el validador propios.**
  - A favor: sin dependencias; ya funciona y está probado (99 % de cobertura); rendimiento
    conocido.
  - En contra: ninguna de las 9 capacidades que faltan; cada regla nueva habría que programarla y
    mantenerla; formato que no entiende ninguna otra herramienta.
- **JSON Schema con `fastjsonschema`.**
  - A favor: mismo estándar y, según sus propias mediciones, mucho más rápido (compila el
    esquema a código Python).
  - En contra: se detiene en el **primer** error de cada documento (lanza una excepción), así que
    no permite informar de todas las incidencias de un archivo; los errores traen menos
    información estructurada (ruta y validador), y el código generado dificulta depurar.
- **Modelos `pydantic` generados.**
  - A favor: validación rápida (núcleo en Rust) y errores detallados.
  - En contra: está pensado para modelos definidos **en código**, no para esquemas que se deducen
    en tiempo de ejecución y se editan como datos; generar clases dinámicamente complica la
    migración y la edición manual. Además exporta JSON Schema, pero no lo usa como fuente.
- **Otros formatos: JSON Type Definition (RFC 8927), Cerberus.**
  - A favor: JTD es simple y está pensado para generar código; Cerberus tiene reglas de valores
    (`min`, `regex`, `allowed`).
  - En contra: JTD no admite uniones de tipos (que la inferencia produce) ni `pattern`, y su
    soporte en editores es escaso; Cerberus es un formato propio de una librería de Python, sin
    soporte en VS Code ni en otros lenguajes.

## Consecuencias

- **Positivas:**
  - Las 9 capacidades que faltan pasan a estar disponibles, y las reglas se pueden añadir a mano
    al esquema sin programar nada.
  - Validación en VS Code mientras se edita, y esquemas reutilizables en APIs y en otros
    lenguajes.
  - El validador pasa a ser una librería mantenida y probada contra la suite oficial de JSON
    Schema.
  - Los informes y sus categorías no cambian, salvo la nueva `regla_incumplida`.
- **Negativas / riesgos:**
  - **Nuevas dependencias** (`jsonschema` y `rfc3339-validator`, con las suyas): las primeras
    dependencias de ejecución del proyecto.
  - **Traducción de errores:** hay que convertir los errores de `jsonschema` al formato de
    incidencias y garantizar que coinciden con los del validador propio (categoría, nivel, ruta y
    orden). Se mitiga con un test de equivalencia sobre todos los datos de `tests/datos/`.
  - **Rendimiento:** `jsonschema` es una implementación en Python puro y probablemente más lenta
    que el validador propio, que está hecho a medida. Hay que medirlo (ver Métricas) y decidir si
    compensa.
  - **Migración** de los `esquemas.json` existentes, cubierta con el comando `migrar-esquemas`
    y su verificación.
  - **Dos formatos que mantener** mientras exista la opción `--formato propio`.
- **Métricas:** *se completan en la Fase 4.4 con el benchmark final.*
