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
originales, para poder hacer descriptivos y análisis sobre los informes incluidos (201 al cerrar el bloque; 196 tras las exclusiones de nivel, [D34](decisiones.md#d34-prisma_counts_2026-10-29json-es-la-fuente-de-verdad-del-prisma)).

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
2. Comprueba que 201 menos las exclusiones de nivel es el número de informes incluidos que declara `prisma_counts_2026-10-29.json` (196); los excluidos se marcan en `excluido_nivel` y `excluido_nivel_codigo`, no se borran (D34).
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
- 201 menos las exclusiones de nivel no da los informes incluidos que declara `prisma_counts_2026-10-29.json`, o una exclusión no está en la matriz.
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
- `Extraccion_datos_v2_2026-10-18_normalizada.csv`: 201 filas, 81 columnas (58 originales y 23 nuevas, con `nivel_dudoso` desde el Bloque 4 y `excluido_nivel` y su código desde D34).
- `Extraccion_datos_v2_2026-10-18_normalizada.json`: trazabilidad (ruta y hash de las entradas, los 18 IDs excluidos, columnas nuevas, frecuencias).
  Hash del CSV: `047840986e236173c915a1ce80a8d7decf690f49f64c3cbae7514b87d7b6bc85`.

---

## Bloque 3 · Descriptivos de la matriz (`descriptivos_03.py`)

Cierre: commits `2e74602` y `af2f11e` (29 oct 2026; hashes tras la reescritura del historial de [D30](decisiones.md#d30-salidas-con-texto-de-los-artículos-no-se-versionan)). Flujograma actualizado ([D29](decisiones.md#d29-flujograma-en-svg)).

### Objetivo del paso
Describir los 196 informes incluidos (año, idioma, país, nivel, disciplina, categoría MMAT, dirección del efecto,
herramientas, resultados y el cruce disciplina × herramienta) con n y %, e indicar dónde la base es de 193 estudios (D34).
Además, listar los informes cuyo nivel educativo toca la elegibilidad, para que Luis Fer decida después.

### Entradas
| Archivo | Versión | SHA-256 |
|---|---|---|
| `data/processed/Extraccion_datos_v2_2026-10-18_normalizada.csv` | salida del bloque 2 | `047840986e236173c915a1ce80a8d7decf690f49f64c3cbae7514b87d7b6bc85` |
| `04_elegibilidad/Elegibilidad_texto_completo_v3_2026-10-26.csv` | v3 · 2026-10-26 (año de la base de datos) | `c6b909bad0147bbe5b77b0324901bb769ee9f790e790366001715db3b92d4293` |
| `config/prisma_counts_2026-10-29.json` | 2026-10-29 (fuente de verdad, D34) | `af536e2c2ea7530b725436a0abfa1738a6e4a2fe9df95779f3bbd714034320c1` |
| `config/categorias.yaml` | repositorio (viaja en la matriz) | `cc4c790a59c4da994965eace66f959191b67f4d05f2cd11d26379666c59137d0` |

### Proceso
Qué hace el script, en lenguaje sencillo:
1. Lee la matriz normalizada de `data/processed/` y comprueba que su huella (SHA-256) es la que registró `normalizar_01`: si alguien la tocó, se detiene.
2. Quita los 5 informes con `excluido_nivel = 1`, comprueba que quedan 196 (como declara `prisma_counts_2026-10-29.json`) y los agrupa en 193 estudios con `estudio_compartido_con` (3 pares).
3. Comprueba que los informes de un mismo estudio coinciden en lo que se cuenta por estudio: disciplina, país, nivel y herramientas.
4. Toma el **año de la base de datos** (el registro buscado, en elegibilidad) y comprueba que cae en la ventana 2021–2026.
   El año APA queda en `cita_apa`; los 4 informes donde difieren se anotan en `anio.json`.
5. Calcula las frecuencias (n y %) de cada tabla. Las tablas de disciplina, país, nivel, herramientas y cruce agregan la base de 193 estudios.
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
- No hay 196 informes ni 193 estudios; un `estudio_compartido_con` no es recíproco; o los informes de un estudio no coinciden en disciplina, país, nivel o herramientas.
- Un año de la base de datos no se puede leer o cae fuera de 2021–2026; falta un informe en elegibilidad; o `cita_apa` no trae año.

Cada tabla de categoría única debe sumar 196 (lo verifica el test y queda en su `.json`); las de multi-etiqueta no suman 196 porque un informe puede estar en varias filas.
Cada tabla con su `.json`: base, hash de la matriz y de las entradas originales, hash de la salida.

Tests: `tests/test_descriptivos_03.py`, 23 pruebas: cada tabla de categoría única suma 196; las de estudio suman 193;
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
| `anio.csv`, `anio_quinquenio.csv` | informes por año (de la base de datos) y por quinquenio | 196 informes |
| `idioma.csv` | idioma del informe | 196 informes |
| `pais.csv`, `nivel.csv` | país del estudio y nivel según el texto | 196 informes y 193 estudios |
| `disciplina.csv` | disciplina normalizada | 196 informes y 193 estudios |
| `mmat_categoria.csv` | categoría MMAT y cuántos son pre-post de un grupo | 196 informes |
| `oe1_direccion.csv` | dirección del efecto | 196 informes |
| `herramientas.csv` | tipo de herramienta (multi-etiqueta) | 196 informes y 193 estudios |
| `resultados.csv` | tipo de resultado (multi-etiqueta) | 196 informes |
| `disciplina_x_herramienta.csv` | cruce, % por fila | 196 informes y 193 estudios |
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
| `config/prisma_counts_2026-10-29.json` | 2026-10-29 (fuente de verdad desde D34) | `af536e2c2ea7530b725436a0abfa1738a6e4a2fe9df95779f3bbd714034320c1` |
| `config/categorias.yaml` | repositorio (`ids_dudosos`, `ids_adicionales`) | `cc4c790a59c4da994965eace66f959191b67f4d05f2cd11d26379666c59137d0` |
| Los demás CSV del Drive del Bloque 1 | sin cambios | ver Bloque 1 |

### Proceso
Qué hace, en lenguaje sencillo:
1. `--derivar-counts` toma los conteos del 26 oct (Drive), suma las 5 exclusiones (informes incluidos −5, excluidos +5, E1 +4, E3 +1) y calcula cuántos estudios desaparecen (un informe de un par solo se excluye junto con su pareja).
   Escribe `config/prisma_counts_2026-10-29.json` en el repo; el del Drive no se modifica ni se sobrescribe.
2. `prisma_02.py` sin opciones recalcula todo desde los CSV, aplica las 5 exclusiones en memoria y lo contrasta con la versión nueva. Solo si todo cuadra dibuja el diagrama.
3. `normalizar_01.py` agrega `nivel_dudoso`, los 2 informes añadidos a la revisión y, sin borrar filas, `excluido_nivel` (0/1) y `excluido_nivel_codigo` (E1/E3) (D34).
4. `descriptivos_03.py` filtra los 5 excluidos, comprueba que quedan 196 informes y 193 estudios (como declara `prisma_counts_2026-10-29.json`), regenera las 11 tablas y completa `decision_luisfer` (32 filas).

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
- [D34](decisiones.md#d34-prisma_counts_2026-10-29json-es-la-fuente-de-verdad-del-prisma) · `prisma_counts_2026-10-29.json` es la fuente de verdad del PRISMA

### Controles
Cuándo falla:
- Una exclusión no es un informe INCLUIDO en elegibilidad, ya es un E4 de dudosos, tiene un código fuera de E1–E5, un ID repetido o campos faltantes.
- Se excluye un informe de un par de estudio sin su pareja.
- Las exclusiones tienen fechas distintas, falta `prisma_counts_2026-10-29.json`, o el recálculo desde los CSV no coincide con él (o la cascada no suma): no se dibuja nada.
- Un ID de `ids_dudosos` o `ids_adicionales` no está en la matriz.
- La matriz no tiene 196 informes con `excluido_nivel = 0` o no son los que declara `prisma_counts_2026-10-29.json`; o las tablas no suman 196 / 193.

Tests: `tests/test_prisma_02.py` (23 pruebas; las nuevas verifican las 5 exclusiones, que ninguna comparte estudio, 196/193/99 y E1 = 32 / E3 = 3,
y los fallos esperados), `tests/test_normalizar_01.py` (14 pruebas: `nivel_dudoso` = 6 IDs, 32 en revisión, 5 excluidos marcados y no borrados) y `tests/test_descriptivos_03.py` (23 pruebas: 32 filas y decisiones, tablas de 196 y 193, nivel sin los excluidos). En total, 60 pruebas.
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
| matriz normalizada (81 columnas; 201 filas con `excluido_nivel`) | | `data/processed/`, fuera de git |
| 11 tablas en `outputs/tablas/` | regeneradas sobre 196 informes / 193 estudios | git |

## Bloque 5 · Mini-sprint semántico: ¿sirve BERTopic con embeddings multilingües? (`semantico_04.py`)

Cierre: 31 oct 2026 (commits «Mini-sprint semántico…» en el historial de git). Flujograma actualizado.

### Objetivo del paso
Probar, antes de comprometerse, si BERTopic con embeddings multilingües funciona con este corpus: (Prueba 1) sobre trozos del
texto completo de 10 informes; (Prueba 2) sobre las fichas de los 196 informes, con todos los campos de OE1, OE2 y OE4 (2a) y solo
`oe2_*` (2b), el insumo del marco de criterios de diseño. Dos modelos (e5 principal y MiniLM de control), 5 semillas, y una
calificación a ciegas de Luis Fer. Todo local, sin llamadas a la API.

### Entradas
| Archivo | Versión | SHA-256 |
|---|---|---|
| `data/processed/Extraccion_datos_v2_2026-10-18_normalizada.csv` | salida del bloque 2 (196 incluidos + 5 `excluido_nivel`) | `047840986e236173c915a1ce80a8d7decf690f49f64c3cbae7514b87d7b6bc85` |
| `config/prisma_counts_2026-10-29.json` | 2026-10-29 (D34) | `af536e2c2ea7530b725436a0abfa1738a6e4a2fe9df95779f3bbd714034320c1` |
| `_trabajo/ext/txt/R####.txt` de 10 informes (Drive, solo lectura) | texto completo con referencias cortadas | el hash de cada uno queda en `outputs/semantico_metricas/prueba1_metricas.json` |
| `config/stopwords_semantico.yaml` | repositorio | `1677087a5c705bb0d8be175a84e7459be4cd4c9b2c8d955c2387dfc427c46774` |
| `requirements-semantico.txt` | 53 paquetes fijados (bertopic 0.17.4, sentence-transformers 6.2.0, torch 2.15.0, umap-learn 0.5.12, hdbscan 0.8.44) | `8a99295016c92eb9cb10616d059ea111b016ec896882f0f63740deb100454554` |
| `intfloat/multilingual-e5-base` (Hugging Face) | revisión `d128750597153bb5987e10b1c3493a34e5a4502a` | fijada por revisión (commit) |
| `paraphrase-multilingual-MiniLM-L12-v2` (Hugging Face) | revisión `e8f8c211226b894fcb81acc59f3b34ba3efd5f42` | fijada por revisión (commit) |
| `config/params.yaml` (sección `semantico`) | semillas, UMAP, umbrales, muestra, campos | hash en cada `.json` de métricas |

### Proceso
Qué hace, en lenguaje sencillo:
1. **Prepara las unidades.** Prueba 1: limpia el texto completo (corta en el marcador de referencias o en su encabezado, quita títulos,
   marcadores de página y encabezados repetidos, une las palabras cortadas con guion) y lo parte en trozos de ~150 palabras (e5) y ~90 (MiniLM)
   sin cortar oraciones: 408 y 624 trozos. Prueba 2: toma cada campo de la ficha, quita las marcas `[F]`/`[I]` y las citas de página,
   parte `oe2_criterios_candidatos` en un criterio por unidad y descarta lo de menos de 5 palabras: 3.608 unidades (2b: 2.176).
2. **Calcula embeddings** con cada modelo en la GPU del Mac (MPS) y, solo para la Prueba 1, también en CPU para comparar tiempo y resultado.
3. **Corre BERTopic** (UMAP + HDBSCAN) con 5 semillas por modelo y prueba, y calcula: ARI entre semillas, ARI entre modelos, % sin tema,
   coherencia NPMI contra la misma medida con asignaciones barajadas, y el reparto de cada tema (por idioma, informe, OE, disciplina y nivel).
4. **Hoja a ciegas.** Para la Prueba 2b toma la corrida de la semilla más representativa de cada modelo (20 temas de e5 y los 15 más grandes de MiniLM),
   mezcla las filas y reemplaza modelo y semilla por un código aleatorio. Luis Fer califica cada tema (interpretable / mixto / ruido); recién entonces
   se abre la tabla de traducción y se calcula el porcentaje por modelo.
5. **Veredicto** frente a los umbrales aprobados (`config/params.yaml`).

Comandos exactos (el venv se crea con `.venv/bin/python -m venv .venv-semantico` y `pip install -r requirements-semantico.txt`; los modelos se bajan
con `huggingface_hub.snapshot_download(repo_id, revision=…)` usando las revisiones de `params.yaml`):
```
PYTHONPATH=src .venv-semantico/bin/python -m rs_pipeline.semantico_04
PYTHONPATH=src .venv-semantico/bin/python -m rs_pipeline.semantico_04 --hoja-2b
PYTHONPATH=src .venv/bin/python -m rs_pipeline.semantico_04 --calificacion-2b
```

### Decisiones aplicadas
- [D35](decisiones.md#d35-mini-sprint-semántico-diseño-de-las-pruebas) · Diseño de las pruebas y umbrales
- [D36](decisiones.md#d36-análisis-de-sensibilidad-por-modelo-de-embeddings) · Análisis de sensibilidad por modelo de embeddings
- [D37](decisiones.md#d37-los-temas-sobre-fichas-agrupan-la-extracción-no-el-texto-original) · Los temas sobre fichas agrupan la extracción, no el texto original
- [D38](decisiones.md#d38-hoja-de-calificación-a-ciegas-solo-prueba-2b) · Hoja de calificación a ciegas (solo Prueba 2b)
- [D39](decisiones.md#d39-resultado-de-las-corridas-y-veredicto-automático-provisional) · Resultado de las corridas y veredicto automático
- [D40](decisiones.md#d40-calificación-a-ciegas-de-la-prueba-2b-y-veredicto-final) · Calificación a ciegas de la Prueba 2b y veredicto final

### Controles
Cuándo falla (código 1 y mensaje claro):
- La matriz normalizada cambió desde que se normalizó, no tiene las columnas de la ficha, o sus informes incluidos no son los 196 de `prisma_counts_2026-10-29.json`.
- Un informe de la Prueba 1 no está entre los incluidos, no tiene idioma válido, no existe su texto, no se encuentra su sección de referencias o no queda ningún trozo.
- Las dos asignaciones que se comparan (ARI) no tienen el mismo largo.
- Al repetir la corrida de la hoja a ciegas, las asignaciones no son las guardadas; o la hoja ya tiene calificaciones (no se sobrescribe).
- Una calificación no es interpretable / mixto / ruido, o la hoja y la traducción no tienen los mismos códigos.

Tests: `tests/test_semantico.py` (27 pruebas: ARI con valores conocidos, NPMI, limpieza y trozos sin cortar oraciones, y los números reales: 5 inglés / 3 español /
2 portugués, 408 y 624 trozos, 3.608 unidades) y `tests/test_semantico_salidas.py` (recalculan ARI con una fórmula independiente, comprueban la hoja a ciegas,
la traducción, la calificación 29/6/0 y que lo versionado no traiga texto). Total del proyecto: 111 pruebas.
```
.venv/bin/pytest
```

### Salidas
| Archivo | Contenido | Dónde |
|---|---|---|
| `outputs/semantico_metricas/prueba1_metricas.json`, `prueba2a_…`, `prueba2b_…` | todas las métricas numéricas, por corrida, semilla y modelo | git (solo números) |
| `outputs/semantico_metricas/prueba2b_calificacion.json` | % interpretables / mixtos / ruido por modelo y veredicto final, con hashes de la hoja y la traducción | git |
| `outputs/semantico_metricas/veredicto.json` | criterios por prueba y modelo, y veredicto final de la 2b | git |
| `outputs/semantico/hoja_calificacion_ciega_2b.csv` (+ `_sin_calificar_respaldo.csv`) y `traduccion_codigos_2b.csv` | hoja con fragmentos de las fichas y su traducción de códigos | local, ignorado |
| `outputs/semantico/asignaciones_*.csv` | tema de cada unidad por prueba, modelo y semilla (sin texto) | local, ignorado |

**Resultado:** la Prueba 1 (texto completo) no sirve para la síntesis (más de 50 % de los temas son «de un documento»); la Prueba 2b (fichas `oe2_*`) sigue con los dos modelos.



## Bloque 6 · Marco de criterios v0 y cruce con la evidencia (`criterios_05.py`)

Cierre: 31 oct 2026. Flujograma actualizado.

### Objetivo del paso
Pasar de los 20 temas de e5 (Prueba 2b) a un marco de 9 criterios de diseño con texto de Luis Fer, y cruzar cada criterio con la evidencia: cuántas unidades, informes y estudios lo sostienen, con qué calidad y diseño, en qué nivel y disciplina, con qué dirección del efecto, y cuánto dice solo que el estudio «no reporta».

### Entradas
| Archivo | Versión | SHA-256 |
|---|---|---|
| `data/processed/Extraccion_datos_v2_2026-10-18_normalizada.csv` | salida del bloque 2 | `047840986e236173c915a1ce80a8d7decf690f49f64c3cbae7514b87d7b6bc85` |
| `config/criterios_v0.yaml` | marco v0 (D42) | `5df40f492afdbb69063dc1524125c9d92233a00cf898023c8c5dd4f039d5a21f` |
| `outputs/semantico/asignaciones_prueba2b_principal_s4.csv` | e5, semilla medoide 4 (local) | `8ce70164250779b98b3f5be6c83fb4e56b4cb98c190fd12d08b6dc7246cca221` |
| `config/prisma_counts_2026-10-29.json` | 196 informes / 193 estudios | `af536e2c2ea7530b725436a0abfa1738a6e4a2fe9df95779f3bbd714034320c1` |

### Proceso
1. Paso 1: `semantico_04 --hoja-nombrar-2b` genera la hoja de los 20 temas; Luis Fer los nombra sin ver propuestas; Claude propone sus nombres aparte y se compara el acuerdo (8 de 9 temas nombrados coinciden en sustancia).
2. Paso 2: Luis Fer decide el marco (9 criterios, D42) y el peso de la evidencia (D43). `criterios_05.py` calcula los pesos A, B y C de cada informe, los combina (suma y mínimo), asigna estudios, cruza cada criterio con sus unidades, separa las unidades «no reporta» y busca los 5 candidatos más parecidos a cada enunciado.
```
PYTHONPATH=src .venv-semantico/bin/python -m rs_pipeline.criterios_05
PYTHONPATH=src .venv-semantico/bin/python -m rs_pipeline.criterios_05 --ejemplos   # ejemplos de C09 (local)
```

### Decisiones aplicadas
- [D41](decisiones.md#d41-bloque-6-paso-1-nombrar-los-temas-de-la-prueba-2b-e5) · Nombrar los temas; regla A/B/C
- [D42](decisiones.md#d42-bloque-6-paso-2-marco-de-criterios-v0-decisiones-de-luis-fer-sobre-los-20-temas-de-e5) · Marco de criterios v0
- [D43](decisiones.md#d43-bloque-6-paso-2-e-peso-de-la-evidencia-y-cruce-de-los-criterios-con-los-estudios) · Peso de la evidencia y cruce

### Controles
Falla (código 1) si la matriz cambió o no tiene los 196 informes / 193 estudios, si un informe no tiene 5 ítems MMAT con Sí / No / No se puede saber, si una dirección del efecto o un nivel es desconocido, o si las asignaciones guardadas no corresponden a las unidades actuales de las fichas.
Tests: `tests/test_criterios.py` (reglas con casos a mano; MMAT 28 alta / 49 media / 119 baja recalculado; unidades, informes y estudios de cada criterio recalculados desde las asignaciones; los repartos suman). Total del proyecto: 129 pruebas.

### Salidas
| Archivo | Contenido | Dónde |
|---|---|---|
| `outputs/tablas/criterios_v0_evidencia.csv/.json` | por criterio: n de unidades, informes y estudios; peso (suma y mínimo); sensibilidad; nivel; disciplina; dirección; «no reporta» | git |
| `outputs/tablas/criterios_v0_reporte_por_campo.csv` | por campo de ficha, informes donde el campo entero no reporta | git |
| `outputs/tablas/mmat_items_por_informe.csv/.json` | respuestas MMAT ítem por ítem, para el anexo | git |
| `outputs/semantico/criterios_v0_*.csv`, `propuestas_nombres_claude_2b_e5.csv` | IDs, ejemplos, 5 candidatos por criterio, propuestas de nombres (con texto) | local, ignorado |


## Bloque 7 · Libro de códigos y piloto de codificación deductiva (`codificacion_06.py`)

Cierre del diseño: 31 oct 2026. Sin llamadas a la API. Flujograma actualizado.

### Objetivo del paso
Medir evidencia real (no cobertura de campos) codificando cada informe frente a cada criterio. Este paso solo diseña el libro de códigos, elige las muestras y arma la hoja del piloto, y estima el costo de codificar los 196 informes.

### Entradas
| Archivo | Versión | SHA-256 |
|---|---|---|
| `config/criterios_v0.yaml` | marco v0 (D42) | `5df40f492afdbb69063dc1524125c9d92233a00cf898023c8c5dd4f039d5a21f` |
| `data/processed/Extraccion_datos_v2_2026-10-18_normalizada.csv` | salida del bloque 2 | `047840986e236173c915a1ce80a8d7decf690f49f64c3cbae7514b87d7b6bc85` |
| `config/params.yaml` (sección `codificacion`) | semilla, campos, precios | en git |

### Proceso
`codificacion_06.py` escribe el libro de códigos desde el marco, calcula el peso de cada informe (D43), sortea con semilla fija el piloto (5 informes variados) y la muestra de confiabilidad (40, estratificada por peso y nivel), limpia los 19 campos de la ficha de los 5 del piloto (sin marcas [F]/[I] ni citas de página) y estima los tokens y el costo con la Batch API y el caché.
```
PYTHONPATH=src .venv-semantico/bin/python -m rs_pipeline.codificacion_06
```

### Decisiones aplicadas
- [D44](decisiones.md#d44-bloque-7-libro-de-códigos-y-codificación-deductiva-piloto) · Libro de códigos, campos, muestras, costo

### Controles
Falla (código 1) si `criterios_v0.yaml` no trae C01–C09 en orden, si falta una columna de la ficha, si no hay un piloto variado, o si la hoja del piloto ya tiene códigos o notas (no se sobrescribe).
Tests: `tests/test_codificacion.py` (8 pruebas). Total del proyecto: 137 pruebas.

### Salidas
| Archivo | Contenido | Dónde |
|---|---|---|
| `config/libro_codigos_v0.yaml`, `docs/libro_codigos_v0.md` | libro de códigos v0 (escala, reglas, campos, criterios, ejemplos inventados) | git |
| `outputs/tablas/costo_codificacion_estimado.json` | tokens y USD estimados para los 196 informes | git |
| `outputs/semantico/hoja_codificacion_piloto.csv` y `_correspondencia.csv` | hoja ciega P01–P05 con los 19 campos y su correspondencia | local, ignorado |
| `outputs/semantico/muestra_confiabilidad_40.csv` | lista de 40 informes | local, ignorado |

### Bloque 7, paso 2 · Piloto codificado, libro v1 y acuerdo con Claude Code (`codificacion_claude.py`)
- **Qué se hizo:** Luis Fer codificó el piloto (5 informes × 9 criterios). Con sus tres reglas nuevas (D45) se escribió el libro v1 (`python -m rs_pipeline.codificacion_06 --libro-v1`). Claude Code codificó los mismos 5 informes leyendo solo las fichas y dejó una línea por informe en `logs/codificacion_claude.jsonl` (D46). Comando para registrar un lote: `PYTHONPATH=src .venv/bin/python -m rs_pipeline.codificacion_claude --registrar lote.json`; para comparar: `… -m rs_pipeline.codificacion_claude`.
- **Resultado:** acuerdo 71,1 % (32 de 45), kappa ponderado cuadrático 0,548; orientativo (5 informes) y no ciego.
- **Controles:** falla si un código no es 0, 1 o 2, si faltan criterios o justificaciones, si la hoja no tiene los nueve códigos de Luis Fer, o si la hoja y el registro no tienen los mismos informes. Tests: 144 en total.
- **Salidas:** `outputs/tablas/acuerdo_piloto_luisfer_claude.csv/.json` (git); `logs/` y `outputs/semantico/` (ignorados).

### Bloque 7, paso 3 · Libro v2 y muestra de 40 sin anclaje (D47)
- **Qué se hizo:** el piloto queda fuera de la confiabilidad; libro v2 (`codificacion_06 --libro-v2`); hoja de la muestra de 40 (`codificacion_06 --hoja-40`); protocolo para que la codificación de Claude se haga en una sesión nueva, sin ver los códigos del piloto (`docs/protocolo_codificacion_ciega.md`).
- **Comando de la sesión nueva (registrar un lote):** `PYTHONPATH=src .venv/bin/python -m rs_pipeline.codificacion_claude --registrar outputs/semantico/lote_codificacion_40.json --hoja hoja_codificacion_40.csv --libro v2`.
- **Controles:** falla si el lote no trae exactamente los informes de la hoja, si un código no es 0, 1 o 2, o si falta una justificación de una línea; la hoja de 40 no se sobrescribe si ya tiene códigos. Tests: 149 en total.
- **Salidas:** `config/libro_codigos_v2.yaml`, `docs/libro_codigos_v2.md`, `docs/protocolo_codificacion_ciega.md`, `outputs/tablas/codificacion_claude_resumen.json` (git); hoja, correspondencia, registro y códigos de Claude (ignorados).

### Bloque 7, paso 4 · Confiabilidad de la muestra de 40 (D48)
- **Qué se hizo:** se comparan los códigos de Luis Fer (`codigos_luisfer_40.csv`) con los de Claude (registro, libro v2) por criterio y en total.
- **Comando:** `PYTHONPATH=src .venv/bin/python -m rs_pipeline.confiabilidad_40`.
- **Controles:** falla si falta el archivo de Luis Fer o una columna, si un código no es 0, 1 o 2, o si los dos no tienen exactamente los mismos 40 informes con el libro v2. Tests: 153 en total.
- **Salidas:** `outputs/tablas/confiabilidad_40.csv/.json` (git, con hash de las entradas); desacuerdos con justificaciones en `outputs/semantico/` (ignorado).

### Bloque 7, paso 5 · Confiabilidad de presencia (D49)
- **Qué se hizo:** la escala principal pasa a presencia (0 frente a 1 o 2); se recalculan acuerdo, kappa de Cohen y AC1 de Gwet por criterio y total, con IC bootstrap (mismo comando que el paso 4).
- **Controles:** los de D48; además el test compara la salida publicada con la tabla de códigos (conteo de códigos 2 y criterios con AC1 ≥ 0,60). Tests: 155 en total.
- **Salidas:** `outputs/tablas/confiabilidad_40_presencia.csv/.json` (git); desacuerdos de presencia en `outputs/semantico/` (ignorado).

### Bloque 7, paso 6 · Libro v3, verificación de presencia y hoja de 196 (D50)
- **Qué se hizo:** libro v3 (presencia 0/1, listas «cuenta / no cuenta»), hoja de 20 informes nuevos para que Luis Fer verifique C05, C06 y C08, hoja de los 196 repartida en cuatro lotes y registro de lotes parciales. No se codificó ningún informe.
- **Comandos:** `PYTHONPATH=src .venv/bin/python -m rs_pipeline.codificacion_06 --libro-v3`, `… --hoja-presencia-20` y `… --hoja-196`. Registrar el lote N: `PYTHONPATH=src .venv/bin/python -m rs_pipeline.codificacion_claude --registrar outputs/semantico/lote_codificacion_196_loteN.json --hoja hoja_codificacion_196.csv --libro v3 --lote N`.
- **Controles:** falla si el lote no trae exactamente los informes del lote N, si un código no es 0 o 1 (en v3), si un lote pasaría de 50 informes, si se intenta reescribir un libro histórico (v0 a v2) o si una hoja ya tiene códigos. Tests: 168 en total.
- **Salidas:** `config/libro_codigos_v3.yaml`, `docs/libro_codigos_v3.md`, `docs/protocolo_codificacion_ciega.md` (git); hojas, correspondencias y lotes en `outputs/semantico/` (ignorados).

### Bloque 7, paso 7 · Verificación de C05, C06 y C08 en 20 informes (D51, `verificacion_presencia_20.py`)
- **Objetivo del paso:** saber si los códigos de Claude de C05, C06 y C08 en los 196 informes (libro v3) se pueden dar por validados, comparándolos con los que Luis Fer codificó a ciegas en 20 informes nuevos.
- **Entradas:** `outputs/semantico/codigos_luisfer_presencia_20.csv`, `hoja_codificacion_presencia_20_correspondencia.csv` y `hoja_codificacion_196_correspondencia.csv` (locales, ignorados); `config/libro_codigos_v3.yaml` (`c1f7eeb6…`); `logs/codificacion_claude.jsonl`. Los hashes de cada archivo quedan en `outputs/tablas/verificacion_presencia_20.json`.
- **Proceso:** convierte cada V en su id real y ese id en su T, comprueba que los 20 estén entre los 196, toma los códigos de Claude y calcula por criterio % de acuerdo, kappa de Cohen, AC1 de Gwet (IC 95 % por bootstrap de informes) y prevalencia de cada codificador. Si el AC1 es ≥ 0,60 el criterio queda validado; si no, escribe la lista de desacuerdos y una hoja de adjudicación para que Luis Fer decida.
  ```
  PYTHONPATH=src .venv/bin/python -m rs_pipeline.verificacion_presencia_20
  ```
- **Decisiones aplicadas:** [D49](decisiones.md#d49-la-escala-principal-pasa-a-ser-la-presencia-0-frente-a-1-o-2) (presencia y AC1) · [D50](decisiones.md#d50-libro-v3-presencia-01-verificación-de-c05-c06-y-c08-y-codificación-de-los-196) (umbral AC1 ≥ 0,60) · [D51](decisiones.md#d51-verificación-de-c05-c06-y-c08-en-20-informes-luis-fer-frente-a-claude-libro-v3) (resultado).
- **Controles:** falla si falta un archivo o una columna, si las correspondencias no tienen 20 y 196 informes, si un informe de los 20 no está entre los 196, si el registro no trae los 196 con el libro v3, si un código no es 0 o 1, o si la hoja de adjudicación ya tiene códigos finales. Tests: `tests/test_verificacion_presencia_20.py` (5 pruebas); 173 en total.
- **Resultado:** AC1 0,252 (C05), −0,496 (C06) y −0,224 (C08); ninguno alcanza 0,60. Los 37 desacuerdos van todos en un sentido (Luis Fer 1, Claude 0). Queda pendiente la adjudicación de Luis Fer.
- **Salidas:** `outputs/tablas/verificacion_presencia_20.csv/.json` (git, solo números); `outputs/semantico/desacuerdos_presencia_20_luisfer_claude.csv` y `adjudicacion_presencia_20.csv` (ignorados).

### Bloque 7, paso 8 · Definición estricta y cierre de la adjudicación (D52, `adjudicacion_d52.py`)
- **Objetivo del paso:** dejar decididos los 37 desacuerdos de D51 sin revisarlos uno a uno, y separar los pocos que sí necesitan la mirada de Luis Fer.
- **Entradas:** `outputs/semantico/adjudicacion_presencia_20_lector.csv` (local, ignorado; no se modifica), ambas correspondencias, `config/libro_codigos_v3.yaml` (`c1f7eeb6…`) y `logs/codificacion_claude.jsonl`. Hashes en `outputs/tablas/calibracion_presencia_20.json`.
- **Proceso:** A01 y A02 quedan en 0 (decididos por Luis Fer). En los otros 35, si la ficha contiene un término de la lista «cuenta» del criterio el caso pasa a «revisar»; si no, queda en 0 con la regla D52. También cuenta cuántos informes de C05 con desacuerdo tienen C03 = 1 en Claude y calcula la prevalencia amplia, literal y final.
  ```
  PYTHONPATH=src .venv/bin/python -m rs_pipeline.adjudicacion_d52
  ```
- **Decisiones aplicadas:** [D51](decisiones.md#d51-verificación-de-c05-c06-y-c08-en-20-informes-luis-fer-frente-a-claude-libro-v3) · [D52](decisiones.md#d52-definición-estricta-de-c05-c06-y-c08-y-cierre-de-la-adjudicación).
- **Controles:** falla si falta un archivo o una columna, si la hoja del lector no trae los 37 casos, si el registro no trae los 196 con el libro v3, o si `adjudicacion_revisar.csv` ya tiene decisiones de Luis Fer (no se sobrescribe). Tests: `tests/test_adjudicacion_d52.py`; 177 en total.
- **Resultado:** 2 decididos por Luis Fer, 20 en 0 por la regla D52 y **15 a revisar** (C05 3, C06 4, C08 8). Claude codificó C03 = 1 en 4 de los 9 informes de C05 con desacuerdo.
- **Salidas:** `outputs/tablas/calibracion_presencia_20.csv/.json` (git); `adjudicacion_presencia_20_cierre.csv` y `adjudicacion_revisar.csv` en `outputs/semantico/` (ignorados).
