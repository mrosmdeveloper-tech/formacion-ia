# Capacidades del formato de esquema

Qué reglas de validación y qué usos admite cada formato de esquema.

## Comparativa

| Regla o uso | Ejemplo | Formato propio | JSON Schema | Cómo, en JSON Schema |
|---|---|:---:|:---:|---|
| Tipos | `cantidad` es un número | ✅ | ✅ | `type`, deducido de los modelos |
| Campos obligatorios y opcionales | `telefono` puede faltar | ✅ | ✅ | `required`, deducido |
| Nulos | `notas` puede ser `null` | ✅ | ✅ | `"null"` en `type`, deducido |
| Uniones de tipos | `codigo` es número o texto | ✅ | ✅ | `type` como lista, deducido |
| Rangos numéricos (`minimum` / `maximum`) | `cantidad` ≥ 1; `fc` entre 30 y 220 | ❌ | ✅ | a mano; probado ¹ |
| Enteros frente a decimales (`integer`) | `t` (segundos) es entero | ❌ | ⚠️ | a mano, cambiando `number` por `integer`; se valida, pero se regenera al `actualizar` ² |
| Patrones de texto (`pattern`) | `sku` con la forma `SKU-1234-AB` | ❌ | ✅ | a mano; probado ¹ |
| Valores permitidos (`enum`) | `deporte` ∈ {carrera, ciclismo, senderismo} | ❌ | ✅ | a mano; probado ¹ |
| Formatos (`email`, `date-time`) | `email` del cliente, `fecha` del pedido | ❌ | ✅ | a mano; se comprueban de verdad (`FormatChecker` y `rfc3339-validator`); probado ¹ ³ |
| Longitud de listas (`minItems`) | un pedido tiene al menos una línea | ❌ | ✅ | a mano; probado ¹ |
| Reutilización de subesquemas (`$ref`) | la forma `{lat, lon}` en puntos y fotos | ❌ | ✅ | a mano, con `$defs` y `$ref`; probado ¹ |
| Edición en otras herramientas (VS Code, APIs) | validar el JSON mientras se escribe | ❌ | ✅ | `exportar-vscode`; el esquema es estándar |
| Documentación del esquema (`description`) | explicar qué es `fc` | ❌ | ✅ | generada en la raíz; a mano en cualquier campo |

**Resumen:** el formato propio admite 4 de 13. JSON Schema admite **12 de 13 por completo y la
13.ª (`integer`) con una limitación**.

1. Tests en `tests/test_jsonschema_formato.py`: `test_reglas_anadidas_a_mano_se_detectan`
   (`minimum`, `maximum`, `pattern`, `enum`, `format` email y date-time),
   `test_regla_sobre_un_objeto_muestra_su_tipo` (`minItems`) y los tests de reglas a mano que se
   conservan al `actualizar` (incluido `$ref`).
2. `type`, `properties`, `required`, `additionalProperties` e `items` son la **estructura** que se
   deduce de los modelos, y se regeneran cada vez que se actualiza el tipo. El resto de reglas
   añadidas a mano se conservan.
3. `date-time` sigue el RFC 3339 y exige zona horaria (`2026-09-29T10:00:00Z`): las fechas del
   generador de datos no la llevan.

## Situación inicial: formato propio (`esquemas.json`)

El formato propio solo expresa la **forma** de los datos (tipos, obligatorios, nulos y uniones),
no reglas sobre sus **valores**.

### Una regla añadida a mano se pierde sin avisar

Comprobado con la versión anterior a JSON Schema: si se añade `"minimum": 1` al esquema de
`cantidad` en `esquemas.json`,

1. `validar` la **ignora**: un documento con `"cantidad": -5` sale válido, sin incidencias;
2. el siguiente guardado (por ejemplo `actualizar`) la **borra**, porque el almacén solo conoce
   las claves `t`, `nulo`, `campos`, `req`, `esq` e `item`.

Así que el esquema deducido no se podía enriquecer a mano: cualquier regla de negocio tenía que
programarse en el validador propio. Con JSON Schema, la misma regla se respeta al validar y se
conserva al actualizar.
