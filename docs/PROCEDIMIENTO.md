# Procedimiento del pipeline rs-pipeline

Este documento explica, bloque por bloque, qué hace cada paso del pipeline, con qué datos, bajo qué
decisiones y con qué controles. Se añade una sección al cerrar cada bloque (regla de `CLAUDE.md`).
El flujo completo está en [flujograma.mmd](flujograma.mmd) y las decisiones en [decisiones.md](decisiones.md).

Reglas que valen para todos los bloques:
- El Drive es **solo lectura**. Los scripts leen de ahí y escriben únicamente dentro del repositorio.
- Los hashes de las entradas son los SHA-256 que registró cada script al cerrar el bloque. Si un archivo
  del Drive cambia, el hash cambia y el `.json` de trazabilidad de la siguiente corrida lo mostrará.
- Si falta un archivo, una columna o un ID, o un conteo no cuadra, el script **falla** con un mensaje claro
  (código de salida 1) y no escribe resultados.
- La ruta del Drive se indica con la variable `RS_DRIVE_ROOT` en `.env` (ver `.env.example`).

---

## Bloque 1 · Conteos PRISMA y diagrama (`prisma_02.py`)

Cierre: commits `f9731c0` y `087cb2c` (28 oct 2026).

### Objetivo del paso
Recalcular desde los CSV los conteos de la revisión sistemática (identificados → cribados → buscados →
evaluados → incluidos), compararlos con los conteos declarados en `prisma_counts_2026-10-26.json` y,
solo si todo cuadra, dibujar el diagrama PRISMA 2020 en español (al cerrar el bloque: 201 informes = 198 estudios; tras las exclusiones de nivel del [Bloque 4](#bloque-4--exclusiones-por-nivel-de-la-población-prisma_02py---derivar-counts): 196 = 193).

### Entradas
| Archivo (en el Drive, salvo `config/`) | Versión | SHA-256 |
|---|---|---|
| `01_busquedas/Registro_busquedas_PRISMA_v3.md` | v3 · 2026-10-06 | `4bbffb6f3423697a094a6e414d3cbc3aad80cb231be8042ff950ced661e811c7` |
| `02_cribado/Cribado_titulo_resumen_2026-10-06.csv` | 2026-10-06 | `81091c47afedde33efa460334c965ec2e97a0153b810557ff0c55b6bb88394c7` |
| `03_recuperacion/Recuperacion_textos_completos_2026-10-10.csv` | 2026-10-10 | `d97a430406dac743887a3fbb8875dda24dedf019b783d006a43b6c81ac46f70f` |
| `04_elegibilidad/Elegibilidad_texto_completo_v3_2026-10-26.csv` | v3 · 2026-10-26 | `c6b909bad0147bbe5b77b0324901bb769ee9f790e790366001715db3b92d4293` |
| `04_elegibilidad/Casos_dudosos_elegibilidad_v4_decididos_2026-10-26.csv` | v4 · 2026-10-26 | `2a63562ed8ca36a36f33aefba4275bf7282f60eb2a3b170fa2f86bbb3ae0ceae` |
| `05_extraccion/Extraccion_datos_v2_2026-10-18.csv` | v2 · 2026-10-18 | `cff8902b3de4f2f4fa5846d79db7c5f43dd6f529c393e0511a1f9875b6a8ff7d` |
| `06_prisma/prisma_counts_2026-10-26.json` | 2026-10-26 | `ee8d7b5282c0d4d108362319f8a3b352020e1be991eec4239ce0fa4209780af5` |
| `config/reclasificaciones.yaml` | repositorio | `4edfca04cc0134bac92d4c597d797ec39a5deadb9bf8dca27e6160b8143b7326` |
| `03_recuperacion/artículos_pdf/_no_corresponde/` (15 PDF) | sin versión | un hash por PDF, en el `.json` de trazabilidad |

### Proceso
Qué hace el script, en lenguaje sencillo:
1. Lee `RS_DRIVE_ROOT` de `.env` y abre los archivos del Drive en modo lectura. Calcula la huella (SHA-256) de cada uno.
2. Aplica en memoria seis cambios de decisión del cribado (D→E2, `config/reclasificaciones.yaml`); el CSV del Drive no se toca.
3. Cuenta los registros cribados, los excluidos por cada motivo (E1 a E5), los buscados en texto completo y los no recuperados.
   Los 137 no recuperados se desglosan en sin acceso (119), duplicado detectado en la recuperación (1), PDF de otro documento (15) e incompletos o ilegibles (2).
4. Cuenta los evaluados, los excluidos por motivo (sumando los 18 E4 de los casos dudosos) y los incluidos.
5. Compara cada número con el JSON y comprueba que cada etapa suma con la siguiente.
6. Agrupa los informes de la matriz de extracción en estudios con `estudio_compartido_con`: 201 informes son 198 estudios (3 pares).
7. Comprueba que los 15 informes de "PDF de otro documento" tengan su PDF separado o sean `NO_CORRESPONDE`.
8. Lee del Registro de búsquedas las fuentes (ERIC, SciELO, Scopus = 1.105; La Referencia, BDTD = 122) y comprueba que sumen 1.227.
9. Si todo cuadra, arma el diagrama con `prisma-flow`, reemplaza los textos por su versión en español, ajusta las alturas y escribe SVG, PNG y el archivo de trazabilidad.

Comando exacto (desde la raíz del repositorio):
```
.venv/bin/python src/rs_pipeline/prisma_02.py
```

### Decisiones aplicadas
- [D1](decisiones.md#d1-fuente-de-verdad-de-los-conteos) · Fuente de verdad de los conteos
- [D2](decisiones.md#d2-seis-reclasificaciones-d--e2) · Seis reclasificaciones D → E2
- [D3](decisiones.md#d3-identificados-1227-y-duplicados-124) · Identificados (1227) y duplicados (124)
- [D4](decisiones.md#d4-los-137-informes-no-recuperados) · Los 137 informes no recuperados
- [D5](decisiones.md#d5-casos-dudosos) · Casos dudosos
- [D6](decisiones.md#d6-herramientas-y-versiones) · Herramientas y versiones
- [D7](decisiones.md#d7-entorno-p2) · Entorno (P2)
- [D8](decisiones.md#d8-pip-audit) · pip-audit
- [D9](decisiones.md#d9-variable-del-drive) · Variable del Drive
- [D10](decisiones.md#d10-prisma_02py-p3) · prisma_02.py (P3)
- [D11](decisiones.md#d11-pdf-de-otro-documento) · PDF de otro documento
- [D12](decisiones.md#d12-estudios-198) · Estudios (198)
- [D13](decisiones.md#d13-sin-columna-de-otros-métodos) · Sin columna de "otros métodos"
- [D14](decisiones.md#d14-diagrama-p5) · Diagrama (P5)
- [D15](decisiones.md#d15-duplicado-separado-en-los-no-recuperados-cambio-de-especificación) · Duplicado separado en los no recuperados (cambio de especificación)
- [D16](decisiones.md#d16-ajustes-finales-del-diagrama) · Ajustes finales del diagrama

### Controles
Cuándo falla (cada caso termina con un mensaje que nombra el problema):
- Falta un archivo, una columna o `RS_DRIVE_ROOT`, o la carpeta indicada no existe.
- Hay IDs repetidos o un ID de recuperación, elegibilidad o dudosos que no está en la etapa anterior.
- Una reclasificación apunta a un ID que no existe o cuya decisión actual no es la esperada.
- Algún conteo calculado difiere del JSON, o alguna etapa no suma con la siguiente (el reporte lista cada diferencia y no se dibuja nada).
- Los informes no son 198 estudios, falta el PDF de un "PDF de otro documento", o las fuentes del Registro no coinciden con `params.yaml` ni suman 1.227.

Lo que **no** se verifica por script (dato declarado): los 1.227 identificados y los 124 duplicados, y la división en bases de datos y repositorios; vienen del Registro y del JSON ([D3](decisiones.md#d3-identificados-1227-y-duplicados-124)).

Observación que no es falla: 9 registros figuran como D en el cribado y como I en la recuperación; no afecta ningún conteo ([D10](decisiones.md#d10-prisma_02py-p3)).

Tests: `tests/test_prisma_02.py`, 17 pruebas contra los CSV reales: cada etapa suma con la siguiente, lo recalculado iguala al JSON,
el desglose de los 137, los 198 estudios con 3 pares, los 15 PDF, la división de las fuentes, y los casos en que debe fallar
(conteo alterado, reclasificación inconsistente, variable del Drive ausente, PDF sin respaldo, estudio compartido con informe ausente).
```
.venv/bin/pytest tests/test_prisma_02.py
```

### Salidas
En `outputs/figuras/` (dentro del repositorio, en git):
- `Diagrama_PRISMA_2020_Eje3_2026-10-26.svg` y `.png` (el PNG mide el doble que el SVG).
- `Diagrama_PRISMA_2020_Eje3_2026-10-26.json`: ruta y hash de cada entrada y de cada salida, versiones, conteos y avisos.
  Hash del SVG: `15bf82e57bd0cffa7491161ac68de995c316abaea5f4029e03bf588b049defcb`.
  Hash del PNG: `e29bdb023a50e499e4c601ccbb03fbd6fa78d8c5c5c5b2bf0625d09ad0e9ea98`.

El diagrama no lleva título: el número y el título van fuera de la imagen, en el Word (APA 7).

---

## Bloque 2 · Normalización de la matriz de extracción (`normalizar_01.py`)

Cierre: commits `6c8478e` y `5d2af49` (29 oct 2026). Ampliado el 29 oct con país y nivel (D25 a D27).

### Objetivo del paso
Dejar las columnas de texto libre de la matriz de extracción en categorías comparables (disciplina, categoría MMAT,
dirección del efecto, tipo de herramienta, tipo de resultado, país y nivel educativo), sin perder los valores
originales, para poder hacer descriptivos y análisis sobre los 201 informes incluidos.

### Entradas
| Archivo | Versión | SHA-256 |
|---|---|---|
| `05_extraccion/Extraccion_datos_v2_2026-10-18.csv` | v2 · 2026-10-18 | `cff8902b3de4f2f4fa5846d79db7c5f43dd6f529c393e0511a1f9875b6a8ff7d` |
| `04_elegibilidad/Casos_dudosos_elegibilidad_v4_decididos_2026-10-26.csv` | v4 · 2026-10-26 | `2a63562ed8ca36a36f33aefba4275bf7282f60eb2a3b170fa2f86bbb3ae0ceae` |
| `06_prisma/prisma_counts_2026-10-26.json` | 2026-10-26 | `ee8d7b5282c0d4d108362319f8a3b352020e1be991eec4239ce0fa4209780af5` |
| `config/categorias.yaml` | repositorio (D17–D22, D25–D27) | `cc4c790a59c4da994965eace66f959191b67f4d05f2cd11d26379666c59137d0` |

### Proceso
Qué hace el script, en lenguaje sencillo:
1. Lee la matriz de extracción v2 (219 filas) y los casos dudosos, y quita los 18 informes que se excluyeron por E4 en los dudosos. Quedan 201 informes.
2. Comprueba que 201 es el número que declara `prisma_counts`.
3. Para cada columna a normalizar mira el valor crudo en `config/categorias.yaml` y escribe la categoría aprobada en una columna nueva (`*_norm`).
   Las columnas con varias etiquetas posibles (herramientas y resultados) se separan en columnas 0/1; el texto de "otro" se guarda en una columna de detalle.
4. El **país** es el país donde se hizo el estudio según el texto (51 categorías, con "varios países" y "Chipre" para R1006).
   El **nivel** sigue lo que dice el texto del informe y no la etiqueta de la extracción (8 categorías); una columna marca los informes cuyo nivel toca la elegibilidad (30 al cerrar el bloque; 32 desde el Bloque 4) y otra, `nivel_dudoso`, los 6 de decisión incierta.
5. Las reglas de excepción aprobadas (resolución de problemas pasa a indagación/habilidades; conceptual autoinformado; covariables que no cuentan como resultado) se aplican y se cuenta cuántos casos tocan.
6. Escribe la matriz con las 58 columnas originales sin tocar más las 20 nuevas, y un archivo de trazabilidad con ruta y hash de cada entrada.

Comando exacto:
```
PYTHONPATH=src .venv/bin/python -m rs_pipeline.normalizar_01
```

### Decisiones aplicadas
- [D17](decisiones.md#d17-disciplina-9-valores--5-categorías) · Disciplina (9 valores → 5 categorías)
- [D18](decisiones.md#d18-mmat-categoría-6-valores--5-categorías) · MMAT categoría (6 valores → 5 categorías)
- [D19](decisiones.md#d19-dirección-del-efecto-11-valores--5-categorías) · Dirección del efecto (11 valores → 5 categorías)
- [D20](decisiones.md#d20-tipo-de-herramienta-multi-etiqueta) · Tipo de herramienta: multi-etiqueta
- [D21](decisiones.md#d21-tipo-de-resultado-multi-etiqueta-oe1_resultado_tipo) · Tipo de resultado: multi-etiqueta (oe1_resultado_tipo)
- [D22](decisiones.md#d22-columnas-nuevas-originales-conservadas) · Columnas nuevas, originales conservadas
- [D23](decisiones.md#d23-normalizar_01py-paso-b) · normalizar_01.py (Paso B)
- [D25](decisiones.md#d25-país-51-categorías) · País (51 categorías)
- [D26](decisiones.md#d26-r1006--chipre) · R1006 → Chipre
- [D27](decisiones.md#d27-nivel-según-el-texto-del-informe-8-categorías) · Nivel según el texto del informe (8 categorías)

### Controles
Cuándo falla:
- Falta un archivo o una columna necesaria, o un E4 de los dudosos no está en la matriz.
- No quedan exactamente los 201 informes que declara `prisma_counts`.
- Un valor crudo no está en `config/categorias.yaml` (el mensaje lo nombra con su frecuencia, y no se escribe ningún archivo). Vale también para país y nivel.
- Un segmento de `oe1_resultado_tipo` tiene una etiqueta desconocida, los paréntesis no cuadran o una fila se queda sin etiqueta.
- Las reglas de excepción no tocan exactamente los casos aprobados (3 reasignados, 3 autoinformados, 1 covariable).
- Una columna nueva ya existía, o la normalización cambia filas o columnas originales.

El nivel **no cambia el PRISMA ni excluye nada** por sí mismo: al cerrar este bloque `prisma_02.py` daba 201 informes = 198 estudios. Las exclusiones se aplican después, desde `config/exclusiones_nivel.yaml` (Bloque 4).

Tests: `tests/test_normalizar_01.py`, 13 pruebas contra la matriz real: se conservan las 201 filas y las columnas originales,
ningún valor queda sin mapear, los conteos de cada categoría (por ejemplo disciplina 90/70/22/14/5, 83 pre-post de un grupo,
51 países, 8 niveles y 32 informes en revisión), las columnas 0/1, las excepciones aprobadas, el hash de la fuente
en el archivo de trazabilidad, y los casos en que debe fallar.
```
.venv/bin/pytest tests/test_normalizar_01.py
```

### Salidas
En `data/processed/` (dentro del repositorio pero **fuera de git**, porque es un derivado del Drive que se regenera con el script):
- `Extraccion_datos_v2_2026-10-18_normalizada.csv`: 201 filas, 79 columnas (58 originales y 21 nuevas, con `nivel_dudoso` desde el Bloque 4).
- `Extraccion_datos_v2_2026-10-18_normalizada.json`: trazabilidad (ruta y hash de las entradas, los 18 IDs excluidos, columnas nuevas, frecuencias).
  Hash del CSV: `2a8c043f75d66e06f3e3adb4e5842bbf03f8811e78230e51fb34478006a672d6`.

---

## Bloque 3 · Descriptivos de la matriz (`descriptivos_03.py`)

Cierre: commits `2e74602` y `af2f11e` (29 oct 2026; hashes tras la reescritura del historial de [D30](decisiones.md#d30-salidas-con-texto-de-los-artículos-no-se-versionan)). Flujograma actualizado ([D29](decisiones.md#d29-flujograma-en-svg)).

### Objetivo del paso
Describir los 201 informes incluidos (año, idioma, país, nivel, disciplina, categoría MMAT, dirección del efecto,
herramientas, resultados y el cruce disciplina × herramienta) con n y %, e indicar dónde la base es de 198 estudios.
Además, listar los informes cuyo nivel educativo toca la elegibilidad, para que Luis Fer decida después.

### Entradas
| Archivo | Versión | SHA-256 |
|---|---|---|
| `data/processed/Extraccion_datos_v2_2026-10-18_normalizada.csv` | salida del bloque 2 | `2a8c043f75d66e06f3e3adb4e5842bbf03f8811e78230e51fb34478006a672d6` |
| `04_elegibilidad/Elegibilidad_texto_completo_v3_2026-10-26.csv` | v3 · 2026-10-26 (año de la base de datos) | `c6b909bad0147bbe5b77b0324901bb769ee9f790e790366001715db3b92d4293` |
| `06_prisma/prisma_counts_2026-10-26.json` | 2026-10-26 | `ee8d7b5282c0d4d108362319f8a3b352020e1be991eec4239ce0fa4209780af5` |
| `config/categorias.yaml` | repositorio (viaja en la matriz) | `cc4c790a59c4da994965eace66f959191b67f4d05f2cd11d26379666c59137d0` |

### Proceso
Qué hace el script, en lenguaje sencillo:
1. Lee la matriz normalizada de `data/processed/` y comprueba que su huella (SHA-256) es la que registró `normalizar_01`: si alguien la tocó, se detiene.
2. Comprueba que hay 201 informes (como declara `prisma_counts`) y los agrupa en 198 estudios con `estudio_compartido_con` (3 pares).
3. Comprueba que los informes de un mismo estudio coinciden en lo que se cuenta por estudio: disciplina, país, nivel y herramientas.
4. Toma el **año de la base de datos** (el registro buscado, en elegibilidad) y comprueba que cae en la ventana 2021–2026.
   El año APA queda en `cita_apa`; los 4 informes donde difieren se anotan en `anio.json`.
5. Calcula las frecuencias (n y %) de cada tabla. Las tablas de disciplina, país, nivel, herramientas y cruce agregan la base de 198 estudios.
6. Arma `revision_elegibilidad_nivel.csv` con los 32 informes cuyo nivel toca la elegibilidad. La columna `decision_luisfer` trae las decisiones de Luis Fer (D33): `incluir` salvo los 5 de `exclusiones_nivel.yaml`. Este CSV trae fragmentos de la extracción de los artículos: queda solo en tu disco (no se versiona, D30); en git va su `.json`.

Comando exacto:
```
PYTHONPATH=src .venv/bin/python -m rs_pipeline.descriptivos_03
```

### Decisiones aplicadas
- [D24](decisiones.md#d24-año-de-los-descriptivos-el-de-la-base-de-datos) · Año de los descriptivos: el de la base de datos
- [D25](decisiones.md#d25-país-51-categorías) · País (51 categorías)
- [D26](decisiones.md#d26-r1006--chipre) · R1006 → Chipre
- [D27](decisiones.md#d27-nivel-según-el-texto-del-informe-8-categorías) · Nivel según el texto del informe (8 categorías)
- [D28](decisiones.md#d28-revisión-de-elegibilidad-por-nivel) · Revisión de elegibilidad por nivel

La **regla 3** de elegibilidad, confirmada por Luis Fer el 29 oct 2026 ([D31](decisiones.md#d31-regla-3-de-elegibilidad-confirmada)):
*"Se incluyen los estudios con estudiantes de 2.º año universitario cuando el curso es todavía de ciencia básica o introductoria (p. ej., química general II, física para ciencias de la salud). Se excluyen los cursos avanzados o profesionalizantes (E1, población)."*

### Controles
Cuándo falla:
- Falta la matriz normalizada o su registro, o la matriz cambió desde que se normalizó.
- No hay 201 informes ni 198 estudios; un `estudio_compartido_con` no es recíproco; o los informes de un estudio no coinciden en disciplina, país, nivel o herramientas.
- Un año de la base de datos no se puede leer o cae fuera de 2021–2026; falta un informe en elegibilidad; o `cita_apa` no trae año.

Cada tabla de categoría única debe sumar 201 (lo verifica el test y queda en su `.json`); las de multi-etiqueta no suman 201 porque un informe puede estar en varias filas.
Cada tabla con su `.json`: base, hash de la matriz y de las entradas originales, hash de la salida.

Tests: `tests/test_descriptivos_03.py`, 21 pruebas: cada tabla de categoría única suma 201; las de estudio suman 198;
conteos reales (idioma, año, MMAT, herramientas, resultados); el cruce es coherente con las demás tablas; país y nivel;
el archivo de revisión (32 filas, columnas exactas, 27 incluir / 4 excluir E1 / 1 excluir E3, regla 3 citada); el PRISMA recalculado da 196 informes;
y los casos en que debe fallar (matriz modificada, estudio con informes distintos, socio no recíproco, año fuera de la ventana o ilegible).
```
.venv/bin/pytest tests/test_descriptivos_03.py
```

### Salidas
En `outputs/tablas/` (en git; son frecuencias, sin textos completos), cada una con su `.json`:

| Archivo | Contenido | Base |
|---|---|---|
| `anio.csv`, `anio_quinquenio.csv` | informes por año (de la base de datos) y por quinquenio | 201 informes |
| `idioma.csv` | idioma del informe | 201 informes |
| `pais.csv`, `nivel.csv` | país del estudio y nivel según el texto | 201 informes y 198 estudios |
| `disciplina.csv` | disciplina normalizada | 201 informes y 198 estudios |
| `mmat_categoria.csv` | categoría MMAT y cuántos son pre-post de un grupo | 201 informes |
| `oe1_direccion.csv` | dirección del efecto | 201 informes |
| `herramientas.csv` | tipo de herramienta (multi-etiqueta) | 201 informes y 198 estudios |
| `resultados.csv` | tipo de resultado (multi-etiqueta) | 201 informes |
| `disciplina_x_herramienta.csv` | cruce, % por fila | 201 informes y 198 estudios |
| `revision_elegibilidad_nivel.csv` (local, no versionado; `.json` sí) | 32 informes con la decisión de Luis Fer (D33); no cambia el PRISMA por sí solo | por informe |

## Bloque 4 · Exclusiones por nivel de la población (`prisma_02.py --derivar-counts`)

Cierre: 29 oct 2026 (los commits están en el historial de git, mensaje «Exclusiones por nivel…»). Flujograma actualizado.

### Objetivo del paso
Aplicar al PRISMA las decisiones de Luis Fer sobre la revisión de elegibilidad por nivel: 5 informes pasan de incluidos a excluidos
(4 por E1 población y 1 por E3 disciplina), sin tocar el Drive, y marcar con `nivel_dudoso` los 6 informes de decisión incierta
para el análisis de sensibilidad.

### Entradas
| Archivo | Versión | SHA-256 |
|---|---|---|
| `config/exclusiones_nivel.yaml` | repositorio · 2026-10-29 | `c25c9a9509f44478988c167dfbdb507f1c86b249d75b486ce1dc5182cb3285a2` |
| `06_prisma/prisma_counts_2026-10-26.json` (Drive, solo lectura) | 2026-10-26 (base) | `ee8d7b5282c0d4d108362319f8a3b352020e1be991eec4239ce0fa4209780af5` |
| `05_extraccion/Extraccion_datos_v2_2026-10-18.csv` (Drive) | v2 · 2026-10-18 | el hash de cada corrida queda en el `.json` del diagrama |
| `config/categorias.yaml` | repositorio (`ids_dudosos`, `ids_adicionales`) | `cc4c790a59c4da994965eace66f959191b67f4d05f2cd11d26379666c59137d0` |
| Los demás CSV del Drive del Bloque 1 | sin cambios | ver Bloque 1 |

### Proceso
Qué hace, en lenguaje sencillo:
1. `--derivar-counts` toma los conteos del 26 oct (Drive), suma las 5 exclusiones (informes incluidos −5, excluidos +5, E1 +4, E3 +1) y calcula cuántos estudios desaparecen (un informe de un par solo se excluye junto con su pareja).
   Escribe `config/prisma_counts_2026-10-29.json` en el repo; el del Drive no se modifica ni se sobrescribe.
2. `prisma_02.py` sin opciones recalcula todo desde los CSV, aplica las 5 exclusiones en memoria y lo contrasta con la versión nueva. Solo si todo cuadra dibuja el diagrama.
3. `normalizar_01.py` agrega `nivel_dudoso` y los 2 informes añadidos a la revisión; `descriptivos_03.py` completa `decision_luisfer` (32 filas).

Comandos exactos:
```
.venv/bin/python src/rs_pipeline/prisma_02.py --derivar-counts
.venv/bin/python src/rs_pipeline/prisma_02.py
PYTHONPATH=src .venv/bin/python -m rs_pipeline.normalizar_01
PYTHONPATH=src .venv/bin/python -m rs_pipeline.descriptivos_03
```

### Decisiones aplicadas
- [D31](decisiones.md#d31-regla-3-de-elegibilidad-confirmada) · Regla 3 de elegibilidad confirmada
- [D32](decisiones.md#d32-criterio-para-formación-docente) · Criterio para formación docente
- [D33](decisiones.md#d33-decisiones-de-la-revisión-de-elegibilidad-por-nivel) · Decisiones de la revisión por nivel (27 incluir · 4 E1 · 1 E3)

### Controles
Cuándo falla:
- Una exclusión no es un informe INCLUIDO en elegibilidad, ya es un E4 de dudosos, tiene un código fuera de E1–E5, un ID repetido o campos faltantes.
- Se excluye un informe de un par de estudio sin su pareja.
- Las exclusiones tienen fechas distintas, falta `prisma_counts_2026-10-29.json`, o el recálculo desde los CSV no coincide con él (o la cascada no suma): no se dibuja nada.
- Un ID de `ids_dudosos` o `ids_adicionales` no está en la matriz.

Tests: `tests/test_prisma_02.py` (23 pruebas; las nuevas verifican las 5 exclusiones, que ninguna comparte estudio, 196/193/99 y E1 = 32 / E3 = 3,
y los fallos esperados), `tests/test_normalizar_01.py` (`nivel_dudoso` = 6 IDs, 32 en revisión) y `tests/test_descriptivos_03.py` (32 filas y decisiones).
```
.venv/bin/pytest
```

### Salidas
| Archivo | Contenido | Dónde |
|---|---|---|
| `config/exclusiones_nivel.yaml` | las 5 exclusiones (id, código, motivo, decidido_por, fecha) | git |
| `config/prisma_counts_2026-10-29.json` | conteos vigentes: 196 informes, 193 estudios, 99 excluidos | git |
| `outputs/figuras/Diagrama_PRISMA_2020_Eje3_2026-10-29.{svg,png,json}` | diagrama PRISMA 2020 actualizado (el del 26 oct queda como versión anterior) | git |
| `revision_elegibilidad_nivel.csv` | 32 informes con `decision_luisfer` | local, no versionado (D30) |
| matriz normalizada (79 columnas, con `nivel_dudoso`) | | `data/processed/`, fuera de git |

**Pendiente de decisión:** las tablas del Bloque 3 siguen sobre los 201 informes; falta decidir si pasan a 196 informes y 193 estudios.
