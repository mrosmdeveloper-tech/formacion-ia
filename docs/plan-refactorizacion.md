# Plan de refactorización de `gestor.py`

**Objetivo:** convertir `gestor.py` (680 líneas en un único archivo) en un paquete `gestor_json/`
con módulos pequeños, tipados y probados por separado, **sin cambiar el comportamiento observable**:
el mismo `esquemas.json`, los mismos informes byte a byte, la misma salida por consola y los mismos
códigos de salida.

**Red de seguridad:** los 80 tests de caracterización de la Fase 2 (96 % de cobertura de
`gestor.py`), incluido el que compara byte a byte `esquemas.json` y los tres informes del lote de
`datos/ejemplos/` con la referencia de `tests/datos/esperado/ejemplos/`.

---

## 1. Problemas detectados

Las referencias son a líneas de `gestor.py` en el commit `bb0bccc`.

### 1.1 Función gigante

- `main()` (líneas 244-672) tiene **429 líneas** y resuelve en línea los seis comandos: analiza
  los argumentos, lee y escribe archivos, clasifica, valida, agrega estadísticas, escribe informes
  e imprime. No se puede probar ninguna parte sin ejecutar el comando entero.
- Solo el bloque de `validar` (448-669) ocupa 222 líneas y mezcla cinco responsabilidades:
  argumentos, clasificación (530-563), lectura del documento (564-578), truncado (585-595) y
  agregación e informes (596-666).

### 1.2 `if` anidados y funciones largas

- `fusionar` (38-90): cinco niveles de anidamiento para decidir de dónde salen `campos` e `item`.
- `validar` (138-229): 92 líneas que comprueban nulos, tipos, campos obligatorios, campos extra y
  listas en una sola función recursiva.
- Especificidad de patrones (546-555): tres bucles anidados dentro de `main()`.

### 1.3 Duplicación

| Qué se repite | Dónde | Copias |
|---|---|---|
| Detección del tipo lógico de un valor | `inferir` 14-35, `validar` 157-168, campo extra 203-214 | 3 |
| Paso de `"t"` a lista (`if type(e["t"]) == list`) | 39-42, 43-46, 94-97, 124-127, 140-143 | 5 |
| Traducción de código a nombre (`"num"` → `"numero"`) | `desc` 99-113 y 203-214, más el truco `desc({"t": tv, ...})` en 175-176 | 2 |
| Carga de `esquemas.json` | 279-288, 335-344, 368-377, 398-407, 430-439, 490-499 | 6 |
| Guardado de `esquemas.json` | 311-313, 360-362, 444-446 | 3 |
| Lectura de un modelo JSON | 293-300, 349-356 | 2 |
| Bucle de análisis de argumentos | 256-269, 318-328, 387-394, 419-426, 453-479 | 5 |
| Construcción de rutas JSONPath | 181-184, 199-202, 229; se vuelven a analizar en `clave_orden` 232-241 y 609 | 4 |

### 1.4 Estado global

- `incidencias` (línea 10) es una lista global que `validar` llena (139, 148, 170, 189, 219) y que
  `main()` reinicia (529), recorta y reordena (580-587). La validación no se puede llamar de forma
  aislada ni en paralelo, y su resultado depende del estado anterior.

### 1.5 Diccionarios sin estructura

- El esquema es un diccionario anidado con claves crípticas (`t`, `req`, `esq`, `campos`, `item`),
  y `t` puede ser un texto **o** una lista. Cada función tiene que adivinar la forma.
- Las incidencias son diccionarios de seis claves construidos a mano en 8 sitios distintos (148,
  170, 189, 219, 536, 556, 570 y 588).
- El formato de almacenamiento está acoplado a toda la lógica: cambiarlo (Fase 4) obligaría a
  tocar la inferencia, la fusión, la validación y la presentación.

### 1.6 Cadenas y valores mágicos

- Códigos de tipo `"str"`, `"num"`, `"bool"`, `"obj"`, `"list"`, `"unk"` repartidos por todo el
  archivo.
- Categorías escritas a mano: `"nulo_no_permitido"` (150), `"tipo_incorrecto"` (172),
  `"falta_campo"` (191), `"campo_extra"` (221), `"sin_tipo"` (538), `"varios_tipos"` (558),
  `"json_invalido"` (572), `"incidencias_truncadas"` (590).
- Niveles `"error"` y `"aviso"`; el límite `200` (452); el top `10` (635); el nombre
  `"esquemas.json"` (21 apariciones); la expresión regular de identificador, repetida (181, 199,
  234).

### 1.7 Nombres poco descriptivos

- `d`, `e`, `v`, `r`, `f`, `m`, `n`, `p`, `x`, `tt`, `ta`, `tb`, `tv`, `est`, `mx`, `sal`,
  `cands`, `cerr`, `stip`…
- `aux` significa cinco cosas distintas: campos fusionados (64), nombre de un tipo (204), posición
  en la lista (580), total de incidencias (586) y categorías ordenadas (637). `tmp`, otras cuatro:
  nivel (216), tipo registrado (383), incidencias del documento (582) y rutas ordenadas (633).

### 1.8 Falta de tipos, documentación y manejo de recursos

