# Decisiones del pipeline

Registro de decisiones de Luis Fer (28 oct 2026). Cada una indica su fuente.

## D1. Fuente de verdad de los conteos
`06_prisma/prisma_counts_2026-10-26.json` (E2=347, 671 excluidos en cribado, 432 buscados).

## D2. Seis reclasificaciones D → E2
R0843, R0907, R0945, R0980, R1020, R1067 quedaron como D en el cribado del 06 oct y luego se
reclasificaron a E2 sin actualizar el CSV. No se edita el Drive: se aplican desde
`config/reclasificaciones.yaml`. Cualquier otra diferencia entre CSV y JSON debe hacer fallar el script.

## D3. Identificados (1227) y duplicados (124)
Se toman del JSON como dato declarado; no se recalculan desde los CSV de búsqueda
(faltan los `.ris` y no hay B03). Fuente: `01_busquedas/Registro_busquedas_PRISMA_v3.md`.

## D4. Los 137 informes no recuperados
Van todos en la caja "Informes no recuperados" (definición del checkpoint del Eje 3):
- Sin acceso: 120 = 119 con `obtenido=no` + 1 duplicado detectado tarde.
- PDF de otro documento: 15 = 10 `NO_CORRESPONDE` + 5 con `obtenido=sí` sin fila en elegibilidad.
- Incompletos/ilegibles: 2 (`NO_RECUPERADO`).

El reporte del script lista los IDs de los 5 sin fila en elegibilidad para revisión de Luis Fer.

## D5. Casos dudosos
`decision_luisfer = ok` significa "acepto la sugerencia automática". Los 18 E4 de los dudosos son
las filas con `sugerencia_automatica` que empieza por "Excluir E4" (17 `ok` + R0012 `excluir`).

## D6. Herramientas y versiones
- `py-prisma` no existe en PyPI. Se usa `prisma-flow` 0.6.1 (BSD-3, compatible con MIT).
  Dependencias de ejecución que trae: `pydantic>=2` y `resvg>=0.2.0`.
- Python 3.13 y pandas 2.3.3 (no pandas 3 por ahora).
- Script de PRISMA: `src/rs_pipeline/prisma_02.py`.

## D7. Entorno (P2)
- `pip` del venv actualizado a 26.2.2 (la 25.2 traía vulnerabilidades según pip-audit; no está en requirements.txt).
- `requirements.txt` fija solo los paquetes directos; sus dependencias (numpy, pydantic, resvg, etc.) las resuelve pip.
- Hooks de pre-commit locales (ruff del venv y gitleaks de brew) para no descargar segundas versiones.
- `ruff.toml` ignora S101 (assert) solo en `tests/`.

## D8. pip-audit
Se cambia la regla de `CLAUDE.md`: pip-audit se corre cada vez que cambie `requirements.txt` y antes de cada push (no antes de cada commit ni como hook, porque depende de red).

## D9. Variable del Drive
`RS_DRIVE_ROOT` va en `.env` (ignorado por git; plantilla en `.env.example`). El script la lee con un lector mínimo propio, sin python-dotenv.

## D10. prisma_02.py (P3)
- Las reclasificaciones se validan: el ID debe existir y su decisión actual debe ser la de `de`; si no, el script falla.
- Observación sin efecto en los conteos: 9 registros están como D en el cribado y como I en recuperación (I/D no entra en PRISMA). Solo se reporta. Coincide con el Registro v3 ("se reclasificaron 15: 9 a I y 6 a E2"): los 6 a E2 están en `config/reclasificaciones.yaml` (D2) y los 9 a I solo cambian la etiqueta I/D.
- `identificados` y `duplicados` quedan como declarados, sin verificar (ver D3). El 198 sí se verifica (D12).

## D11. PDF de otro documento
Todo informe contado como "PDF de otro documento" (15) debe ser `NO_CORRESPONDE` en elegibilidad o tener su PDF en `03_recuperacion/artículos_pdf/_no_corresponde/`; si no, el script falla. Los 5 sin fila en elegibilidad (R0008, R0051, R0905, R0934, R0973) fueron revisados por Luis Fer y sus PDF están en esa carpeta. La carpeta tiene 15 PDF, igual que los contados. El script registra el SHA-256 de cada PDF en el reporte; los PDF no se suben a git.

## D12. Estudios (198)
Se verifican por script con `estudio_compartido_con` de `Extraccion_datos_v2_2026-10-18.csv`, excluyendo los 18 E4 de los dudosos: 201 informes = 198 estudios con 3 pares (R0177+R0188, R0844+R0930, R0990+R1031). Los IDs de extracción deben ser iguales a los INCLUIDOS de elegibilidad (219). Si no cuadra, falla.

## D13. Sin columna de "otros métodos"
El diagrama usa solo la columna de bases de datos y repositorios. El rastreo de referencias no agregó estudios a esta versión, así que no se dibuja la columna de otros métodos (sitios web, organizaciones, citas).

