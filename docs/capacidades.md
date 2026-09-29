# Capacidades del formato de esquema

Qué reglas de validación y qué usos admite el formato de esquema.

## Situación inicial: formato propio (`esquemas.json`)

| Regla o uso | Ejemplo | Formato propio | Notas |
|---|---|:---:|---|
| Tipos | `cantidad` es un número | ✅ | texto, número, booleano, objeto, lista y desconocido |
| Campos obligatorios y opcionales | `telefono` puede faltar | ✅ | `req` en cada campo |
| Nulos | `notas` puede ser `null` | ✅ | `nulo` en cada nodo |
| Uniones de tipos | `codigo` es número o texto | ✅ | `t` como lista |
| Rangos numéricos (`minimum` / `maximum`) | `cantidad` ≥ 1; `fc` entre 30 y 220 | ❌ | |
| Enteros frente a decimales (`integer`) | `t` (segundos) es entero | ❌ | `int` y `float` son el mismo tipo |
| Patrones de texto (`pattern`) | `sku` con la forma `SKU-1234-AB` | ❌ | |
| Valores permitidos (`enum`) | `deporte` ∈ {carrera, ciclismo, senderismo} | ❌ | |
| Formatos (`email`, `date-time`) | `email` del cliente, `fecha` del pedido | ❌ | |
| Longitud de listas (`minItems`) | un pedido tiene al menos una línea | ❌ | |
| Reutilización de subesquemas (`$ref`) | la forma `{lat, lon}` en puntos y fotos | ❌ | cada subesquema se repite en línea |
| Edición en otras herramientas (VS Code, APIs) | validar el JSON mientras se escribe | ❌ | el formato solo lo entiende esta herramienta |
| Documentación del esquema (`description`) | explicar qué es `fc` | ❌ | |

**Resumen:** 4 de 13. El formato propio solo expresa la **forma** de los datos (tipos, obligatorios,
nulos y uniones), no reglas sobre sus **valores**.

### Una regla añadida a mano se pierde sin avisar

Comprobado con la versión actual: si se añade `"minimum": 1` al esquema de `cantidad` en
`esquemas.json`,

1. `validar` la **ignora**: un documento con `"cantidad": -5` sale válido, sin incidencias;
2. el siguiente guardado (por ejemplo `actualizar`) la **borra**, porque el almacén solo conoce
   las claves `t`, `nulo`, `campos`, `req`, `esq` e `item`.

Así que el esquema deducido no se puede enriquecer a mano: cualquier regla de negocio tendría que
programarse en el validador propio.