- Sin type hints ni docstrings.
- Los archivos se abren sin `with` (281, 295, 311, 509-512, 565, 651): si hay una excepción, quedan
  abiertos.
- `fusionar` comparte subdiccionarios entre esquemas (79-81, 87-89) en lugar de copiarlos:
  cualquier modificación posterior afectaría a los dos.

---

## 2. Estructura objetivo

```
gestor_json/
  __init__.py
  config.py            # constantes: límites, categorías, niveles, nombres de archivo
  tipos_logicos.py     # enum TipoLogico y clasificar_valor(valor) (con la trampa de bool resuelta)
  modelos.py           # dataclasses: NodoEsquema, CampoEsquema, TipoRegistrado, Incidencia,
                       #   ResultadoArchivo
  rutas.py             # construcción de rutas JSONPath, clave de orden y normalización ([*])
  inferencia.py        # deducir el esquema de un documento (función pura)
  fusion.py            # fusionar dos esquemas (función pura)
  validacion.py        # interfaz Validador y ValidadorPropio (devuelve incidencias, sin globales)
  registro.py          # RegistroTipos: alta, baja, consulta y búsqueda de tipo por nombre de archivo
  almacenamiento.py    # interfaz AlmacenEsquemas y AlmacenEsquemasPropio (esquemas.json)
  lote.py              # validar un archivo o una carpeta y agregar resultados
  informes.py          # escritura de CSV y JSON, resumen por consola
  cli.py               # argparse con subcomandos, orquestación y códigos de salida
main.py                # punto de entrada
```

### Piezas principales

- **`TipoLogico`** (enum): `TEXTO`, `NUMERO`, `BOOLEANO`, `NULO`, `OBJETO`, `LISTA`, `DESCONOCIDO`,
  cuyo valor es el nombre que se muestra (`"texto"`, `"numero"`…). Los códigos `"str"`, `"num"`…
  pasan a ser un detalle **exclusivo** de `AlmacenEsquemasPropio`.
- **`clasificar_valor(valor) -> TipoLogico`**: la única detección de tipos del programa. Comprueba
  `bool` antes que `int`.
- **`NodoEsquema`**: `tipos: tuple[TipoLogico, ...]` (siempre una tupla, ordenada), `admite_nulo`,
  `campos: dict[str, CampoEsquema]` e `item: NodoEsquema | None`. Métodos `acepta(tipo)` y
  `describir()` (el antiguo `desc`).
- **`CampoEsquema`**: `obligatorio: bool` y `esquema: NodoEsquema`.
- **`Incidencia`** (inmutable): `nivel`, `categoria`, `ruta`, `esperado`, `encontrado` y `mensaje`,
  con constructores por categoría (`Incidencia.falta_campo(ruta, campo, esperado)`…) para que los
  mensajes se definan una sola vez.

### Decisión clave de diseño: dos interfaces que aíslan el formato del esquema

```python
class Validador(Protocol):
    def validar(self, documento: Any) -> list[Incidencia]: ...

class AlmacenEsquemas(Protocol):
    def cargar(self) -> dict[str, TipoRegistrado]: ...
    def guardar(self, tipos: dict[str, TipoRegistrado]) -> None: ...
```

- `ValidadorPropio` y `AlmacenEsquemasPropio` son las implementaciones actuales.
- `RegistroTipos`, `lote.py` e `informes.py` **solo dependen de las interfaces**. En la Fase 4 se
  añadirán `ValidadorJsonSchema` y `AlmacenEsquemasJsonSchema` sin tocar el registro, el lote ni
  los informes.

```
cli.py ──► RegistroTipos ──► AlmacenEsquemas ◄── AlmacenEsquemasPropio (esquemas.json)
   │                                                  (Fase 4: AlmacenEsquemasJsonSchema)
   └────► lote.py ──► Validador ◄── ValidadorPropio
            │                        (Fase 4: ValidadorJsonSchema)
            └──► informes.py
```

---

## 3. Pasos en orden

Estrategia de **estrangulamiento**: `gestor.py` sigue siendo el punto de entrada y cada paso le
quita una responsabilidad, que pasa a un módulo de `gestor_json/`. Tras cada paso se ejecuta toda
la batería (`python -m pytest`), y solo se hace commit con los 80 tests en verde.