## D14. Diagrama (P5)
- Se construye con `prisma-flow` 0.6.1: `new_review(...).validate()` y `to_layout()`; luego se reemplazan los textos de cada caja por ID, en español, y se recalculan las posiciones para cajas más altas (desgloses E1–E5 y de los no recuperados). Las etiquetas de E1–E5 y de los no recuperados están en `config/params.yaml`.
- Identificación: 1.105 bases de datos (ERIC 707 + SciELO 53 + Scopus 345) y 122 repositorios de tesis (La Referencia 85 + BDTD 37). Se leen de la línea "Total identificado" del Registro v3 (dato declarado) y deben sumar los 1.227 del JSON.
- `PNGRenderer(scale=2)` recorta la imagen (agranda el dibujo pero no el lienzo). El PNG se rasteriza con `resvg` ampliando `width` y `height` del SVG. `resvg==0.2.0` ya venía instalado con prisma-flow y ahora se fija en `requirements.txt` porque se importa directamente.
- Aviso esperado de prisma-flow: 198 estudios frente a 201 informes (un estudio puede tener varios informes; ver D12).
- Nombre de salida: `Diagrama_PRISMA_2020_Eje3_<fecha del JSON de conteos>`. El archivo `.json` hermano guarda hashes de entradas y salidas, versiones y conteos.

## D15. Duplicado separado en los no recuperados (cambio de especificación)
Decidido por Luis Fer (28 oct 2026). Reemplaza el desglose de D4: el duplicado detectado tarde (R1042) deja de sumarse a "sin acceso". Desglose de los 137: sin acceso 119 (`obtenido=no`) + duplicado detectado en la recuperación 1 + PDF de otro documento 15 + incompletos o ilegibles 2. Total sin cambios. El test del desglose y el del texto del diagrama se actualizaron por este cambio de especificación, no para forzarlos a verde.

## D16. Ajustes finales del diagrama
- Sin título dentro de la imagen: en APA 7 el número y el título van fuera, en el Word. El SVG conserva un `<title>` interno (accesibilidad) en español.
- Banda superior: "Identificación de estudios a través de bases de datos y repositorios" (revisión nueva, no actualización).

## Deuda técnica
- `prisma_02.alto_texto` llama a `SVGRenderer._max_chars` (método privado de prisma-flow) para calcular cuántas líneas ocupa cada texto y así dar altura a las cajas. Si prisma-flow cambia ese método, el cálculo puede fallar o desajustarse. Mitigación: versión fijada en 0.6.1 y un test que genera el diagrama completo. Alternativa si molesta: copiar la fórmula `(ancho - 28) / 6,1` en el propio script.
- `rasterizar_png` usa `resvg` directamente porque `PNGRenderer(scale=...)` recorta la imagen (ver D14).

# Bloque: normalización de la matriz de extracción (29 oct 2026)
Insumo: `05_extraccion/Extraccion_datos_v2_2026-10-18.csv` sin los 18 E4 de los dudosos (201 informes). Mapeo en `config/categorias.yaml`.

## D17. Disciplina (9 valores → 5 categorías)
física 90, química 70, biología 22, ciencias integradas 14, otra 5. Bioquímica va en química. Las integradas con matemáticas van en ciencias integradas. "Ciencias de la Tierra y ambientales" va en ciencias integradas (el área MEN es "Ciencias naturales y educación ambiental"); por eso "otra" queda en 5 informes.

## D18. MMAT categoría (6 valores → 5 categorías)
Se fusiona la categoría 3 (83 con "incluye pre-post de un grupo" + 26 sin la marca = 109). Columna nueva `pre_post_un_grupo` (0/1) = 1 en los 83 con la marca.

## D19. Dirección del efecto (11 valores → 5 categorías)
no comparativo 76, favorable a la simulación 63, mixto 50, sin diferencia 11, "otro (comparación dentro de la misma simulación)" 1. Los dos "paquete" quedan en favorable con `efecto_aislado` = 0; los otros 61 favorables tienen 1; vacío en el resto. "Mixto" con matiz queda en mixto. No hay valores "desfavorable" (aunque el protocolo lo prevé): si aparece uno, el script falla.

## D20. Tipo de herramienta: multi-etiqueta
Sin categoría "combinada". Una columna 0/1 por herramienta (`oe2_herr_simulacion_interactiva`, `_laboratorio_virtual`, `_movil`, `_realidad_virtual_aumentada`, `_otro`) y `oe2_herr_otro_detalle` con el texto de "otro". "Juego (otro)" cuenta como otro con detalle "juego". Las marcas `[F]` y `[I]` sí están documentadas en `_trabajo/extraccion/PROTOCOLO_EXTRACCION.md` (regla 1): `[F]` = lo dice el texto, `[I]` = inferencia razonable del extractor. Son marcas de procedencia, no categorías; se quitan de la etiqueta. Hay 1 valor con `[I]` ("simulación interactiva [I]") y 1 con `[F]` ("otro — [F] simulación narrativa…").