| # | Commit | Qué cambia | Cómo se verifica |
|---|---|---|---|
| 1 | `refactor: extrae constantes y enum de tipos lógicos` | `config.py` (categorías, niveles, 200, 10, `esquemas.json`) y `tipos_logicos.py` con `TipoLogico`. `gestor.py` los usa en lugar de las cadenas. | 80 tests en verde |
| 2 | `refactor: clasificación de valores en una única función` | `clasificar_valor` sustituye a las 3 copias de detección de tipos (inferir, validar, campo extra). | Tests de `bool` frente a número y de campos extra |
| 3 | `refactor: introduce dataclasses del esquema y de las incidencias` | `modelos.py`, con la conversión desde y hacia el diccionario de `esquemas.json` en `almacenamiento.py`. La lógica trabaja con `NodoEsquema`; se guarda en el mismo formato. | `esquemas.json` idéntico byte a byte (orden de claves incluido) |
| 4 | `refactor: construcción de rutas JSONPath centralizada` | `rutas.py`: `ruta_campo`, `ruta_indice`, `clave_orden` y `normalizar` (`[*]`). | Tests de `$.pulso["zona 1"]`, del orden numérico y de las rutas más frecuentes |
| 5 | `refactor: inferencia y fusión como funciones puras` | `inferencia.py` y `fusion.py`, sin compartir subesquemas (copias nuevas). | Tests de inferencia y de las 5 reglas de fusión en ambos órdenes |
| 6 | `refactor: validador sin estado global que devuelve incidencias` | `ValidadorPropio.validar(documento) -> list[Incidencia]`; desaparece la global `incidencias`. El orden por ruta se aplica en el validador. | Test por categoría de incidencia; test golden |
| 7 | `refactor: registro de tipos y almacenamiento de esquemas separados` | `RegistroTipos` (alta, actualización, baja, consulta, clasificación por especificidad) y `AlmacenEsquemasPropio` (única carga y único guardado, con `with`). | Tests de comandos, de errores y de clasificación |
| 8 | `refactor: validación de lotes e informes separados` | `lote.py` (recorrer la carpeta, validar, truncar y agregar en `ResultadoArchivo`) e `informes.py` (CSV, `resumen_lote.json` y consola). | Tests de informes exactos y golden |
| 9 | `refactor: argparse con subcomandos en cli.py y punto de entrada main.py` | `cli.main(argv) -> int`, con un subcomando por comando y los mismos mensajes y códigos. `gestor.py` queda como envoltorio de una línea. | Tests de errores de argumentos |
| 10 | `refactor: mejora nombres, añade type hints y docstrings` | Repaso final de nombres, tipos y docstrings en todo el paquete. | 80 tests en verde |
| 11 | `test: adapta tests a la nueva estructura` | Se borra `gestor.py`; los tests llaman a `gestor_json.cli.main(argv)`. **Los valores esperados no cambian.** | Golden idéntico; `esquemas.json` e informes idénticos |

Después (Fase 3.3): tests unitarios directos de `tipos_logicos`, `inferencia`, `fusion`,
`validacion`, `rutas` y `registro`, con `pytest.mark.parametrize`.

---

## 4. Riesgos y cómo los mitigan los tests

| Riesgo | Mitigación |
|---|---|
| Cambiar sin querer el orden de las claves o el formato de `esquemas.json` al pasar a dataclasses | `test_registrar_infiere_todos_los_tipos_logicos` compara el texto exacto del archivo; el test golden, los bytes |
| Alterar el orden de los tipos de una unión (`numero \| texto`) | Tests de fusión y de `mostrar` con uniones. El enum se declara en el mismo orden que los códigos antiguos ordenados (`bool`, `list`, `num`, `obj`, `str`) |
| Romper la trampa de `bool` al unificar la detección de tipos | `test_incidencias_de_cada_documento[base_bool_numero.json]` |
| Cambiar el orden de las incidencias al quitar la global | Tests por documento con varias incidencias ordenadas; test de 250 incidencias (orden numérico `[2]` < `[10]`) |
| Cambiar un mensaje o un código de salida al pasar a argparse (argparse tiene sus propios mensajes y usa el código 2) | Los 22 casos de `ERRORES_DE_COMANDOS` y los 8 de `ERRORES_DE_VALIDAR` comparan el mensaje exacto. `cli.py` valida los argumentos con los mismos mensajes y no deja que argparse imprima los suyos |
| Aliasing: al copiar subesquemas en la fusión, cambiar el resultado | Tests de fusión y de `actualizar` (fusión sobre un esquema ya guardado) |
| Mover `datetime.now` y `time.perf_counter` a otros módulos rompe el fixture que los fija | Solo se cambia **dónde** fija el fixture `cli` la fecha y el cronómetro, nunca los valores esperados. Se revisa en el diff de cada commit |
| Sobre-refactorizar y cambiar conductas discutibles | Ver el apartado 5: esas conductas se conservan y cualquier cambio se decidiría aparte, con su propio commit `fix:` |

**Criterio de terminado:** los 80 tests originales en verde sin cambiar ningún valor esperado, el
test golden idéntico, `gestor.py` eliminado, y cobertura del paquete ≥ 70 % (objetivo: mantener
alrededor del 95 %).

---

## 5. Conductas actuales que se conservan (aunque sean discutibles)

La refactorización no cambia el comportamiento. Estas rarezas quedan anotadas por si se quiere
corregirlas después, en commits `fix:` aparte:

1. `registrar` rechaza un `--tipo` vacío o de espacios (270), pero `actualizar`, `mostrar` y
   `eliminar` solo comprueban que exista (329, 395, 427).
2. Los mensajes de error se imprimen por la salida estándar, no por la de errores.
3. Una opción sin valor (`--tipo` al final) da "argumento no reconocido" en lugar de "falta el valor".
4. `tipos` solo menciona el primer argumento sobrante (366).
5. Un archivo sin tipo sale como `valido = no`, pero no cuenta como error para el código de salida.