## D21. Tipo de resultado: multi-etiqueta (oe1_resultado_tipo)
Se conservan los nombres de la matriz: conceptual, indagación/habilidades, actitud/motivación, otro. Columnas 0/1 `oe1_res_conceptual`, `oe1_res_indagacion_habilidades`, `oe1_res_actitud_motivacion`, `oe1_res_otro`, más `oe1_res_otro_detalle` (texto de "otro", sin dividir).
- Resolución de problemas va en indagación/habilidades en los 4 casos (3 que estaban en "otro" pasan a indagación; 1 ya estaba).
- Conceptual autoinformado (3 informes: "autopercibido", "comprensión autoinformada") sigue siendo conceptual y activa `conceptual_autoinforme` = 1.
- Las covariables no cuentan como resultado (1 informe: "compromiso y carga cognitiva como covariables"; su segmento de actitud/motivación no se cuenta).
- Sin decisión expresa (queda como en la propuesta): "otro (percepción de aprendizaje; actitud/preferencia)" es solo "otro"; "potencial pedagógico por inspección" y "diferencias por género" siguen en "otro".

## D22. Columnas nuevas, originales conservadas
Las columnas originales no se tocan. Las normalizadas son nuevas: `disciplina_norm`, `mmat_categoria_norm`, `oe1_direccion_norm` y las 0/1 y de detalle de D18 a D21. Un valor crudo que no esté en `config/categorias.yaml` hace fallar el script.

## D23. normalizar_01.py (Paso B)
- Entradas: matriz v2 (Drive, solo lectura), dudosos v4 (para los 18 E4), `prisma_counts` (debe dar 201 informes) y `config/categorias.yaml`. La salida va a `data/processed/Extraccion_datos_v2_2026-10-18_normalizada.csv`, con un `.json` hermano que registra ruta y SHA-256 de cada entrada y de la salida.
- Falla si falta un archivo o una columna, si un valor crudo no está en el mapeo, si una etiqueta de resultado no existe, si los paréntesis no cuadran o si las reglas de excepción de `oe1_resultado_tipo` no tocan exactamente los casos aprobados (3 reasignados, 3 autoinforme, 1 covariable).
- `data/processed/` está en `.gitignore`: la matriz normalizada es un derivado del Drive y se regenera con el script. Si más adelante se publica con los datos (CC BY 4.0), hay que revisar antes las columnas de citas textuales (`oe1_cita`, `oe2_criterios_candidatos`) y decidirlo.
- Se ejecuta con `PYTHONPATH=src python -m rs_pipeline.normalizar_01` porque importa de `prisma_02`.
- Resultado: 219 filas − 18 E4 = 201 informes; 58 columnas originales + 17 nuevas.

## D24. Año de los descriptivos: el de la base de datos
Decidido por Luis Fer (29 oct 2026). Las tablas de año y la ventana de búsqueda 2021–2026 usan el **año de la base de datos** (el registro buscado, columna `anio` de elegibilidad). El año APA se conserva en `cita_apa`. Cuatro informes difieren: R0247 (base 2023 / APA 2024), R0751 (2021 / 2020), R0804 (2021 / 2020) y R0872 (2026 / 2025); es probable que la publicación en línea sea anterior a la impresa. Cada caso queda en `outputs/tablas/anio.json`. El script falla si un año no se puede leer o cae fuera de la ventana.
- **Quinquenio:** calendario (2020–2024 y 2025–2029). Con la ventana 2021–2026, el primero solo tiene informes de 2021 a 2024.
- **Base** (propuesta del asistente, sin objeciones): todas las tablas usan 201 informes; la base de 198 estudios se agrega (`n_estudios`, `pct_estudios`) solo donde los informes del mismo estudio coinciden: disciplina, país, nivel, herramientas y el cruce disciplina × herramienta. Si no coinciden, el script falla. No hay base de estudios en año, idioma, MMAT, dirección ni resultados: los tres pares difieren en MMAT, dirección y resultados, y año e idioma son del informe.

## D25. País (51 categorías)
Aprobado por Luis Fer (29 oct 2026). `pais_norm` es el país donde se hizo el estudio según el texto de la extracción; se quitan las marcas `[F]`/`[I]`, los detalles y las páginas. Hay 49 países, "Chipre" (D26) y "varios países" (R0047 y R1091). Los países inferidos por afiliación (marca `[I]` o "el texto no lo declara") se mantienen; "Hong Kong, China" queda como "Hong Kong".

## D26. R1006 → Chipre
Instrucción de Luis Fer: país donde se hizo el estudio según el texto; si es Nicosia, "Chipre". El informe R1006 (Asiksoy) escribe en la afiliación "Near East University, Nicosia, Turkey" y solo dice que el estudio fue en "a private university" (240 estudiantes de ingeniería, semestre de otoño 2020–2021); no nombra el país del sitio de estudio. Nicosia está en Chipre, así que se asigna Chipre por inferencia desde la afiliación. Nota: el propio artículo escribe "Turkey" en esa dirección; la extracción decía "Turquía según la afiliación".

## D27. Nivel según el texto del informe (8 categorías)
Aprobado por Luis Fer (29 oct 2026): la categoría sigue **lo que dice el texto del informe**, no la etiqueta de la extracción. media 95, secundaria básica 46, primer año universitario 32, universitario 2.º año o superior 13, mixto 6, universitario año no reportado 5, formación docente 3, secundaria sin precisar 1 (R0777: "ciclo VII", grados 9–11, abarca básica y media). El texto manda, por ejemplo: R0115 dice "primer año universitario — en realidad segundo año", y pasa a "2.º año o superior". Los casos de secundaria sin nivel se resolvieron con `grado_equivalente_col` (grado 9 = básica; grados 10 y 11 = media). **Esto no cambia el PRISMA ni excluye ningún informe.** La matriz normalizada queda con 58 originales + 20 nuevas = 78 columnas (`pais_norm`, `nivel_norm` y `nivel_en_revision` se suman a las 17 de D17–D22).

## D28. Revisión de elegibilidad por nivel
Archivo `outputs/tablas/revision_elegibilidad_nivel.csv` (local, no versionado, ver D30; 30 informes, con `.json` que sí se versiona): los 13 de "universitario: 2.º año o superior", los 3 de "formación docente", los 5 de "universitario: año no reportado" y los 9 de "primer año" que quedaron con aviso (R0186, R0066, R0882, R0302, R0477, R0533, R0721, R0956 y R0598). Columnas: id, cita_apa, nivel_crudo, nivel_norm, fragmento_justificativo (campos `contexto` y `alertas` de la extracción, con páginas), motivo_revision y `decision_luisfer` (vacía). La decisión es de Luis Fer y se toma después.
- **Regla 3 de elegibilidad:** la redacción vigente es la de [D31](#d31-regla-3-de-elegibilidad-confirmada); las dos redacciones que se citaban aquí quedaron reemplazadas. Las otras reglas del 11 oct están en `config/params.yaml`.
- No incluidos en el archivo (fuera de las categorías pedidas): R0263 y R0416, de nivel "mixto" con pregrado.

## D29. Flujograma en SVG
`docs/flujograma.svg` se genera desde `docs/flujograma.mmd` con `@mermaid-js/mermaid-cli` 12.0.0 (MIT) por `npx`, con el Chrome local y sin descargar Chromium. No se agregó nada a `requirements.txt` ni al repositorio: el paquete queda en la caché de npm. Al renderizar, Mermaid valida la sintaxis del `.mmd`. Comando en `README.md`.

## D30. Salidas con texto de los artículos no se versionan
Antes del primer push a GitHub (repo privado) se revisó qué había en `outputs/`. Las tablas de frecuencias y el diagrama son solo conteos. `revision_elegibilidad_nivel.csv` trae la columna `fragmento_justificativo` (hasta ~970 caracteres, con citas literales cortas de los informes), así que Luis Fer decidió (29 oct 2026): (1) el CSV va a `.gitignore` y queda solo en el disco local; el `.json` hermano (solo conteos y la regla 3) sigue versionado; (2) se sacó el CSV de todo el historial con `git filter-branch` (solo lo tocaba el commit de descriptivos), antes de cualquier push; (3) se hizo un respaldo previo con `git bundle` fuera del repo. Por la reescritura cambiaron los hashes de los últimos commits (descriptivos `647af66`→`2e74602`, cierre del Bloque 3 `0940c0e`→`af2f11e`, citas de commits `e1d3181`→`6e27926`); `PROCEDIMIENTO.md` se corrigió. Regla nueva en `CLAUDE.md`: los outputs con texto de los artículos no se versionan; y push a origin al cerrar cada bloque. (Se numera D30 porque D29 ya es el flujograma SVG.)

## D31. Regla 3 de elegibilidad confirmada
Luis Fer confirmó el 29 oct 2026 el texto de la regla 3: *"Se incluyen los estudios con estudiantes de 2.º año universitario cuando el curso es todavía de ciencia básica o introductoria (p. ej., química general II, física para ciencias de la salud). Se excluyen los cursos avanzados o profesionalizantes (E1, población)."* Reemplaza las dos redacciones anteriores: la del checkpoint del Eje 3 ("2.º año cercano a lo clínico: incluir (es ciencia)"), que fue un error de transcripción, y la de la columna `sugerencia_automatica` de Casos_dudosos v4 ("2.º año cercano a lo introductorio = incluir"), que sigue tal cual en el Drive (solo lectura). Queda en `config/params.yaml` (`regla_3_elegibilidad.texto`) y en el `.json` de la revisión. Se aplicó para proponer una decisión por informe en `revision_elegibilidad_nivel.csv`, sin excluir nada todavía (D28). Cambió un test: el que comparaba el texto antiguo ahora compara el confirmado (cambio de especificación pedido por Luis Fer). (Se numera D31 porque D30 ya es "Salidas con texto de los artículos no se versionan".)

## D32. Criterio para formación docente
Decidido por Luis Fer (29 oct 2026). Los futuros docentes se **incluyen** cuando aprenden contenido científico en un curso básico o introductorio (regla 1 del 11 oct). Se **excluyen (E1)** cuando el resultado medido es su competencia para enseñar (didáctica, TPACK, actitud hacia usar simulaciones en el aula). Así se reconcilia con el E1 del cribado: la población no se excluye por ser futuros docentes sino por lo que se mide.

## D33. Decisiones de la revisión de elegibilidad por nivel
Decididas por Luis Fer el 29 oct 2026 sobre `revision_elegibilidad_nivel.csv`, ahora con 32 informes (los 30 de D28 más R0263 y R0416, de nivel "mixto" con pregrado). Se aplicaron la regla 3 ([D31](#d31-regla-3-de-elegibilidad-confirmada)) y el criterio de formación docente ([D32](#d32-criterio-para-formación-docente)).
- **Incluir (27):** todos los propuestos como incluir y además R0015, R0349, R0280, R0450, R0868, R0115, R0064, R0453, R0597, R0870 y R0416.
- **Excluir E1 (4):** R0720, R0935, R0877 y R0186. **Excluir E3, disciplina (1):** R0295 (seminario de introducción a la realidad virtual en ingeniería en computación).
- **`nivel_dudoso` = 1** (columna nueva de la matriz normalizada, para el análisis de sensibilidad): R0280, R0064, R0453, R0597, R0870 y R0416. La matriz queda en 79 columnas (58 originales y 21 nuevas).
- Las 5 exclusiones están en `config/exclusiones_nivel.yaml` (id, código, motivo, decidido_por, fecha). `prisma_02.py` las aplica en memoria sobre los CSV del Drive, que no se tocan; falla si alguna no es un informe incluido o si excluye un informe de un par sin su pareja. Ninguno de los 5 comparte estudio.
- **Nueva versión de prisma_counts:** `config/prisma_counts_2026-10-29.json`, en el repo (el Drive es solo lectura y la del 26 oct no se sobrescribe). Se deriva con `prisma_02.py --derivar-counts` desde la base del Drive más las exclusiones y registra el hash de ambas. Resultado: excluidos en texto completo 94 → 99 (E1 28 → 32, E3 2 → 3), **informes incluidos 201 → 196, estudios 198 → 193**. `prisma_02` contrasta esa versión con el recálculo desde los CSV; el diagrama nuevo es `Diagrama_PRISMA_2020_Eje3_2026-10-29.*` (el del 26 oct queda como versión anterior).
- Las tablas y la matriz pasaron a la base de 196 informes y 193 estudios: ver [D34](#d34-prisma_counts_2026-10-29json-es-la-fuente-de-verdad-del-prisma).

## D34. `prisma_counts_2026-10-29.json` es la fuente de verdad del PRISMA
Decidido por Luis Fer (29 oct 2026). Desde ahora `normalizar_01.py`, `descriptivos_03.py` y `prisma_02.py` leen los conteos de `config/prisma_counts_2026-10-29.json` (196 informes, 193 estudios). El JSON del Drive del 26 oct queda solo como base para derivarlo (`prisma_02.py --derivar-counts`).
- La matriz normalizada **conserva las 201 filas** (los 5 excluidos no se borran) y agrega `excluido_nivel` (0/1) y `excluido_nivel_codigo` (E1 o E3, vacío si no está excluido): 81 columnas, 58 originales y 23 nuevas. `normalizar_01` falla si 201 menos las exclusiones no es el número de informes incluidos que declara el JSON.
- `descriptivos_03` filtra los excluidos: las tablas suman **196** informes (o **193** estudios donde la base es de estudios) y falla si la matriz no coincide con el JSON. `revision_elegibilidad_nivel.csv` sigue con las 32 filas, incluidos los 5 excluidos.
- Cambió un test por redondeo, no por un error de cálculo: la suma de porcentajes de `pais` (51 categorías con 1 decimal) da 99,5; antes pasaba con 201 por casualidad. La tolerancia ahora es el máximo que permite el redondeo (0,05 por fila).

## D35. Mini-sprint semántico: diseño de las pruebas
Aprobado por Luis Fer (29 oct 2026). Pregunta: ¿sirve BERTopic con embeddings multilingües en este corpus? Todo local, sin llamadas a la API, en un venv aparte (`.venv-semantico`, `requirements-semantico.txt` fijado, `pip-audit` sin vulnerabilidades). Código: `semantico_texto.py`, `semantico_metricas.py` y `semantico_04.py` (`PYTHONPATH=src .venv-semantico/bin/python -m rs_pipeline.semantico_04`).
- **Modelos** (revisión fija en `params.yaml`): principal `intfloat/multilingual-e5-base` (prefijo `passage: `); control `paraphrase-multilingual-MiniLM-L12-v2`. No se usan modelos más grandes por la RAM (8 GB).
- **Prueba 1 (mecánica):** trozos del texto completo (Drive, solo lectura) de R0998, R0045, R0578, R0527, R1085, R0755, R0711, R0730, R0713 y R0922. Trozos de ~150 palabras (e5) y ~90 (MiniLM) sin cortar oraciones, sin referencias ni encabezados: 408 y 624 trozos. Los `.txt` ya traen las referencias cortadas con un marcador (8 de 10) o conservan el encabezado «References» (R0045 y R0713, que se cortan ahí); sin ninguno de los dos el script falla.
- **Prueba 2 (principal):** fichas de los 196 informes (sin los 5 `excluido_nivel`), limpias de `[F]`/`[I]` y de citas de página. **2a:** `oe1_hallazgo`, `oe2_*` y `oe4_*` juntos (3.608 unidades: oe1 196, oe2 2.176, oe4 1.236). **2b:** solo `oe2_*`.
- **Decisiones propias (1 a 3 confirmadas por Luis Fer el 30 oct 2026; la 4 no se mencionó):** (1) `oe2_tipo_herramienta` no entra: son 3 etiquetas repetidas ya normalizadas y formarían temas triviales; (2) `oe2_criterios_candidatos` se parte en un criterio por unidad con su propio separador « || » (662 unidades); (3) se descartan las fichas de menos de 5 palabras (por ejemplo «no reporta»; 386 en total, sobre todo `oe2_idioma_accesibilidad` 72, `oe2_costo_licencia` 65, `oe4_organizacion` 50 y `oe4_steam` 49); (4) las palabras vacías (es/en/pt) incluyen «estudiantes», «estudio» y «resultados» por aparecer en casi todos los trozos.
- **Método:** UMAP (15 vecinos, 5 componentes, coseno) y HDBSCAN (tamaño mínimo 10, `eom`), 5 semillas de UMAP (HDBSCAN es determinista), embeddings calculados una vez. Estabilidad: ARI entre las 10 parejas de semillas, contando solo unidades con tema en ambas corridas. Coherencia: NPMI de las 10 palabras clave por co-aparición en la misma unidad, comparada con la misma medida sobre asignaciones barajadas de la misma corrida. Prueba 1 además: mezcla de idiomas (2 o más idiomas con ≥10 % de los trozos de un tema), % de temas «de un documento» (>70 % de sus trozos del mismo informe), tiempo MPS contra CPU y RAM. Prueba 2: reparto de cada tema por OE de origen (2a), `disciplina_norm` y `nivel_norm`.
- **Umbrales** (aprobados; `params.yaml`): embeddings de los 10 informes en menos de 300 s; ARI entre semillas ≥0,6 (cumple) y <0,4 (no cumple); sin tema ≤40 % (cumple) y >60 % (no cumple); NPMI real mayor que el azar; mezcla de idiomas ≥50 % de los temas (solo Prueba 1; 0 % no cumple); si más de 50 % de los temas son «de un documento», la prueba de texto completo no sirve para la síntesis; interpretables ≥60 % (cumple) y <40 % (no cumple), con al menos 3 temas, a juicio de Luis Fer.
- **Deuda técnica:** `semantico_04.py` copia tres funciones mínimas de `prisma_02.py` (`leer_env`, `raiz_drive`, `sha256`) porque el venv semántico no tiene `prismaflow` ni `resvg`. Los tres módulos se formatearon con `ruff format`.

## D36. Análisis de sensibilidad por modelo de embeddings
Las dos pruebas corren con e5-base y con MiniLM, y se reporta el acuerdo entre ellos como ARI entre las asignaciones de temas (25 parejas: cada semilla de un modelo contra cada semilla del otro, solo unidades con tema en ambos). En la Prueba 1 los trozos de los dos modelos son distintos, así que se compara por oración (cada oración hereda el tema de su trozo); en las fichas las unidades son las mismas. Resultado: ARI medio 0,177 en la Prueba 1 (0,152–0,192), 0,481 en la 2a (0,395–0,698) y 0,636 en la 2b (0,298–0,737). **Limitación:** MiniLM trunca a 128 tokens y el 92,8 % de sus trozos de ~90 palabras los supera (e5 trunca el 0,2 %), de modo que en la Prueba 1 el control ve solo una parte de cada trozo y la comparación no es limpia.

## D37. Los temas sobre fichas agrupan la extracción, no el texto original
Los temas de la Prueba 2 se calculan sobre las fichas, que son la extracción hecha por Claude, no sobre el texto de los artículos. Se usan como triangulación de la síntesis temática, no como sustituto de ella.

## D38. Hoja de calificación a ciegas (solo Prueba 2b)
Luis Fer acotó la hoja el 30 oct 2026 (la primera, de 138 temas, quedó descartada en `outputs/semantico/descartadas/`). `outputs/semantico/hoja_calificacion_ciega_2b.csv` (ignorada por git; UTF-8 con BOM para Excel) lista **35 temas** de la Prueba 2b (solo `oe2_*`): los 20 de e5 y los 15 más grandes de MiniLM, de la **semilla medoide** de cada modelo (e5 semilla 4; MiniLM semilla 3; la que más se parece, por ARI, a las otras cuatro). Cada tema trae 10 palabras clave, 3 fragmentos de ≤60 palabras y una columna `calificacion` vacía (interpretable / mixto / ruido). El código aleatorio de 5 caracteres reemplaza al modelo y la semilla; las filas están barajadas. La tabla que traduce los códigos está aparte, en `outputs/semantico/traduccion_codigos_2b.csv` (también ignorada), y no se ha abierto. Las corridas se repitieron para obtener los textos (`semantico_04 --hoja-2b`) y dieron exactamente las asignaciones ya guardadas.

## D39. Resultado de las corridas y veredicto automático (provisional)
Medias de las 5 semillas. El detalle numérico está en `outputs/semantico_metricas/` (en git: solo números). La interpretabilidad falta: la califica Luis Fer con la hoja a ciegas.
- **Prueba 1:** e5 7 temas, 0,0 % sin tema, ARI entre semillas 0,996, NPMI 0,338 contra 0,087 al azar; MiniLM 4 temas, 1,2 % sin tema, ARI 0,953, NPMI 0,312 contra 0,016. Mezcla de idiomas: 0 % de los temas con e5 (no cumple) y 33–50 % con MiniLM (intermedio). Temas «de un documento»: 71,4 % con e5 y 66,7–80 % con MiniLM (no cumple en ambos). Embeddings de los 10 informes: e5 59,6 s en MPS y 45,9 s en CPU; MiniLM 7,9 s y 9,2 s (cumple). Coseno MPS contra CPU 1,0. RAM máxima del proceso 1,3 GB.
- **Prueba 2a:** e5 30 temas, 10,7 % sin tema, ARI 0,994, NPMI 0,039 contra −0,089; MiniLM 48 temas, 30,5 % sin tema, ARI 0,838 (mín 0,644), NPMI 0,054 contra −0,310. El 95 % (e5) y el 93 % (MiniLM) de los temas tienen más de 70 % de sus unidades de un mismo OE (ARI tema contra OE 0,14 y 0,09): los temas siguen sobre todo el tipo de campo. Por disciplina y nivel casi ningún tema pasa de 70 % (e5 2,7 % y 0,7 %; MiniLM 13,5 % y 8,5 %).
- **Prueba 2b:** e5 20 temas, 7,7 % sin tema, ARI 0,998, NPMI −0,010 contra −0,032 (supera al azar en 4 de 5 corridas, pero es casi cero); MiniLM 25 temas, 19,5 % sin tema, ARI 0,822 (mín 0,549), NPMI 0,072 contra −0,134.
- **Veredicto frente a los umbrales:** estabilidad, sin tema, NPMI y tiempo cumplen en las 6 combinaciones. No cumplen: mezcla de idiomas (P1, e5) y temas «de un documento» (P1, e5 y MiniLM). Con la regla aprobada, la **prueba de texto completo no sirve para la síntesis**. Las fichas (Prueba 2) cumplen lo automático y quedan a la espera de la interpretabilidad.

## D40. Calificación a ciegas de la Prueba 2b y veredicto final
Luis Fer calificó la hoja a ciegas de la Prueba 2b (35 temas) el 31 oct 2026: **29 interpretables, 6 mixtos y 0 ruido**. Se abrió después la traducción de códigos (`traduccion_codigos_2b.csv`) y se calculó por modelo (`semantico_04 --calificacion-2b`; resultado numérico en `outputs/semantico_metricas/prueba2b_calificacion.json`, con el hash de la hoja calificada y de la traducción):

| Modelo | Temas calificados | Interpretables | Mixtos | Ruido | Frente al umbral (≥60 % sigue; <40 % no sigue) |
|---|---|---|---|---|---|
| e5-base | 20 (todos) | 18 (90,0 %) | 2 (10,0 %) | 0 | cumple |
| MiniLM | 15 (los más grandes de 23) | 11 (73,3 %) | 4 (26,7 %) | 0 | cumple |

Ambos tienen además al menos 3 temas interpretables. **Veredicto final de la Prueba 2b: sigue, con los dos modelos.** Todos los criterios aprobados cumplen: ARI entre semillas 0,998 (e5) y 0,822 (MiniLM); sin tema 7,7 % y 19,5 %; NPMI real mayor que el azar (e5 −0,010 contra −0,032 en 4 de 5 corridas; MiniLM 0,072 contra −0,134 en 5 de 5); interpretabilidad 90,0 % y 73,3 %.
- **Límites que acompañan al veredicto:** (1) la coherencia NPMI de e5 supera al azar por poco y es casi cero; (2) de MiniLM se calificaron solo los 15 temas más grandes de 23, de modo que su porcentaje describe los temas grandes; (3) se calificó solo la semilla medoide de cada modelo; (4) la interpretabilidad de la Prueba 2a no se calificó y queda pendiente; (5) los temas agrupan la extracción hecha por Claude, no el texto original (D37); (6) la Prueba 1 (texto completo) no cumple la regla de temas «de un documento» (D39).
- **Protección:** `escribir_hoja_ciega` falla si la hoja existente ya tiene calificaciones, para que una corrida futura no pise el trabajo de Luis Fer. El respaldo sin calificar (`hoja_calificacion_ciega_2b_sin_calificar_respaldo.csv`) se conserva y un test comprueba que sigue vacío y con los mismos códigos.
- **Tests cambiados por especificación:** dos asertos que daban por vacía la calificación de la hoja y por pendiente la interpretabilidad de la Prueba 2b; ahora esperan la hoja calificada y «cumple».

## D41. Bloque 6, paso 1: nombrar los temas de la Prueba 2b (e5)
Decisiones aprobadas por Luis Fer (31 oct 2026) para pasar de los temas a un marco de criterios de diseño:
- **Alcance:** solo se nombran los **20 temas de e5** de la semilla medoide (la que Luis Fer calificó, semilla 4); MiniLM queda como control de sensibilidad.
- **Quién nombra primero:** Luis Fer, **sin ver propuestas**. En este paso no se generan nombres ni criterios propios.
- **Qué puede hacer con cada tema:** mantener, fusionar, dividir o descartar (columna `accion`; `fusionar_con` indica con cuál).
- **Regla de peso de la evidencia (se aplicará en el paso 2; aquí solo se registra):**
  - **A. Calidad MMAT:** criterios cumplidos, alta / media / baja.
  - **B. Diseño:** comparativo con control > pre-post de un grupo > descriptivo o cualitativo.
  - **C. Pertinencia:** secundaria > primer año universitario > `nivel_dudoso`.
  - **Análisis de sensibilidad:** cada criterio debe sostenerse también sin los estudios de peso bajo.
- **Hoja:** `outputs/semantico/hoja_nombrar_temas_2b_e5.csv` (ignorada por git; UTF-8 con BOM), una fila por tema, con las columnas `tema, n_unidades, n_informes, palabras_clave, campos_oe2, fragmento_1` a `fragmento_5`, `accion, fusionar_con, nombre, criterio, nota` (las cinco últimas vacías). `campos_oe2` lista los campos de la ficha de donde vienen las unidades del tema, solo los que superan el 5 % (por ejemplo «oe2_andamiaje 70 %; oe2_retroalimentacion 20 %»).
- **Fragmentos:** las 5 unidades más representativas se definen como las más cercanas (coseno) al centroide de los embeddings e5 del tema; son el texto completo de la unidad de la ficha, sin recortar. Las 20 filas salen de repetir la corrida de la semilla 4, que debe dar exactamente las asignaciones guardadas (si no, falla).
- **Protección:** `semantico_04 --hoja-nombrar-2b` se niega a sobrescribir la hoja si alguna de las cinco columnas a llenar ya tiene contenido.
- **Tests:** columnas exactas, 20 temas, `n_unidades` y `n_informes` recalculados desde las asignaciones, `campos_oe2` recalculado, que cada fragmento sea una unidad real de la ficha, la protección y el cálculo del centroide (117 pruebas en total).


## D42. Bloque 6, paso 2: marco de criterios v0 (decisiones de Luis Fer sobre los 20 temas de e5)
Decisiones de Luis Fer (31 oct 2026) tras nombrar la hoja `hoja_nombrar_temas_2b_e5.csv` (respaldo sin nombrar: `…_sin_nombrar_respaldo.csv`):
- **Estructura oficial de un criterio (3 niveles):** `dimension` = columna `nombre` de la hoja · `criterio_corto` = columna `criterio` · `enunciado` = columna `nota`.
- **Marco v0, 9 criterios** (`config/criterios_v0.yaml`, texto de Luis Fer, se versiona): C01 = tema 0 (borrador, con textos dados por Luis Fer; la dimensión sale de la hoja) · C02 = 2 · C03 = 5 · C04 = 6 · C05 = 11 · C06 = 12 · C07 = 16 + 8 (el 8, usabilidad, se fusiona con el 16; textos del 16) · C08 = 17 (todos «aprobado», textos tal cual de la hoja) · C09 nuevo (borrador) = 3, 4, 7, 9, 10, 13, 18, 19, con dimensión, criterio corto y enunciado dados por Luis Fer.
- **Descartados:** tema 1 (qué herramienta se usó: es un dato, no un criterio), 14 y 15 (mezclas pequeñas). Los 20 temas quedan cubiertos una sola vez.
- **Diferencia con la hoja:** en la columna `accion` de la hoja los temas 3, 4, 7, 8, 9, 10, 13, 18 y 19 figuran como «descartar»; las decisiones de este registro (C09 y la fusión 8→16) tienen prioridad.
- **6 y 12 quedan separados;** si en el cruce comparten más del 70 % de sus informes, se avisa a Luis Fer.
- **Chequeo de acuerdo de nombres:** Claude propuso un nombre corto por tema leyendo solo el respaldo sin nombrar, antes de abrir los textos de Luis Fer (`outputs/semantico/propuestas_nombres_claude_2b_e5.csv`, ignorado).
- **Pendiente de aprobación:** la operacionalización del peso de la evidencia (A, B, C y su combinación) y el cruce por criterio (E).
