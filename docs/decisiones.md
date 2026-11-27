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

## D43. Bloque 6, paso 2 (E): peso de la evidencia y cruce de los criterios con los estudios
Aprobado por Luis Fer (31 oct 2026), con sus ajustes. Código: `src/rs_pipeline/criterios_05.py`. Base: 196 informes / 193 estudios (sin los 5 excluidos por nivel).
- **A. Calidad MMAT:** se cuentan los «Sí» de los 5 ítems de `mmat_items` (cuenta «No se puede saber» como no cumplido). **Alta** = 3 o más · **media** = 2 · **baja** = 0–1, o `mmat_s1` distinto de «Sí». **Advertencia:** el manual MMAT 2018 desaconseja un puntaje global; el conteo se usa **solo para agrupar en la sensibilidad**. Para el anexo se genera la tabla ítem por ítem `outputs/tablas/mmat_items_por_informe.csv` (solo Sí / No / No se puede saber, sin texto ni puntaje).
- **B. Diseño:** comparativo con control = alto · pre-post de un grupo = medio · descriptivo o sin comparación (`comparacion` empieza con «ninguna» o `oe1_direccion_norm` = «no comparativo») = bajo. Los 5 informes con comparación pero «no comparativo» pasan a bajo.
- **C. Pertinencia:** secundaria = 2 · primer año, 2.º año introductorio, formación docente y mixto = 1 · `nivel_dudoso` o «universitario: año no reportado» = 0.
- **Peso final:** **regla principal = suma** de los puntos A+B+C (0–2 cada uno): 5–6 alto, 3–4 medio, 0–2 bajo. **Segunda sensibilidad = regla del mínimo** (el eje más débil manda). Ambas se reportan por criterio.
- **Estudio:** los atributos de un estudio con dos informes salen del informe de más puntos (a igual, el de menor id).
- **Unidades de un criterio:** las unidades `oe2_*` de los temas de e5 (semilla medoide 4) que lo componen (D42); el tema −1 no cuenta.
- **C09, «criterio sostenido por brecha de reporte + contexto».** Cada unidad se clasifica por patrón («no reporta / no se menciona / no especifica / no declara / no detalla / no indica / no describe / no informa / no evalúa», «sin datos…», «no hay datos/medición…») en: **real** (sin el patrón), **mixta** (tiene contenido y además una frase «no reporta») y **solo «no reporta»** (el patrón y nada más; un segmento con 3 o más palabras de contenido tras quitar la etiqueta y la frase cuenta como contenido). No se borra ninguna unidad. Las unidades de menos de 5 palabras ya se descartaban antes de agrupar (D35), por lo que las «no reporta» más cortas no están en los temas; para eso se reporta además, por campo de ficha, en cuántos de los 196 informes el campo entero no reporta (`criterios_v0_reporte_por_campo.csv`).
- **Resultado del cruce (estudios por peso suma alto / medio / bajo; sin bajo con suma; sin bajo con mínimo):** C01 193: 31/114/48; 145; 52 · C02 177: 31/100/46; 131; 50 · C03 110: 21/58/31; 79; 29 · C04 89: 12/56/21; 68; 22 · C05 51: 8/28/15; 36; 16 · C06 44: 6/24/14; 30; 9 · C07 99: 15/51/33; 66; 23 · C08 13: 4/7/2; 11; 7 · C09 191: 30/114/47; 144; 51.
- **Aviso 6 y 12:** comparten 1 informe (1,1 % de los del tema 6 y 2,3 % de los del 12); no pasan del 70 %, quedan separados.
- **Archivos:** `outputs/tablas/criterios_v0_evidencia.csv/.json` y `criterios_v0_reporte_por_campo.csv` (en git, solo números, con hash de entradas); IDs de unidades, ejemplos de reporte y los 5 `oe2_criterios_candidatos` más parecidos (coseno e5, prefijo `passage: `, como en la agrupación) a cada enunciado, en `outputs/semantico/` (ignorado).
- **Tests:** `tests/test_criterios.py` (reglas A/B/C y pesos con casos a mano; conteos MMAT 28/49/119 recalculados; unidades, informes y estudios por criterio recalculados desde las asignaciones; repartos que suman; hash de la salida).

## D44. Bloque 7: libro de códigos y codificación deductiva (piloto)
Decisiones de Luis Fer (31 oct 2026). Código: `src/rs_pipeline/codificacion_06.py`. En este bloque solo hay diseño y hoja piloto; **no se llama a la API**.
- **Por qué se codifica:** el cruce del Bloque 6 (D43) contó **cobertura de campos de ficha**, no evidencia: casi todos los informes «sostienen» cada criterio porque cada ficha tiene los mismos campos. Por eso la columna «Estudios» de `criterios_v0_evidencia.csv` se reporta **solo como cobertura temática**. La evidencia real se mide codificando cada informe frente a cada criterio.
- **Libro de códigos v0** (`config/libro_codigos_v0.yaml` y `docs/libro_codigos_v0.md`; criterios C01–C09 tomados de `config/criterios_v0.yaml`, C01 y C09 siguen en borrador). Escala por informe y criterio: **0** = no aparece, o la ficha dice explícitamente que no se reporta · **1** = descrito (el laboratorio o la actividad lo tenía, pero el estudio no reporta su efecto) · **2** = con resultado (el estudio lo vincula a un resultado: mejoró algo, o su ausencia causó problemas). Reglas: codificar solo lo que dice la ficha; ante duda entre dos códigos, el menor. Ejemplos inventados (no texto de artículos) para los tres códigos en C02, C04 y C09.
- **Campos de la ficha que se codifican** (los mismos que leerá la API después), en este orden: `tema, nivel_norm, disciplina_norm, diseno, comparacion, oe1_hallazgo, oe1_condiciones, oe1_direccion_norm, oe2_herramienta, oe2_andamiaje, oe2_retroalimentacion, oe2_interactividad, oe2_dispositivo, oe2_conectividad, oe2_idioma_accesibilidad, oe2_costo_licencia, oe2_usabilidad_calidad, oe4_secuencia, oe4_rol_docente`. **No** se incluyen `oe2_criterios_candidatos` (inferencias del extractor que sesgarían el código) ni `lf_*` (notas de Luis Fer). Se quitan las marcas [F]/[I] y las citas de página.
- **Muestras** (semilla fija 20261031 en `params.yaml`; sin los 5 excluidos por nivel; peso = regla de la suma de D43 por informe): **piloto** de 5 informes, con 3 o más pesos, disciplinas e idiomas distintos y estudios distintos (sorteo con semilla hasta cumplir) · **confiabilidad** de 40 informes, estratificados por peso × nivel con reparto proporcional (mínimo 1 por estrato no vacío), sin repetir el piloto ni su estudio. Solo se guarda la lista (`outputs/semantico/muestra_confiabilidad_40.csv`); la hoja se arma después del piloto.
- **Hoja del piloto:** `outputs/semantico/hoja_codificacion_piloto.csv` (ignorada; UTF-8 con BOM), columnas `id_ciego, [19 campos], C01…C09, nota`; `id_ciego` = P01…P05 en orden sorteado, y la correspondencia con el id real está en `hoja_codificacion_piloto_correspondencia.csv` (ignorado). `codificacion_06` no sobrescribe la hoja si ya tiene códigos o notas.
- **Estimación de costo (sin llamar a la API),** Batch API (50 % sobre entrada y salida, se acumula con el caché), libro de códigos en caché de 1 h. Precios del 31 oct 2026 en https://platform.claude.com/docs/en/about-claude/pricing (claude-sonnet-5-5: entrada 2, salida 10; claude-opus-5-5: entrada 4, salida 20; USD por millón de tokens; lectura de caché 0,05× la entrada). Tokens estimados con 3,5 caracteres por token (rango 3,0–4,0, sin API): libro y reglas ≈ 2.500 tokens; ficha ≈ 590 tokens por informe; entrada total ≈ 608.000 tokens (con caché, el libro cuenta una vez); salida 60 tokens por informe (solo los 9 códigos) o 450 (con una justificación breve por criterio). Resultado para los 196 informes: **Sonnet 5.5 de 0,20 a 0,59 USD con caché (de 0,67 a 1,05 sin caché); Opus 5.5 de 0,41 a 1,17 USD con caché (de 1,33 a 2,10 sin caché)**. En el rango de 3,0–4,0 caracteres por token todo queda por debajo de 2,3 USD. Si se usa razonamiento extendido, la salida sube y hay que reestimar. El caché en Batch es de mejor esfuerzo. Archivo: `outputs/tablas/costo_codificacion_estimado.json`.
- **Antes de usar la API** hará falta, como siempre, que Luis Fer apruebe el lote y el costo (CLAUDE.md).
- **Tests:** `tests/test_codificacion.py` (libro = criterios, columnas exactas de la hoja, sin marcas ni citas, piloto variado y reproducible con la semilla, muestra de 40 sin repetir, cuotas, protección de la hoja y costo con cuentas a mano).

## D45. Libro de códigos v1 y piloto de Luis Fer
Piloto codificado por Luis Fer (31 oct 2026) en `outputs/semantico/hoja_codificacion_piloto.csv` (respaldo sin códigos: `…_sin_codificar_respaldo.csv`; las notas de Luis Fer las guarda él aparte). Del piloto salen tres reglas nuevas; el libro v1 (`config/libro_codigos_v1.yaml`, `docs/libro_codigos_v1.md`) conserva la escala, los criterios y las reglas del v0 (que no se tocan) y agrega:
- **a)** «2» exige que los autores atribuyan el resultado, aunque sea en parte, a ESE componente. Que la intervención en conjunto funcione no basta: un paquete cuenta 1 para los componentes a los que no se atribuye el resultado.
- **b)** Un dato descriptivo de contexto o de barrera (p. ej., el porcentaje sin internet en casa) es 1. Solo es 2 si el estudio dice que influyó en la actividad o en el aprendizaje.
- **c)** «1» exige que la ficha mencione el componente. Si no lo menciona, o dice que no se documenta, es 0, aunque se pueda suponer que existía.
- **Codificación de Claude Code del mismo piloto** (modelo `claude-sonnet-5-5`, solo con las fichas, registrada en `logs/codificacion_claude.jsonl`): **acuerdo 32 de 45 (71,1 %), kappa ponderado cuadrático total 0,548.** Por criterio: C01 40 % (κ 0,00), C02 60 % (0,00), C03 80 % (0,545), C04 100 % (1,00), C05 60 % (0,50), C06 100 % (1,00), C07 80 % (0,545), C08 40 % (0,00), C09 80 % (0,667). Con 5 informes es solo orientativo, y el kappa por criterio es poco estable.
- **Límite del método:** los códigos de Luis Fer ya estaban a la vista de Claude cuando codificó, así que **no es una codificación ciega**; el acuerdo puede estar sobreestimado. Los 13 desacuerdos van todos en el mismo sentido (Claude codifica más bajo que Luis Fer), lo que sugiere que las reglas nuevas bajan códigos o que Claude es más estricto.
- **Recodificación sugerida (no cambia la hoja de Luis Fer):** `outputs/semantico/sugerencias_recodificacion_piloto.csv` (ignorado); 13 de sus 45 códigos cambiarían: 7 por la regla a, 1 por la b y 5 por la c. Luis Fer decide.
- **Archivos:** `outputs/tablas/acuerdo_piloto_luisfer_claude.csv/.json` (en git, solo números); `outputs/semantico/{codigos_claude_piloto,desacuerdos_piloto_luisfer_claude,sugerencias_recodificacion_piloto}.csv` (ignorados).
- **Tests:** `tests/test_codificacion_claude.py` (kappa con cuenta a mano, validación, registro solo-agrega, hash de las fichas, hoja de Luis Fer, acuerdo publicado, reglas nuevas del libro).

## D46. La codificación la hace Claude Code, no la API
Decisión de Luis Fer (31 oct 2026): el piloto, la muestra de 40 y los 196 informes los codifica Claude Code con la suscripción de Luis Fer; **no se usa la API**.
- `CLAUDE.md`: la sección «API de Claude» queda solo para un uso futuro, y se agrega «Codificación asistida por Claude Code»: cada informe deja una línea en `logs/codificacion_claude.jsonl` (fecha, modelo con su ID exacto, hash del YAML del libro, `id_ciego`, hash de la ficha leída, los 9 códigos y una justificación de una línea por código); `logs/` sigue fuera de git y a git va solo un resumen numérico; lotes de máximo 50 informes por sesión, cada uno con commit; nunca se recodifica sobre un registro anterior (un nuevo intento es una nueva línea con fecha).
- `outputs/tablas/costo_codificacion_estimado.json` queda marcado «no aplica (D46)» (la estimación original se conserva dentro como registro histórico).
- **Test cambiado por especificación:** `test_costo_con_cuentas_a_mano` leía los campos de la estimación en el nivel superior del JSON; ahora comprueba el estado «no aplica (D46)» y los lee dentro de `estimacion_api_no_vigente`. El cálculo del costo sigue probado igual.

## D47. Cierre del piloto, libro de códigos v2 y muestra de 40 sin anclaje
Decisiones de Luis Fer (1 nov 2026):
- **El piloto no entra en el cálculo de confiabilidad.** Su hoja queda como está (no se recodifica). Los resultados del piloto (D45) siguen siendo orientativos.
- **Libro de códigos v2** (`config/libro_codigos_v2.yaml`, `docs/libro_codigos_v2.md`; v1 no se toca). Conserva la escala, los criterios y las reglas del v1 y agrega: **d)** si el grupo de comparación también tuvo el componente, no se puede atribuir el resultado a ese componente: se codifica 1, no 2 · **C08:** predecir y luego comparar con lo observado (predecir-observar-explicar), o comparar resultados con valores de referencia o con la teoría, cuenta como 1; es 2 solo si el estudio relaciona ese contraste con un resultado. Con ejemplos inventados de ambos.
- **Hoja de la muestra de 40:** `outputs/semantico/hoja_codificacion_40.csv` (ignorada; UTF-8 con BOM), mismas columnas que la del piloto, `id_ciego` = M01…M40 en orden sorteado, `C01`–`C09` y `nota` vacías. La correspondencia con los ids reales está en `hoja_codificacion_40_correspondencia.csv` (ignorado). Sale de la lista de 40 de D44 (semilla fija; sin el piloto ni su estudio ni los 5 excluidos por nivel).
- **Codificación sin anclaje:** Claude no codifica la muestra en la sesión donde vio los códigos del piloto. La hará una **sesión nueva** que solo lee el libro v2, la hoja de 40 y `docs/protocolo_codificacion_ciega.md`, y que registra sus códigos en `logs/codificacion_claude.jsonl` y en `outputs/semantico/codigos_claude_40.csv` (ignorado). Luis Fer no abre ese archivo hasta terminar sus propios códigos. A git va solo `outputs/tablas/codificacion_claude_resumen.json` (cuántos informes, libro, modelo y fecha; sin códigos).
- **Herramientas:** `codificacion_claude --registrar LOTE.json --hoja hoja_codificacion_40.csv --libro v2` valida todo el lote antes de escribir, solo agrega líneas al registro y falla si el lote no trae exactamente los informes de la hoja.
- **Tests:** libro v2 (dos reglas más, v1 intacto), hoja de 40 (columnas, M01–M40, sin códigos, sin repetir el piloto), lote y resumen sin códigos.

## D48. Confiabilidad de la muestra de 40 (libro v2)
**Procedencia de los códigos:** los códigos de Luis Fer fueron decididos por él leyendo las fichas, apoyado en notas propias de lecturas previas; Claude codificó primero en sesión limpia sin acceso a los códigos humanos. Por eso no es una doble codificación independiente en sentido estricto: Luis Fer tuvo lecturas previas y Claude no.
- **Comparación** (`python -m rs_pipeline.confiabilidad_40`): n = 40 informes × 9 criterios; acuerdo exacto, kappa ponderado cuadrático, AC1 de Gwet sin pesos (para criterios con casi todo en un código, como C06), distribución 0/1/2 de cada codificador y IC 95 % del kappa total por bootstrap de informes (5000 remuestreos, semilla 20261101).
- **Resultado:** kappa total 0.296 (IC 95 % 0.233 a 0.353). Veredicto según el umbral de Luis Fer (≥ 0,60 sigue; 0,40–0,60 se revisan criterios; < 0,40 se replantea el libro): **kappa total < 0,40: se replantea el libro**.
- **Salidas:** `outputs/tablas/confiabilidad_40.csv/.json` (git, solo números); `outputs/semantico/desacuerdos_40_luisfer_claude.csv` (ignorado, trae justificaciones).
- **Tests:** `tests/test_confiabilidad_40.py` (AC1 con cuenta a mano, umbrales del veredicto, distribuciones y salidas publicadas contra los códigos fuente).

## D49. La escala principal pasa a ser la presencia (0 frente a 1 o 2)
Decisión de Luis Fer (1 nov 2026), tomada **después de ver los resultados de D48** (kappa ponderado total 0,296); no se declaró antes de codificar.
- **Escala principal: presencia binaria** (0 = no aparece o se dice que no se reporta; 1 = aparece, con o sin resultado). **La atribución (código 2) deja de usarse como medida.** Se reporta como hallazgo: solo 16 de 360 códigos de Claude (y 114 de Luis Fer) atribuyen el resultado a un componente específico; la mayoría de los estudios evalúa paquetes. Los códigos 0/1/2 siguen guardados; el libro v2 no cambia.
- **Medidas:** % de acuerdo, kappa de Cohen y AC1 de Gwet por criterio y total, con IC 95 % por bootstrap de informes (los mismos 5000 remuestreos para todas las filas, semilla 20261101). **El AC1 es la medida principal** cuando la prevalencia de algún codificador supera 0,85 (o es menor que 0,15), por la paradoja del kappa: con casi todo en un código, el kappa se acerca a 0 aunque haya acuerdo casi total (p. ej. C01 y C02: Luis Fer marcó presencia en los 40 informes, kappa 0,000 y AC1 0,974 y 0,890). En esta muestra esa condición se cumple en los nueve criterios.
- **AC1 ≥ 0,60 (confiables):** C01, C02, C03, C04, C07, C09. **A revisar:** C05, C06, C08 (los tres desacuerdos van en un solo sentido: Luis Fer codifica presencia y Claude no). Total: AC1 0.636, kappa de Cohen 0.185.
- **Límite:** que C01 y C02 tengan AC1 alto no significa que discriminen; casi todos los informes tienen presencia, así que aportan poca información para comparar estudios.
- **Salidas:** `outputs/tablas/confiabilidad_40_presencia.csv/.json` (git, solo números); `outputs/semantico/desacuerdos_40_presencia_luisfer_claude.csv` (ignorado). `python -m rs_pipeline.confiabilidad_40` genera D48 y D49.
- **Tests:** `tests/test_confiabilidad_40.py` (kappa de Cohen y AC1 binarios con cuenta a mano; la salida publicada contra la tabla de códigos).

## D50. Libro v3 (presencia 0/1), verificación de C05, C06 y C08 y codificación de los 196
Decisiones de Luis Fer (1 nov 2026), tomadas después de D49. Esta sesión solo **prepara**; no se codificó ningún informe.
- **Listas «cuenta / no cuenta» aprobadas** para C05, C06 y C08 (en `docs/libro_codigos_v3.md`).
  - **C05 es trabajar con datos** (medir, registrar, calcular, graficar o interpretar datos propios, concluir a partir de ellos). Explicar o argumentar con lo observado, sin datos registrados, **no cuenta**.
  - **C06 es solo lo que muestra el sistema** (puntaje, marca o mensaje de error, indicador). La respuesta visual al mover parámetros **no cuenta**. La corrección o los comentarios del docente o de pares van a **C04**.
- **Marco** (`config/criterios_v0.yaml`): en el enunciado de C06 se quitó «orientaciones de docentes o pares» y su estado pasó a «borrador: revisar Luis Fer» (ahora son borrador C01, C06 y C09). El hash del marco pasa a `6ee5e11d426e98a32cc4960829c682db04dd32306fde65e0419942fb9cf96736`. El cruce del Bloque 6 (`criterios_v0_evidencia.*`) conserva registrado el hash anterior (`5df40f49…`): no se recalculó porque solo usa `temas_origen`, que no cambió. Los libros v0, v1 y v2 **no se tocan** (siguen con el texto de C06 de D42; su `fuente_criterios.sha256` es el del marco de entonces); `escribir_libro` se niega a reescribirlos.
- **C01 y C02:** confiables en presencia pero casi universales (D49). **En el marco serán condiciones base**, no criterios que distingan estudios (queda como nota en el libro v3).
- **Libro v3** (`config/libro_codigos_v3.yaml`, `docs/libro_codigos_v3.md`; hashes `c1f7eeb671c4…` y `0b9bb5991647…`): escala 0/1, los nueve criterios, regla de duda (0), sin atribución (no importa si el grupo de comparación también tuvo el componente), lista «cuenta / no cuenta» en C05, C06 y C08, ejemplos inventados de 0 y 1. Generación: `python -m rs_pipeline.codificacion_06 --libro-v3`.
- **Plan en paralelo:** Claude codifica los **196** informes con el libro v3 en sesión limpia (4 lotes de 49) y Luis Fer codifica solo C05, C06 y C08 en **20 informes nuevos**. Si C05, C06 y C08 alcanzan **AC1 ≥ 0,60** en esos 20, los códigos de Claude de los 196 quedan validados; si no, se ajusta ese criterio y se recodifica.
- **Muestra de verificación (20):** sin el piloto, las 40 ni sus estudios (150 informes disponibles); estratificada por peso × nivel con reparto proporcional (mínimo 1 por estrato), semilla 20261031 con desplazamiento 4. Hoja `outputs/semantico/hoja_codificacion_presencia_20.csv` (ignorada, con BOM): `id_ciego` V01…V20, los 19 campos, `C05`, `C06`, `C08`, `modo_presencia` (vacía) y `nota`; correspondencia y lista aparte (ignoradas). Comando: `codificacion_06 --hoja-presencia-20`. **La columna `modo_presencia` se creó vacía y sin significado definido; falta que Luis Fer diga para qué la quiere.**
- **Hoja de los 196:** `outputs/semantico/hoja_codificacion_196.csv` (ignorada; mismas columnas que el piloto; T001…T196 en orden sorteado, desplazamiento 6) y una hoja por lote (`…_lote1.csv` a `…_lote4.csv`: T001–T049, T050–T098, T099–T147, T148–T196, para que la sesión lea solo su lote). Comando: `codificacion_06 --hoja-196`. Parámetros nuevos en `params.yaml`: `n_verificacion_presencia`, `n_lotes_196`, `max_por_lote`.
- **Registro de lotes** (`codificacion_claude --registrar … --hoja hoja_codificacion_196.csv --libro v3 --lote N`): el lote debe traer exactamente los informes del lote N (valida sus propios id); los códigos permitidos salen de la escala del libro (en v3, solo 0 y 1); los códigos van a `codigos_claude_196_v3.csv`. Sin `--lote` se conserva el comportamiento anterior (hoja completa).
- **Protocolo** (`docs/protocolo_codificacion_ciega.md`): la sesión limpia lee solo el protocolo, el libro v3, la hoja de su lote y, si hace falta, `codificacion_claude.py`; no abre `codigos_luisfer_*`, `notas_*`, hojas del piloto, 40 o 20, `logs/` ni `codigos_claude_*`.
- **Límites que conviene tener presentes:** (a) con 20 informes el IC del AC1 será ancho; (b) la confiabilidad de C01–C04, C07 y C09 se midió con el texto del libro v2 colapsado a presencia (D49), no con el texto del v3; (c) C05, C06 y C08 se verifican con las listas nuevas, pero los criterios C01, C06 y C09 siguen en borrador.
- **Tests:** `tests/test_presencia_v3.py` (libro v3 contra el marco, listas y notas, libros históricos con hash fijo, lotes, muestra de 20 sin repetir y con el mismo reparto proporcional, hoja de 196 y sus lotes, validación de lotes parciales y del código 2, nombre del CSV, protocolo). **Dos tests existentes cambiados por especificación** (como en D46), porque el marco cambió: `test_libro_repite_los_criterios_y_la_escala` (el libro v0 conserva el C06 de D42) y `test_marco_de_criterios_v0_cubre_los_20_temas_una_vez` (el conjunto de criterios en borrador ahora es C01, C06 y C09).

## D51. Verificación de C05, C06 y C08 en 20 informes (Luis Fer frente a Claude, libro v3)
Sesión del 1 nov 2026, con acceso a todo (no es la de codificación ciega). Luis Fer codificó a ciegas C05, C06 y C08 en 20 informes nuevos (V01–V20); Claude había codificado los 196 con el libro v3 (T001–T196).
- **Cruce:** V → id real (correspondencia de la hoja de 20) → T (correspondencia de la hoja de 196). Los 20 están entre los 196, sin repetidos. Los códigos de Claude salen de `logs/codificacion_claude.jsonl` filtrado por el hash del libro v3 (`c1f7eeb6…`), modelo `claude-sonnet-5-5`.
- **Medidas** (`python -m rs_pipeline.verificacion_presencia_20`, reutiliza `fila_presencia` de `confiabilidad_40.py`): % de acuerdo, kappa de Cohen y AC1 de Gwet sobre presencia 0/1, con IC 95 % por bootstrap de informes (5000 remuestreos, semilla 20261101) y prevalencia de cada codificador.

| Criterio | Acuerdo | Prev. Luis Fer | Prev. Claude | Kappa (IC 95 %) | AC1 (IC 95 %) | Veredicto |
|---|---|---|---|---|---|---|
| C05 | 11/20 (55,0 %) | 0,95 | 0,50 | 0,100 (0,000 a 0,342) | 0,252 (−0,271 a 0,656) | adjudicar |
| C06 | 5/20 (25,0 %) | 0,85 | 0,10 | 0,038 (−0,000 a 0,141) | −0,496 (−0,800 a −0,076) | adjudicar |
| C08 | 7/20 (35,0 %) | 0,95 | 0,30 | 0,044 (0,000 a 0,174) | −0,224 (−0,663 a 0,309) | adjudicar |

- **Veredicto (umbral fijado en D50: AC1 ≥ 0,60):** ninguno de los tres criterios se valida. Hay 37 desacuerdos (C05 9, C06 15, C08 13) y **todos van en el mismo sentido: Luis Fer codifica 1 y Claude 0**, como en D49. Los códigos de Claude de C05, C06 y C08 en los 196 **no quedan validados**.
- **Cómo leerlo:** la prevalencia de Luis Fer es casi universal (0,85–0,95), así que el AC1 depende mucho de cuántos 0 asigna Claude. Con n = 20 los IC son anchos (el de C05 llega a 0,656). Un AC1 negativo (C06) significa menos acuerdo del que se esperaría por azar dadas las prevalencias de cada uno. El patrón (un solo sentido, repetido de la muestra de 40 a esta) apunta a un umbral distinto entre los dos codificadores, no a ruido; qué umbral es el correcto es una decisión de Luis Fer, no de Claude.
- **Adjudicación (pendiente de Luis Fer):** `outputs/semantico/adjudicacion_presencia_20.csv` (ignorado) trae los 37 desacuerdos con la justificación de Claude y la columna `codigo_final` vacía. Luis Fer decide el código final de cada uno. El script no pisa una hoja que ya tenga códigos finales.
- **Límite de la medida «después»:** una vez adjudicados, el acuerdo entre el código final y cada codificador ya no es confiabilidad independiente (el final sale de uno de los dos). Se reportará como *cuánto de lo que cada uno marcó sobrevive a la revisión*, junto con el kappa y el AC1 «antes» de esta tabla. Falta fijar con Luis Fer qué se compara exactamente; no se calculó.
- **Salidas:** `outputs/tablas/verificacion_presencia_20.csv/.json` (git, solo números, con hash de las cinco entradas: códigos de Luis Fer, ambas correspondencias, libro v3 y registro); `desacuerdos_presencia_20_luisfer_claude.csv` y `adjudicacion_presencia_20.csv` en `outputs/semantico/` (ignorados).
- **Tests:** `tests/test_verificacion_presencia_20.py` (cruce con datos inventados y falla si un informe no está entre los 196; los 20 reales cruzan sin repetidos; la salida publicada contra los códigos fuente; la hoja de adjudicación no pisa decisiones). Total: 173.

## D52. Definición estricta de C05, C06 y C08 y cierre de la adjudicación
Decisión de Luis Fer (2 nov 2026), tomada **después de ver los resultados de D51** y de revisar los desacuerdos.
- **Definición estricta (literal):** hay presencia en C05, C06 y C08 solo si la ficha menciona explícitamente un ítem de la lista «cuenta» del libro v3. Según Luis Fer, los desacuerdos de D51 se debían a un **umbral más amplio del investigador**, no a un error de Claude. Los códigos de Claude de los 196 se mantienen; no se recodifica.
- **Verificación pedida (C05 ↔ C03):** Luis Fer sostiene que lo que veía como C05 (manipular y observar) corresponde a C03. En los 9 informes V con desacuerdo en C05, **Claude codificó C03 = 1 en 4** (V03, V07, V16 y V20) y C03 = 0 en 5. En los 6 de esos 9 que quedan en 0 (A01–A04, A06 y A09), C03 = 1 en 4 de 6; en los 3 que van a revisión, 0 de 3. **Cómo leerlo:** Claude codificó C03 = 1 en el 82,7 % de los 196 informes, así que 4 de 9 (44 %) está por debajo de esa tasa base: con los códigos de Claude, la explicación «lo que veía como C05 es C03» no se sostiene como regla. Puede seguir siendo cierta en la lectura del investigador; no queda demostrada aquí.
- **Cierre de la adjudicación** (`python -m rs_pipeline.adjudicacion_d52`, sin revisar los 37 uno a uno). Lee la hoja del lector sin modificarla:
  - A01 y A02 (decididos por Luis Fer) → 0.
  - Los 35 restantes: si la ficha contiene algún término de la lista «cuenta» del criterio → «revisar»; si no → código final 0, decisión «claude (regla D52)». Términos: C05 medi-, registr-, calcul-, tabla, dato; C06 puntaje, error, indicador, retroaliment- automática; C08 predic-, compar-, verific-, contrast-, referencia.
  - **Cómo se buscó** (mi decisión de implementación, revisable): raíz al inicio de palabra, sin tildes ni mayúsculas, en los 16 campos de texto libre de la ficha, **sin** `nivel_norm`, `disciplina_norm` ni `oe1_direccion_norm` (en esas, «media» saldría como «medi-»). «Retroalimentación automática» = ambas palabras a menos de cuatro palabras, en cualquier orden. La búsqueda detecta la palabra, no que el ítem sea el pedido: «revisar» significa «hay que mirarlo», no «probablemente 1».
  - **Resultado:** 37 casos = 2 decididos por Luis Fer + 20 en 0 por la regla D52 + **15 a revisar** (C05 3, C06 4, C08 8). Hoja de los 15 con las columnas del lector: `outputs/semantico/adjudicacion_revisar.csv`; registro de los 37 con el código final: `adjudicacion_presencia_20_cierre.csv` (ambas ignoradas).
- **Confiabilidad antes de la adjudicación (D51, sin cambios):** AC1 0,252 (C05), −0,496 (C06), −0,224 (C08); kappa de Cohen 0,100, 0,038, 0,044.
- **Prevalencia en los 20 después de la adjudicación** (de 20 informes; los 15 «revisar» pueden quedar en 0 o en 1):

| Criterio | Amplia (investigador) | Literal (Claude) | Final, mínima | Final, máxima |
|---|---|---|---|---|
| C05 | 19/20 (0,95) | 10/20 (0,50) | 10/20 (0,50) | 13/20 (0,65) |
| C06 | 17/20 (0,85) | 2/20 (0,10) | 2/20 (0,10) | 6/20 (0,30) |
| C08 | 19/20 (0,95) | 6/20 (0,30) | 6/20 (0,30) | 14/20 (0,70) |

  La prevalencia final queda como rango hasta que Luis Fer decida los 15.
- **Nota de calibración (limitaciones y recomendación para futuras revisiones):** con la lectura amplia del investigador, C05, C06 y C08 aparecen casi en todos los estudios (0,85–0,95); con la lectura literal, 0,10–0,50. La misma ficha produce prevalencias muy distintas según dónde se ponga el umbral, y eso explica por qué el AC1 de D51 fue bajo aunque no haya un codificador «equivocado». Recomendación: **fijar el umbral antes de codificar** con la lista «cuenta / no cuenta» y ejemplos límite, y calibrar a los codificadores en 3–5 informes antes de la muestra de verificación. Límites: la comparación es de 20 informes; la lectura amplia y la literal no son dos codificaciones independientes de la misma regla, sino dos reglas distintas; el cierre por palabras clave no sustituye la lectura de la ficha.
- **Salidas:** `outputs/tablas/calibracion_presencia_20.csv/.json` (git, solo números, con hash de entradas).
- **Tests:** `tests/test_adjudicacion_d52.py` (clasificación con datos inventados, «media» no cuenta como «medi-», retroalimentación automática en cualquier orden, salidas reales contra la hoja del lector, no pisa decisiones). Total: 177.

## D53. Cierre de C05, C06 y C08 en la verificación humana y terminología de la documentación
Decisiones de Luis Fer (2 nov 2026), tomadas después de D52. No cambia el contenido de las decisiones anteriores.
- **Revisión de discrepancias por el investigador, con adopción de la definición operacional estricta:** los 37 casos de `adjudicacion_presencia_20_lector.csv` y `adjudicacion_revisar.csv` quedan en **0** (los 15 que D52 dejó en «revisar» y los 22 que ya estaban en 0). Los códigos de Claude de los 196 no cambian.
- **Notas de revisión** (en la columna `nota_d53` de la hoja de cierre, ignorada):
  - **A04 (V07, C05):** Luis Fer pensó mantener 1; al verificar la ficha, la secuencia predicción → prueba es C08 y la manipulación es C03; no hay medición ni registro de datos. → 0.
  - **A11 (V03, C06):** la «retroalimentación visual inmediata» no dice qué muestra el sistema, y la del docente o de pares es C04. → 0.
  - **A01:** lo que Luis Fer veía en C05 lo asocia a C03; según D52 no se confirma con los códigos de Claude (C03 = 1 en 4 de los 9 informes, por debajo de la tasa base de 82,7 %). Se deja anotado y no se recodifica.
- **Códigos finales de la muestra de 20** (`outputs/semantico/adjudicacion_presencia_20_cierre.csv`, ignorado): 37 casos con `codigo_final` = 0 (2 decididos por Luis Fer, 20 por la regla D52, 15 por la revisión del investigador). A04 y A11 ya figuraban en 0 por la regla D52; la revisión lo confirma.
- **Prevalencia final en los 20 informes** (de 20):

| Criterio | Lectura amplia (investigador) | Final tras la revisión |
|---|---|---|
| C05 | 19/20 (0,95) | **10/20 (0,50)** |
| C06 | 17/20 (0,85) | **2/20 (0,10)** |
| C08 | 19/20 (0,95) | **6/20 (0,30)** |

  Coincide con la «prevalencia final mínima» de D52 (todo lo dudoso quedó en 0) y con la lectura literal de Claude.
- **No se calcula kappa ni AC1 después de la revisión:** el código final sale de uno de los dos codificadores y ya no hay codificadores independientes. Las medidas de confiabilidad válidas siguen siendo las de D51 (AC1 0,252, −0,496 y −0,224; kappa 0,100, 0,038 y 0,044), antes de la revisión.
- **Nota de terminología (vale para toda la documentación desde ahora; no se reescriben las decisiones anteriores).** No se usa la palabra «consenso». Se usa:

| Antes (en D44–D52) | Término desde D53 |
|---|---|
| piloto de 5 y muestra de 40 | **calibración del libro de códigos** |
| codificación de los 196 por Claude | **codificación asistida por IA con libro de códigos cerrado** |
| los 20 informes de Luis Fer (D50–D52) | **verificación humana de la codificación** |
| revisión de los 37 casos (adjudicación) | **revisión de discrepancias por el investigador, con adopción de la definición operacional estricta** |
| κ bajo de D51 | **diagnóstico de calibración (diferencia de umbral, no ruido)** |

  El uso de Claude se declara siempre de forma explícita: modelo (ID exacto), libro de códigos (versión y hash) y registro (`logs/codificacion_claude.jsonl`).
- **Salidas:** `outputs/tablas/prevalencia_final_presencia_20.csv/.json` (git, solo números, con hash de entradas). Comando: `PYTHONPATH=src .venv/bin/python -m rs_pipeline.adjudicacion_d53`. `adjudicacion_d52` se niega a reescribir un cierre que ya trae la revisión D53.
- **Tests:** `tests/test_adjudicacion_d53.py` (5 pruebas: «revisar» pasa a 0 sin tocar el resto, falla con una hoja que no tiene los 37 casos, prevalencia con cuenta a mano, salidas reales contra los códigos de Luis Fer y D52, D52 no pisa el cierre). Total: 182.

## D54. Bloque 8: tabla de evidencia del marco v0 con los códigos de presencia
Decisión de Luis Fer (2 nov 2026). Datos: `codigos_claude_196_v3.csv` (codificación asistida por IA con libro de códigos cerrado, libro v3, `claude-sonnet-5-5`), 196 informes / 193 estudios, sin los 5 excluidos por nivel. Los códigos de C05, C06 y C08 no cambian (D52, D53).
- **Estudio «presente»:** algún informe del estudio con presencia (mi decisión de implementación, igual que el cruce del Bloque 6). Peso, nivel, disciplina y dirección salen del informe de más puntos (D43). Peso y dirección se reparten **entre estudios**, no entre informes.
- **Por criterio:** n y % de informes y de estudios con presencia; reparto por peso entre los estudios presentes con la regla suma (principal) y la del mínimo (sensibilidad); reparto por nivel y disciplina; dirección del efecto (favorable / mixto / sin diferencia / no comparativo / otro) en estudios presentes vs. ausentes.
- **Fisher (solo descriptivo):** exacta bilateral, implementada con combinatoria (`math.comb`; no hay scipy y no se agregó ningún paquete), cada dirección frente al resto; se reportan las 45 pruebas (9 criterios × 5 direcciones), sin corrección por comparaciones múltiples. Con 45 pruebas se esperan por azar unas 2 con p < 0,05; solo una lo cumple (C01, mixto, p = 0,015), y C01 tiene apenas 10 estudios ausentes. No se interpreta como efecto del criterio.
- **Etiquetas:** C01 y C02 = «condición base» (casi universales: 94,4 % y 82,7 % de los informes); C06 = «brecha de diseño» (12,2 %). C05, C06 y C08 llevan la nota de calibración de D52: la prevalencia depende del umbral (con la lectura amplia era 0,85–0,95; con la definición estricta del libro v3, 0,12–0,39 en los 196).
- **Resumen** (% de estudios con peso alto por la regla suma entre los presentes; dirección «favorable» y «mixto», presentes vs. ausentes):

| Criterio | Etiqueta | Informes presentes | Estudios presentes | Peso alto (suma) | Peso alto (mínimo) | Favorable, presente vs. ausente | Mixto, presente vs. ausente |
|---|---|---|---|---|---|---|---|
| C01 | condición base | 94.4 % (185) | 94.8 % (183) | 16.4 % | 2.7 % | 32 % vs 20 % (p = 0.7269) | 22 % vs 60 % (p = 0.0148) |
| C02 | condición base | 82.7 % (162) | 82.9 % (160) | 18.1 % | 3.1 % | 30 % vs 36 % (p = 0.5365) | 24 % vs 27 % (p = 0.6605) |
| C03 | — | 82.7 % (162) | 83.4 % (161) | 17.4 % | 3.1 % | 30 % vs 38 % (p = 0.4078) | 24 % vs 28 % (p = 0.6526) |
| C04 | — | 75.0 % (147) | 75.1 % (145) | 18.6 % | 3.4 % | 31 % vs 31 % (p = 1.0) | 26 % vs 21 % (p = 0.566) |
| C05 | — | 39.3 % (77) | 39.9 % (77) | 15.6 % | 2.6 % | 26 % vs 34 % (p = 0.2664) | 27 % vs 22 % (p = 0.4947) |
| C06 | brecha de diseño | 12.2 % (24) | 12.4 % (24) | 20.8 % | 0.0 % | 21 % vs 33 % (p = 0.3464) | 38 % vs 22 % (p = 0.1283) |
| C07 | — | 58.7 % (115) | 59.6 % (115) | 13.9 % | 2.6 % | 30 % vs 33 % (p = 0.6355) | 26 % vs 22 % (p = 0.6085) |
| C08 | — | 21.9 % (43) | 22.3 % (43) | 27.9 % | 4.7 % | 40 % vs 29 % (p = 0.1933) | 21 % vs 25 % (p = 0.6877) |
| C09 | — | 70.9 % (139) | 72.0 % (139) | 13.7 % | 2.2 % | 27 % vs 41 % (p = 0.0839) | 24 % vs 26 % (p = 0.852) |

- **Cómo leerlo:** las diferencias entre presentes y ausentes en la dirección del efecto son pequeñas y sus pruebas no distinguen del azar, salvo el caso aislado ya señalado. El peso alto es bajo en todos los criterios (la regla del mínimo casi no deja estudios en «alto»). Es una descripción de cobertura y de evidencia disponible, no una comparación de eficacia entre criterios.
- **Salidas:** `outputs/tablas/marco_evidencia_v0.csv/.json` (git, solo números, con hash de entradas). Comando: `PYTHONPATH=src .venv/bin/python -m rs_pipeline.marco_evidencia_08`.
- **Tests:** `tests/test_marco_evidencia.py` (5 pruebas: Fisher con cuentas a mano, fila con datos inventados, bases 196/193, presente + ausente = total por criterio, pesos/nivel/dirección suman los presentes, n por criterio contra los códigos fuente, etiquetas y hashes). Total: 187.

## D55. Bloque 8.1: marco v1 aprobado en 3 niveles
Decisión de Luis Fer (3 nov 2026). Usa la terminología de D53. Archivo: `config/criterios_v1.yaml`.
- **Enunciados aprobados de C01, C06 y C09.** C01 pasa a «articularse con decisiones didácticas explícitas del docente antes, durante y después de la simulación». C09 agrega que el laboratorio debe declarar explícitamente sus requisitos de uso. C06 corrige su `criterio_corto`, que repetía la dimensión («Retroalimentación automática y visualización del desempeño.»), y deja explícita su frontera con C04: C04 abarca la retroalimentación de cualquier agente: respuestas del sistema, orientaciones del docente, espacios de discusión y autoevaluación (Hattie y Timperley, 2007). C06 se limita a la respuesta automática e inmediata del sistema. Los dos criterios se codificaron de forma independiente. Los 9 criterios quedan en `aprobado`.
- **Por qué v1 y no editar v0.** `config/criterios_v0.yaml` queda congelado (sha256 `6ee5e11d426e98a32cc4960829c682db04dd32306fde65e0419942fb9cf96736`): lo usan el libro v3, las salidas del Bloque 8 (con su hash) y las pruebas `test_presencia_v3`, `test_criterios`, `test_codificacion` y `test_semantico_salidas`. Editarlo cambiaría el hash que esas salidas registran y rompería la trazabilidad. La versión aprobada va en un archivo nuevo que registra el hash de v0.
- **Tres niveles.** Base: C01, C02, C03. Calidad: C04, C07, C09. Innovación: C05, C06, C08. Cada criterio lleva el campo `nivel`.
- **DUA como extensión teórica de C09.** Es una extensión teórica declarada (DUA, CAST, 2024), no sale de los datos: la accesibilidad para la diversidad de estudiantes no se codificó con el libro v3. Queda en el campo `extension_teorica` de C09.
- **Qué sostiene el marco.** Se sostiene por convergencia entre la práctica (la evidencia de los estudios), la teoría y las brechas identificadas. No se sostiene por evidencia de efecto: las diferencias de dirección del efecto entre presentes y ausentes de D54 no se distinguen del azar.
- **Campo agregado por trazabilidad.** `fuente_origen_v0` copia tal cual la fuente de v0 (hoja e5 de D42, con su hash, modelo, prueba y semilla), para que la trazabilidad llegue hasta D42 sin abrir v0. El campo `fuente` de v1 apunta a v0 con su sha256.
- **Quién lee v1.** v1 lo consumirán el Bloque 9 (homologación curricular) y la redacción del OE2; los bloques 5–8 siguen leyendo v0 por trazabilidad.
- **Tests:** `tests/test_criterios_v1.py` (15 pruebas: orden y estado, tres criterios por nivel, `dimension` y `temas_origen` iguales a v0, enunciados sin cambio iguales a v0, textos nuevos de C01, C06 y C09, hash de v0, congelamiento de v0). No se modificó ninguna prueba existente.

## D56. Bloque 9: homologación curricular latinoamericana (alcance y reglas)
Decisiones de Luis Fer (3 nov 2026). El Bloque 9 extrae los enunciados de competencias y aprendizajes de ciencias naturales de documentos curriculares oficiales y los homologa contra los 9 criterios del marco v1 (D55), las 3 competencias del ICFES y las competencias de PISA 2025. Los pasos 1 a 3 (esta decisión, el inventario y la descarga) van primero; del paso 4 en adelante van después y no deben quitarle tiempo a la redacción del Eje 3 (30 nov).
- **Alcance.** 6.º a 11.º, homologado por niveles CINE 2011 (UNESCO). CINE 2: Colombia 6–9 · Perú secundaria 1–3 · Brasil Fundamental anos finais · México secundaria · Argentina ciclo básico. CINE 3: Colombia 10–11 · Perú secundaria 4–5 · Brasil Ensino Médio · México bachillerato · Argentina ciclo orientado. Alineación por competencias, no por ítems.
- **Referentes.** ICFES: marco de 2019. PISA: OECD (2026), *PISA 2025 Assessment and Analytical Framework*, donde dos competencias anteriores quedaron fusionadas en una (cuáles y cuántas quedan: se confirma en el PDF, no se da por sabido). UNESCO entra con dos documentos que no son currículos: CINE 2011 (tabla de homologación de grados) y el análisis curricular del ERCE 2019 (antecedente metodológico y lista de contraste; no es nivel de comparación porque ERCE evalúa 6.º de primaria, CINE 1).
- **Versión vigente.** Se usa la versión vigente al 3 nov 2026. La anterior entra solo como referencia (`estado: referencia`, no se codifica). El inventario trae `acto_de_adopcion` (resolución o norma que la hace vigente) o `POR VERIFICAR`.
- **Volumen.** Se codifican **todos** los enunciados del área de ciencias naturales de 6.º a 11.º, sin filtrar por experimentación: filtrar sesgaría las brechas, que necesitan el denominador completo. Tope de **100 unidades por sesión, con commit cada 50** (cambia la regla de `CLAUDE.md`; antes eran 50 informes). `codificacion_06` sigue exigiendo 50 informes porque la codificación de informes ya terminó y no se tocó.
- **Verificación humana.** Muestra estratificada del 15 %, con mínimo 10 por celda país × CINE y tope de 200, más todas las discrepancias Claude–e5 y los criterios con prevalencia < 5 % o > 95 %. Si el total pasa de 300, se avisa a Luis Fer antes de armar la muestra.
- **Descarga de los PDF (reglas).** Solo de URL del inventario que Luis Fer aprobó (`estado: aprobado`), solo de la lista explícita de dominios, sin comodines: `educacion.gob.ar`, `educ.ar`, `argentina.gob.ar`, `minedu.gob.pe`, `gob.pe`, `sep.gob.mx`, `gob.mx`, `gov.br`, `mec.gov.br`, `mineducacion.gov.co`, `colombiaaprende.edu.co`, `icfes.gov.co`, `oecd.org`, `unesco.org`, `uis.unesco.org`. Cualquier otro dominio se consulta. Mi implementación (decisión de implementación): se acepta un dominio listado o un subdominio suyo (p. ej. `curriculonacional.minedu.gob.pe` por `minedu.gob.pe`), solo por `https` y sin usuario en la URL; una redirección a un dominio fuera de la lista hace fallar la descarga. Biblioteca estándar (`urllib`), sin paquetes nuevos. Destino `data/raw/curriculo/` (no se versiona). Por archivo se registran URL, fecha, tamaño, páginas y sha256 en el inventario. Si lo descargado no empieza con `%PDF` el script falla con mensaje claro; si el sitio pide sesión, captcha o aceptar términos, se detiene y se avisa. Nada descargado se ejecuta ni se abre con otro programa: solo se lee el texto.
- **Lectura del PDF.** `pdftotext` y `pdfinfo` del sistema (poppler 26.08.0, Homebrew), llamados con `subprocess`; no se agrega ningún paquete de Python. `pdfplumber` solo si Luis Fer lo pide.
- **Se recicla del pipeline.** Libro de códigos cerrado y codificación asistida por Claude Code (D46, registro jsonl), e5 como triangulación, verificación humana por muestra, hash por salida y pruebas contra números reales. No se usa BERTopic, MMAT ni PRISMA.
- **Inventario.** `config/referentes_curriculares.yaml`, validado por `src/rs_pipeline/referentes_09.py`. Campos: `id`, `rol` (`curriculo` / `marco_evaluacion` / `contexto_unesco`), `pais`, `organismo`, `titulo`, `version`, `fecha`, `acto_de_adopcion`, `url_oficial`, `idioma`, `nivel_cine` (lista con 2 y/o 3), `grados_originales`, `area`, `estado` (`por_verificar` / `aprobado` / `referencia`), `notas`, y los que llena la descarga: `ruta_local`, `fecha_descarga`, `tamano_bytes`, `paginas`, `sha256`. Todo año, título o versión del que no hay certeza queda como `POR VERIFICAR`.
- **Tests:** `tests/test_referentes_09.py` (esquema: campos, valores permitidos, ids únicos, nivel CINE, dominios con casos hechos a mano, descarga a medias). No se modificó ninguna prueba existente.

### Adenda a D56 (4 nov 2026)
Decisiones de Luis Fer sobre la descarga de los referentes del Bloque 9.
- **Estado `aprobado_manual`.** Es un `aprobado` cuyo PDF baja Luis Fer a mano (el sitio rechaza a los scripts: OCDE, DGB, UNESCO). El script automático no lo toca; el PDF se registra con `--ingesta-manual ID [--archivo NOMBRE.pdf]`, que comprueba la cabecera `%PDF`, cuenta las páginas con `pdfinfo` y guarda ruta, fecha, tamaño y sha256 igual que la descarga. El archivo debe estar directamente en `data/raw/curriculo/`.
- **Cambio de especificación en una prueba.** La prueba `test_aprobados_y_descargados_son_coherentes` exigía `estado == "aprobado"` en todo documento descargado. Con el estado nuevo, Luis Fer autorizó cambiar solo ese `assert` para aceptar `aprobado` y `aprobado_manual`. Ninguna otra prueba se tocó.
- **Brasil.** El PDF de 600 páginas descargado como BNCC Fundamental es la BNCC completa de 2018 (Educación Infantil, Fundamental y Medio; el PDF se creó el 13/12/2018). El Ensino Médio está ahí (los códigos `EM13CNT101…` aparecen en la página PDF 557). Un solo archivo (`BR-BNCC-2018.pdf`) sirve a los dos ids (`BR-BNCC-EF-2018` y `BR-BNCC-EM-2018`); el acto de adopción del EM es la Resolução CNE/CP nº 4/2018.
- **Argentina.** Los NAP se tomaron de las resoluciones del CFE (no de educ.ar): ciclo orientado, Res. CFE 180/12; ciclo básico, Res. CFCyE 249/05, Anexo I, cuya denominación es la de la estructura anterior (Tercer Ciclo EGB / Nivel Medio), equivalente al ciclo básico (CINE 2). `cfe.educacion.gob.ar` entra por el dominio listado `educacion.gob.ar` (regla de subdominios de D56), así que la lista no cambió.
- **Pendientes de autorización.** Descarga de documentos en estado `referencia` (México Plan 2025, ERCE) y un dominio solo para un documento (`chile.un.org` para el ERCE): chocan con una prueba que exige que solo se descarguen aprobados y con otra que fija la lista exacta de dominios. Se resuelven cuando Luis Fer autorice cambiar esas pruebas.

### Segunda adenda a D56 (4 nov 2026)
- **Sitios que bloquean scripts.** Regla de Luis Fer: si un sitio rechaza al script (403, 418 u otra señal anti-bot), Luis Fer baja el PDF a mano con el navegador y el script solo lo registra por ingesta manual. No se usan cabeceras de navegador ni otros rodeos para saltar un bloqueo. Se aplicó a la OCDE (PISA 2025), la DGB (MCCEMS), UNESCO (CINE 2011) y las resoluciones del CFE de Argentina.
- **Ingesta manual de documentos de referencia.** La ingesta manual acepta `aprobado_manual` y `referencia` (y los documentos de referencia pueden traer los campos de descarga). La descarga automática sigue exigiendo `aprobado`: un documento de referencia no se baja por script. Luis Fer autorizó el cambio mínimo de código y de su prueba: en `test_campos_de_descarga` el caso «documento que no es aprobado no puede traer campos de descarga» pasó de usar `referencia` a usar `por_verificar`, el `assert` de `test_aprobados_y_descargados_son_coherentes` (el mismo que ya se había ampliado en la primera adenda) ahora acepta también `referencia`, y se agregaron dos pruebas nuevas (referencia con campos de descarga es válido; la ingesta manual acepta referencia y la descarga automática no). No cambió la lista de 15 dominios: ni `cfe.educacion.gob.ar` (entra por `educacion.gob.ar`) ni `chile.un.org`.
- **ERCE.** Informe regional UNESCO (2020), `ark:/48223/pf0000373982` (188 páginas; Luis Fer lo bajó por `chile.un.org/es/download/56177/102656`, que entrega el archivo de UNESDOC `373982spa.pdf`). Estado `referencia`; no se codifica. Los reportes nacionales no hacen falta. La ark `pf0000373973` que figuraba antes no estaba confirmada y se descartó.
- **CINE 2011** en español, UIS/2012/INS/10/REV.2, edición 2013 (89 páginas), bajada del visor de unesdoc. **MCCEMS** de bachillerato: «Sistema Nacional de Bachillerato de la Nueva Escuela Mexicana · CNEyT · MCCEMS · Modelo Educativo 2025» (48 páginas).
- **Perú, Programa curricular de Secundaria (RM 649-2016-MINEDU).** El archivo es un escaneo sin texto. La publicación de gob.pe del 21/05/2025 (compendio «Programas curriculares de la Educación Básica Regular») es el mismo archivo (mismo sha256, confirmado por Luis Fer); queda como URL alterna en las notas del inventario. No hay versión con texto. OCR no autorizado todavía: se presentó un plan (Tesseract, solo páginas 177–194 del área de Ciencia y Tecnología).
- **México Plan 2025.** Queda como `referencia`; lo baja Luis Fer a mano y se registra por ingesta manual. Se revisa en la portada y la página legal si es una edición del Plan 2022.

## D57. Bloque 9: OCR de Perú (PE-PCS-2016), plan aprobado y piloto de 2 páginas
Decisión de Luis Fer (5 nov 2026). Cierra el pendiente «OCR no autorizado todavía» de la segunda adenda a D56: el PDF de Perú es un escaneo sin capa de texto y no hay versión con texto.
- **Aprobado.** OCR con Tesseract 5.5.2 (Leptonica 1.87.0), idioma `spa` (Homebrew; el sha256 de `spa.traineddata` queda en el JSON de procedencia) y `pdftoppm` (poppler 26.08.0) a 300 dpi. Sin paquetes de Python nuevos: ambos se llaman con `subprocess`.
- **Rango.** Solo las páginas PDF 177–194 (sección 6.9, Ciencia y Tecnología). El script rechaza cualquier otra página.
- **Recortes.** Se quita el encabezado «649-2016-MINEDU» (fracción superior 0,09 de la altura) y el pie con el número de página y la parte baja del sello de visación (se conserva hasta 0,905 de la altura). Los recortes y su valor en píxeles quedan en el JSON.
- **Salidas.** Texto y confianza por palabra (TSV) por página, con la marca «origen: OCR», en `data/processed/curriculo/PE-PCS-2016_ocr/` (fuera de git). El JSON de procedencia (versiones, sha256 de entrada y de cada salida, dpi, recortes, confianza por página, fecha) va a `outputs/ocr/` y sí se versiona; no trae texto del documento. Una página con confianza media < 85 se marca `bajo_umbral_pagina`.
- **Control de entrada.** Si el sha256 del PDF no coincide con el del inventario, el script falla.
- **Piloto (páginas 182 y 186, una con dos columnas de desempeños).** Se corrió primero solo en estas 2 páginas; las otras 16 se corrieron después de que Luis Fer aprobó el piloto. Si el OCR mezcla las columnas, se separa cada página en mitad izquierda y derecha.
- **Piloto aprobado (5 nov 2026).** Luis Fer lo revisó contra las imágenes (p186 completa y su pie sin recortar). p182: 728 palabras, confianza media 95,11; p186: 854 palabras, 94,82. Columnas sin mezclar (la izquierda se lee completa y luego la derecha) y rótulos de grado dentro del recorte. `RECORTE_INFERIOR` 0,905 no corta texto: debajo solo hay sello y número de página.
- **Error del documento original.** El rótulo «DESEMPEÑOS SEGUNDO GRADO DE PRIMARIA» de la p186 es un error del original (debe decir «de secundaria»), no del OCR. Se conserva tal cual.
- **Defectos del OCR.** (1) Las viñetas salen como `e`, `+` o `e-`. (2) La etiqueta blanca sobre negro «CICLO VI/VII» no se lee. (3) **El sello de visación borra texto, no solo lo ensucia.** En p186 se perdió entera la línea «la sociedad.» (fin del 7.º desempeño de primer grado); las líneas 70 y 72 del `.txt` quedaron dañadas y hay ruido («A 3]», «EAS»). El sello está en la misma esquina en todo el documento: es un **defecto sistemático** de las 18 páginas.
- **Control de la zona del sello.** Por página, el JSON trae `revisar_zona_sello`: las líneas de la franja inferior izquierda (último 15 % de la altura de la imagen recortada, mitad izquierda) con su confianza media. No se corrige nada automáticamente. El JSON (en git) guarda solo la referencia de cada línea (bloque, párrafo, línea, palabras, confianza); el texto de esas líneas va a `data/processed/curriculo/PE-PCS-2016_ocr/revisar_zona_sello.csv` (fuera de git, porque trae texto del documento).
- **Correcciones manuales.** Van en `data/processed/curriculo/PE-PCS-2016_ocr/correcciones.csv` (fuera de git; columnas `pagina`, `linea_txt`, `texto_ocr`, `texto_corregido`, `motivo`, `verificado_por`). La primera fila es la p186 «la sociedad.» (motivo: sello). A git va solo el resumen numérico (`outputs/ocr/PE-PCS-2016_correcciones_resumen.json`: correcciones por página).
- **Regla para la extracción (paso siguiente, aún NO hecho).** Los desempeños se cortan entre páginas (p186 → p187, en las dos columnas). Se une cada columna con la misma columna de la página siguiente. El ciclo (VI/VII) se toma del texto «nivel esperado del ciclo …», porque la etiqueta en blanco sobre negro no se lee.
- **OCR completo (18 páginas, 177–194).** Corrido el 5 nov 2026; registro en `outputs/ocr/PE-PCS-2016_ocr_p177-194.json`. Ninguna página quedó bajo el umbral de 85.
- **Batería de pruebas.** Luis Fer la corrió fuera del sandbox el 5 nov 2026: 266 passed (257 + las 9 de `test_ocr_pe_09.py`). Después se agregó una prueba (zona del sello): 10 en ese archivo; la batería completa se vuelve a correr tras el OCR completo.
- **Tests:** `tests/test_ocr_pe_09.py` (zona del sello, recorte en píxeles, confianza con conf −1 y texto vacío ignorados, páginas fuera de rango, hash distinto del inventario). No corren Tesseract.

### Adenda a D57 (5 nov 2026): revisión de p188 y recorte superior
Commit del OCR de las 18 páginas: `328d4ec` (hecho por Luis Fer fuera del sandbox). Batería: 267 passed (266 + la prueba nueva de la zona del sello; dato real, corrido por Luis Fer).
Luis Fer revisó p188 contra la imagen: el cuerpo del OCR está bien, pero hay tres problemas sistemáticos.
- **1. `RECORTE_SUPERIOR` 0,09 corta texto.** La posición de la tabla y de los títulos cambia entre páginas. En p188 partió la primera línea, el título «Competencia "Explica el mundo físico…"» (la línea 3 del `.txt` es basura). Medido sobre la franja superior (12 %) de las 18 páginas (render a 100 dpi, sin OCR): el 9 % corta la primera línea de contenido en p178, 179, 180, 184, 185, 187, 188, 190 y 191 (en 187 son las líneas «la selección natural.» y «pluricelulares para la perpetuación de la especie.», justo la continuación de p186 → p187). En p189 el encabezado mismo queda partido por el corte y deja un fragmento basura. En p181, 186 y 192 se pierde solo el rótulo «Desempeños por grado». Sin pérdida: p177, 182, 183, 193 y 194. **Estado: resuelto en la segunda adenda (recortes por página verificados, variante 1d).** Si se aprueba un cambio, el OCR de las 18 se re-corre con nueva procedencia y el JSON `PE-PCS-2016_ocr_p177-194.json` se conserva sin sobrescribir.
- **2. Números romanos.** En p188 la imagen dice «al final del ciclo VII» y el OCR leyó «ciclo VI»; las dos menciones de «nivel esperado del ciclo VII» salen bien. **Regla para la extracción:** el ciclo de una página se acepta solo si TODAS sus menciones coinciden; si no coinciden, la página va a revisión manual.
- **3. Viñetas.** En p188 no aparecen y varios desempeños quedan pegados sin línea en blanco (líneas 46–47, 58–59, 62, 71, 96–97 y 118–119 del `.txt`). **Regla para la extracción:** no depender de las viñetas; un desempeño empieza en una línea que arranca con verbo en tercera persona con mayúscula (Explica, Describe, Sustenta, Establece, Justifica, Fundamenta, Evalúa, Analiza…). El número de desempeños por grado se contrasta contra la imagen en una muestra.
- **Correcciones manuales.** Se agregó a `correcciones.csv` la fila de p188 («impacto-epila:sociedad» → «impacto en la sociedad», motivo: sello). Resumen numérico: 2 correcciones (p186: 1; p188: 1).

### Segunda adenda a D57 (5 nov 2026): recortes superiores por página (variante 1d)
Decisión de Luis Fer: ni recorte 0 con filtro del encabezado por patrón (1b) ni recorte adaptativo en cada corrida (1c). Variante 1d: **medir una vez, congelar en un archivo de configuración y revisar a ojo.**
- **Qué se reemplaza.** El recorte superior de 0,09 se eligió mirando solo dos páginas (182 y 186) y cortó texto en 9 de las 18 (178, 179, 180, 184, 185, 187, 188, 190 y 191) y partió el encabezado en una (189). Se reemplaza por recortes por página, verificados a ojo. `RECORTE_INFERIOR` 0,905 se queda fijo (ya verificado).
- **Cómo se propone el valor.** `src/rs_pipeline/recortes_pe_09.py`, solo con biblioteca estándar: `pdftoppm -gray` entrega la franja superior (15 % de la altura) a 300 dpi en PGM; por fila se calcula la proporción de píxeles oscuros (píxel < 140 de 255; la fila tiene tinta si al menos el 0,4 % son oscuros); las filas con tinta se agrupan en bandas (un hueco de menos de 6 px no parte una banda; una banda de menos de 9 px es una mota del escaneo). La primera banda es el encabezado. Recorte propuesto = fin de esa banda + margen.
- **Margen.** Hasta 6 px a 300 dpi (0,5 mm). Debe ser mayor que el borde difuso de la tinta (mínimo 3 px) y no pasar de la mitad del hueco hasta la línea de abajo, para no tocar ni el encabezado ni el texto siguiente. En p191 el hueco es de solo 10 px, así que el margen baja a 5 px; si el hueco no deja ni 3 px, el script falla en vez de aceptarlo.
- **Valores congelados.** `config/recortes_pe_pcs_2016.yaml` (en git), uno por página 177–194: `recorte_superior` (fracción), `px_300dpi`, `metodo` («propuesto por detección PGM, verificado a ojo»), `verificado_por` (**vacío hasta que Luis Fer apruebe**), `fecha` y `nota` (filas del encabezado, hueco, margen). Incluye el sha256 del PDF.
- **Evidencia para revisar** (fuera de git): `data/processed/curriculo/PE-PCS-2016_ocr/revision_recortes/`, con la franja superior (15 %) de cada página a 100 dpi y una línea roja en el recorte propuesto (`p177.png` … `p194.png` y `todas.png`, en dos columnas, de izquierda a derecha y de arriba abajo). No se corrió OCR.
- **Control en el OCR.** `ocr_pe_09.py` lee el recorte superior de ese YAML y **falla** si falta la página, si está repetida o si `verificado_por` está vacío. El JSON de procedencia registra el sha256 del YAML y el recorte de cada página. También falla si el JSON de salida ya existe, para no sobrescribir una procedencia anterior.
- **Re-corrida.** OCR de las 18 páginas con procedencia nueva `PE-PCS-2016_ocr_p177-194_v2.json`; el JSON del commit `328d4ec` no se toca ni se borra. Se compara antes y después (palabras, confianza media, primera línea leída). Hecha: ver la tercera adenda.
- **Correcciones por contexto.** `correcciones.csv` pasa de ubicar por número de línea a ubicar por contexto, porque al re-correr el OCR cambian los números: columnas `pagina`, `texto_antes`, `texto_ocr`, `texto_corregido`, `texto_despues`, `motivo`, `verificado_por`. Se actualizaron las filas de p186 y p188.
- **Pruebas.** Batería: 267 passed (dato real, corrido por Luis Fer). Después de estos cambios: 17 pruebas en `test_ocr_pe_09.py` (nuevas: recorte verificado, falta de página, falta de verificación —vacía, solo espacios o nula—, página repetida, YAML inexistente) y 8 en `test_recortes_pe_09.py` (lectura de PGM, bandas de tinta, PNG). Dos pruebas existentes de `test_ocr_pe_09.py` (recorte en píxeles) cambiaron solo la llamada, porque la función ahora recibe el recorte superior como cuarto argumento (`0.09`); sus `assert` no se tocaron.

### Tercera adenda a D57 (5 nov 2026): recortes aprobados y OCR v2
- **(a) Recortes aprobados por revisión visual.** Las 18 páginas (177–194), sin cambiar ningún valor. `verificado_por`: «Luis Fer Oviedo — revisión visual asistida por Claude, 2026-11-05».
- **(b) «Desempeños por grado» en p186 y p192.** Esa etiqueta se pierde porque comparte fila con el encabezado. No afecta: el bloque se identifica por el recuadro de competencia.
- **(c) Rótulos CICLO.** Son texto blanco sobre negro y el OCR no los lee; el ciclo se toma del texto «nivel esperado del ciclo …» (regla de la adenda anterior).
- **Datos de la corrida anterior (v1).** El 2026-11-05 se movieron a `data/processed/curriculo/PE-PCS-2016_ocr/v1/` los 54 archivos (.png, .txt y .tsv) más `revisar_zona_sello.csv`. Antes de moverlos se verificó el sha256 de los 54 contra `outputs/ocr/PE-PCS-2016_ocr_p177-194.json` del commit `328d4ec`: coinciden los 54. Ese JSON no se edita: el campo `ruta` de sus salidas es anterior al movimiento (apunta a la carpeta sin `v1/`), y los datos se localizan por nombre de archivo y sha256.
- **Hash de `revisar_zona_sello.csv` de v1** (no está en el JSON v1, porque es un archivo auxiliar): `fb0365b7a29f89699a029883ea28bdb5bc185ea7ad3a3ad3f80f70cfddb67932`. La corrida v2 generó su propio `revisar_zona_sello.csv` (33 líneas, las mismas 33 que lista el JSON v2, sin el texto), fuera de git.
- **OCR v2.** Procedencia en `outputs/ocr/PE-PCS-2016_ocr_p177-194_v2.json` (con el sha256 del PDF y el del YAML de recortes). Palabras 9701 → 9784; ninguna página bajo el umbral de 85; la confianza media de p188 sube de 93,19 a 95,34. Las páginas con texto recuperado o limpiado por el nuevo recorte: 178, 179, 180, 184, 185, 187, 188, 189, 190 y 191. En p187 vuelven «la selección natural.» y «pluricelulares para la perpetuación de la especie.», justo las líneas de la unión p186 → p187. El script ganó la opción `--sufijo` (solo letras y números) y sigue sin sobrescribir una procedencia existente.
- **Control nuevo del encabezado.** `ocr_pe_09.py` falla, sin escribir la procedencia y sin ajustar el corte, si en el texto leído de alguna página aparece «MINEDU» o «649-2016» (también con espacios o en un token del TSV), o si la primera línea de p191 (hueco de 10 px bajo el encabezado) no empieza por «Estándares». En v1 no aparecían esos textos en ninguna página, así que el control no falla por texto legítimo. Resultado en v2: pasó en las 18 y p191 empieza por «Estándares de aprendizaje…».
- **Correcciones por contexto.** Con el v2, el contexto de las dos filas de `correcciones.csv` (p186 y p188) se sigue encontrando en el texto leído.
- **Pruebas.** 33 en los dos archivos del OCR (25 en `test_ocr_pe_09.py`, 8 en `test_recortes_pe_09.py`), corridas desde una copia en el scratchpad; la suite completa la corre Luis Fer fuera del sandbox.
- **Referencia de ciclos verificada a ojo** (para la regla de consistencia de ciclo y su prueba; la regla aún NO está implementada): p181 VI · p182 VII · p183 VII · p186 VI · p188 VII · p189 VII · p192 VI · p193 VII · p194 VII. El archivo de referencia (fixture) se crea junto con la regla y su prueba, en ese paso.
- **Tabla antes/después aprobada** por Luis Fer (9701 → 9784 palabras; ninguna página bajo el umbral de 85).

## D58. Análisis de sensibilidad de la codificación con varios modelos (regla fijada antes de correr)
Decisión de Luis Fer (20 nov 2026), tomada **antes** de ver cualquier resultado. Propósito: probar si los códigos de presencia de los nueve criterios dependen del modelo que codifica y si se repiten con el mismo modelo, para reforzar la confiabilidad de la revisión de cara a su publicación.
- **Muestra (sin codificación nueva de humanos):** los 60 informes que ya tienen codificación humana: los 40 de la calibración (D47–D49) y los 20 de la verificación humana (D50–D53). Las fichas salen de la hoja de 196 y el script comprueba que son idénticas (mismo `sha256_ficha`) a las que leyó Claude en la corrida original con el libro v3.
- **Paquete ciego** (`python -m rs_pipeline.multimodelo_58 --destino ~/d58-corridas`): carpeta fuera del repositorio, solo local, con `LEEME_CODIFICADOR.md` (copia de `docs/protocolo_d58.md`), `libro_codigos_v3.md` (hash verificado) y 3 lotes de 20 fichas con códigos nuevos X01–X60 (orden al azar, semilla 20261031 + 8). Correspondencia privada en `outputs/semantico/d58_correspondencia.csv` (ignorada); manifiesto en `outputs/tablas/d58_paquete.json` (git; ids X, conteos y hashes, sin texto). Parámetros en `config/d58.yaml`.
- **Codificadores** (cuatro corridas nuevas, en paralelo con Orca, cada una en su propia copia de trabajo, sin acceso a las demás): Claude Sonnet 5.5 (el mismo modelo de la corrida original: repetición), Claude Fable 5.1, Gemini y Codex (OpenAI) con el modelo por defecto del plan de Luis Fer. Cada salida registra el identificador exacto del modelo. Mismo libro v3, mismo protocolo, mismo prompt.
- **Datos enviados a terceros:** las fichas (resúmenes estructurados de los estudios, sin datos personales) se procesan también con servicios de Google y OpenAI; se declara en la tesis.
- **Medidas (presencia 0/1, por criterio y total, con IC 95 % por bootstrap de informes: 5000 remuestreos, semilla 20261101):**
  1. **Entre modelos (medida principal):** AC1 de Gwet para varios codificadores entre las cuatro corridas nuevas, más la tabla de AC1 por pares.
  2. **Repetición:** Claude Sonnet 5.5 de D58 frente a los códigos de la corrida original (`codigos_claude_196_v3.csv`).
  3. **Frente a los humanos (secundaria):** cada modelo frente a los códigos de Luis Fer de la muestra de 40 (C01–C09; en C05, C06 y C08 son de la lectura amplia, anterior a la definición estricta de D52) y frente a los códigos ciegos de la verificación de 20 (C05, C06 y C08, antes de la revisión de discrepancias), con esa advertencia.
- **Veredicto por criterio, fijado de antemano:** AC1 ≥ 0,60 → **robusto**; 0,40 a < 0,60 → **moderado**; < 0,40 → **sensible al modelo**. Se informa además la prevalencia de cada codificador.
- **Qué NO cambia, pase lo que pase:** los códigos de los 196 informes, las tablas y las cifras de la tesis. D58 es un análisis de sensibilidad: se reporta tal cual (apartados 3.5.3, 4.4 y 6.6 de la tesis) y no se recodifica ni se ajusta el libro con estos resultados. Si un criterio resulta sensible al modelo, se declara como limitación y como recomendación para el Bloque 9 (afinar su definición antes de codificar los enunciados curriculares).
- **Tests:** `tests/test_multimodelo_58.py` (muestra de 60 sin repetidos, orden reproducible con la semilla, falla si un informe no está entre los 196 o si una ficha no coincide con la del registro, no sobrescribe un paquete, paquete real: 40 + 20, 3 lotes de 20 con los 19 campos y sin códigos, libro con su hash, manifiesto sin ids reales).

### Adenda a D58 (20 nov 2026, antes de ver resultados): Claude Fable 5.1 sale del análisis
- **Motivo:** el plan de Luis Fer se quedó sin créditos de uso para Claude Fable 5.1 al arrancar la corrida. La exclusión se decide **antes de ver cualquier código** y no depende de lo que haya codificado.
- **Si dejó archivos parciales** en su `salidas/`, no se registran ni se analizan; solo se informa cuántos lotes alcanzó a escribir.
- **Codificadores que quedan (tres, de tres proveedores):** Claude Sonnet 5.5 (Anthropic; también mide la repetición), GPT-5.6-Terra con razonamiento medium (OpenAI, vía Codex CLI 0.164.0; elegido solo para la sesión) y Gemini (Google, vía Antigravity; el modelo exacto se registra con su salida).
- **Medida principal:** AC1 de Gwet para varios codificadores entre las **tres** corridas nuevas, más los AC1 por pares. Los umbrales y la regla de no recodificar no cambian.

### Resultados de D58 (20 nov 2026)
Corridas del 20 nov 2026 en Orca, cada codificador en su propio worktree de `~/d58-corridas` (repositorio local, sin remoto). Registro: `logs/codificacion_d58.jsonl` (privado; 180 líneas, 60 por codificador, un solo registro cada uno). Cálculo: `python -m rs_pipeline.confiabilidad_58 --calcular`; salidas `outputs/tablas/d58_confiabilidad.csv/.json`.
- **Modelos.** `claude-sonnet`: claude-sonnet-5-5. `codex`: el JSON trae `"modelo": "codex"` (no el identificador exacto); según la pantalla de la sesión, **GPT-5.6-Terra con razonamiento medium**, elegido solo para esa sesión, Codex CLI 0.164.0 (vía el alias local `codex-route`, que no se modificó). `gemini`: **Gemini 3.8 Flash (High)**, vía Antigravity. El registro no se reescribe: esta nota es la fuente del modelo de `codex`.
- **Entre modelos (medida principal, 60 informes):** AC1 total **0,808** (IC 95 % 0,766–0,849) → **robusto**. Por criterio: C01 0,869 · C02 0,940 · C03 0,954 · C04 0,858 · C05 0,845 · C06 0,909 · **C07 0,466 (moderado)** · C08 0,908 · C09 0,766. Ocho de nueve criterios son robustos.
- **Por pares (total):** Sonnet–Codex 0,838 · Sonnet–Gemini 0,829 · Codex–Gemini 0,758. Sonnet y Gemini coincidieron en los 60 códigos de C05 (AC1 1,000); se informa sin interpretarlo.
- **Repetición (Sonnet de D58 frente a la corrida original):** AC1 total **0,902** (IC 0,864–0,936), 94,8 % de acuerdo; el criterio más bajo es C09 (0,783).
- **Frente a los humanos:** los modelos siguen apartándose de Luis Fer en C05, C06 y C08 (AC1 entre −0,78 y 0,39), siempre en el mismo sentido: presencia del investigador 0,93–1,00 frente a 0,10–0,57 de los modelos. Como tres modelos de tres proveedores aplican la definición estricta del libro de la misma manera (AC1 entre modelos 0,85–0,91 en esos criterios), el resultado respalda el diagnóstico de D52: **la diferencia es de umbral entre la lectura amplia del investigador y la definición operacional estricta, no ruido de la herramienta**.
- **C07 (moderado).** Prevalencias muy distintas (Codex 0,80; Sonnet 0,60; Gemini 0,40): la definición de C07 deja margen de interpretación. Según la regla de D58, no se recodifica; se declara como limitación y se recomienda afinar su lista «cuenta / no cuenta» antes de usarlo en el Bloque 9.
- **Límites de la lectura.** El acuerdo entre modelos muestra consistencia en la aplicación de la regla escrita, no exactitud frente a una verdad externa; los tres modelos son de gama intermedia (Gemini es un modelo Flash); n = 60; en C01–C03 la prevalencia es alta y el acuerdo informa poco.

## D59. Exploración de la heterogeneidad de la dirección del efecto (regla fijada antes de calcular)
Aprobada por Luis Fer el 21 nov 2026, **antes** de calcular las pruebas. El protocolo completo está en `docs/protocolo_d59.md`.
- **Preguntas:** ¿la proporción de resultados favorables cambia según (1) el nivel (secundaria frente a universitario), (2) el peso de la evidencia (alto frente a medio + bajo, regla de la suma) y (3) el comparador (clase tradicional frente a laboratorio real)? Además, se calcula la corrección de Holm de las 45 pruebas de D54. Cubre los ítems 13e, 20a y 20c de PRISMA y la quinta limitación de la tesis.
- **Base:** estudios comparativos (dirección favorable, mixto o sin diferencia); los atributos de cada estudio salen del informe de más puntos (D43, D54). No se recodifica nada.
- **Prueba:** Fisher exacta bilateral en tablas 2 × 2 (favorable frente a no favorable), una por pregunta. Las tres se corrigen con Holm (1979). No se agrega ningún paquete.
- **Qué se sabía antes:** nivel y peso no se habían cruzado. El comparador sí se miró por informe el 20 nov, en una consulta exploratoria sin registro (clase tradicional 36/50 favorables; laboratorio real 11/34). Esa pregunta no es ciega, y se declara así.
- **Reglas de lectura:** se reporta lo que salga. Con p corregido < 0,05 se habla de «diferencia observada», nunca de efecto; si no, de «no se observó diferencia». El peso y el nivel no son independientes (componente C). No se agregan pruebas después de ver los resultados.
- **Salidas (solo números, en git):** `outputs/tablas/heterogeneidad_59.csv/.json` y `outputs/tablas/holm_d54.csv`.

### Adenda a D59 (21 nov 2026, antes de calcular las pruebas): comparador por decisión del investigador
- **Por qué:** en la hoja de revisión (`--revision`, sin pruebas), las reglas de texto dejaron mal clasificados tres tipos de caso: «laboratorio tradicional» quedó en «varios»; la clase convencional escrita con otras palabras quedó en «otra»; y una negación se leyó como mención de los dos comparadores.
- **Decisión de Luis Fer:** las reglas no cambian. Las 14 decisiones manuales están en `config/comparador_d59.yaml` (7 a laboratorio real, 6 a clase tradicional y 1 a otra) y solo pueden aplicarse a estudios que la regla dejó en «varios» u «otra». El script falla en cualquier otro caso y registra el hash del archivo.
- **Alcance:** solo la pregunta del comparador, que ya no era ciega. Nivel y peso no cambian. Detalle en `docs/protocolo_d59.md`, sección «Adenda».

### Resultados de D59 (21 nov 2026)
Corrida de Luis Fer en su Terminal (`PYTHONPATH=src .venv/bin/python -m rs_pipeline.heterogeneidad_59`); batería completa: 321 pruebas superadas. Base: **117 estudios comparativos**.
- **Nivel:** secundaria 46/86 favorables (53,5 %) frente a universitario 13/28 (46,4 %); diferencia de 7,1 puntos; p = 0,664 (Holm 1,000). **No se observó una diferencia.** Fuera de la prueba: «otro», 1/3.
- **Peso de la evidencia (suma):** alto 14/29 (48,3 %) frente a medio + bajo 46/88 (52,3 %); diferencia de −4,0 puntos; p = 0,831 (Holm 1,000). **No se observó una diferencia.**
- **Comparador:** clase tradicional 38/54 (70,4 %) frente a laboratorio real 10/34 (29,4 %); diferencia de 41,0 puntos; p = 0,0002 (Holm 0,0006). **Se observó una diferencia en la proporción de resultados favorables.** Fuera de la prueba: ninguna 2/6, otra 6/15, otra simulación 2/5, varios 2/3. Recordar que esta pregunta no era ciega (protocolo, sección 2) y que usa las 14 decisiones de la adenda.
- **Holm sobre D54:** 0 de las 45 pruebas quedan por debajo de 0,05 (sin corregir: 1, la de C01 con el efecto mixto). Confirma la frase del 4.5 de la tesis.
- **Lectura, según las reglas fijadas:** son descriptivos, no efectos. Que no se observe una diferencia por nivel o por peso no prueba que no exista, porque los grupos son pequeños; además, peso y nivel no son independientes (componente C). La diferencia por comparador describe con qué se compara la simulación, no qué tan buena es: frente a una clase sin práctica, casi siempre sale favorable; frente al laboratorio real, la mayoría de los resultados son mixtos o sin diferencia.
- **Salidas:** `outputs/tablas/heterogeneidad_59.csv/.json` y `outputs/tablas/holm_d54.csv` (git). Hoja de revisión del comparador en `outputs/semantico/d59_revision_comparador.csv` (ignorada).

## D60. Bloque 9: orden y unidades para el OE3 (piloto de extracción)
Decisiones de Luis Fer (25 nov 2026), tomadas sobre el piloto de inspección de los cuatro documentos (hecho con `pdftotext`, sin escribir nada en el repo).
- **Ruta A.** Primero se extraen y codifican los referentes que exige el OE3 (instrumento de alineación): `CO-EBC-2004`, `CO-DBA-CN`, `CO-ICFES-MR-CN-S11` y `OCDE-PISA2025-MARCO`. Perú, Brasil, México y Argentina van en una segunda pasada con las mismas reglas; la regla de consistencia del ciclo de Perú (D57) queda para esa pasada.
- **Unidades.** EBC: cada viñeta de acción, con su grupo de grados y su columna (me aproximo / entorno vivo / entorno físico / CTS / desarrollo compromisos), incluida la columna actitudinal «desarrollo compromisos», porque las brechas necesitan el denominador completo (D56). DBA: cada evidencia de aprendizaje, con su DBA y su grado; los recuadros «Ejemplo» se guardan como contexto del DBA, no como unidad. ICFES: cada evidencia, con su afirmación y su competencia. PISA 2025: cada descriptor de los recuadros 2.3–2.5, en inglés (texto original); la traducción va en un campo aparte y la codificación se hace sobre el original.
- **Codificación (paso 5, aún no).** Competencia ICFES, competencia PISA y solo los criterios del marco que un currículo puede exigir (C03, C05, C08). Los demás criterios se marcan «no aplica en currículo»; C07 y C09 pasan a la matriz del instrumento como verificación técnica.
- **Regla de juicio del instrumento.** Cumple / parcial / no cumple, con evidencia citada del laboratorio (Fulmer et al., 2018).
- **Piloto (estimado).** EBC págs. 18–23, unas 231 viñetas; DBA págs. 21–39, 28 DBA y unas 99 evidencias; ICFES tabla 5, págs. 38–45, 3 competencias y 9 afirmaciones; PISA recuadros 2.3–2.5, págs. 34–36, 3 competencias. Cierra el pendiente de D56: **PISA 2025 tiene 3 competencias** (explicar fenómenos científicamente; construir y evaluar diseños de indagación e interpretar datos y evidencias críticamente; investigar, evaluar y usar información científica para tomar decisiones y actuar).
- **Orden de implementación.** Primero ICFES y PISA (tabla y recuadros limpios); después DBA y EBC, que necesitan recorte por columnas medido una vez y congelado en un YAML (como los recortes de Perú, D57).

### Adenda a D60 (26 nov 2026): nivel CINE de PISA y archivos de salida
Decisiones de Luis Fer, después del commit `4e4a97c` (extracción de ICFES y PISA).
- **PISA 2025.** En el inventario, `OCDE-PISA2025-MARCO` pasa de `nivel_cine: []` a `[2, 3]`, de acuerdo con su campo `grados_originales` (estudiantes de 15 años, CINE 2 y 3). La extracción `enunciados_09_v1.jsonl` y su resumen se hicieron con el inventario anterior (sha256 `31fa00b60917ddb2660008a237dcc3a870beef0561500dced29c408026a093ba`): en ese archivo las 15 unidades de PISA siguen con `nivel_cine: []`. No se sobrescribe.
- **Un archivo de salida por currículo.** DBA: `enunciados_09_dba_v1.jsonl`. EBC: `enunciados_09_ebc_v1.jsonl`. Ambos en `data/processed/curriculo/` (fuera de git), cada uno con su propio resumen en `outputs/tablas/`.

### Segunda adenda a D60 (26 nov 2026): recortes de los DBA aprobados y resultado del piloto
- **Resultado del piloto de columnas.** Los DBA de 6.º a 11.º (págs. 21–39) son **29 DBA y 99 evidencias**; el piloto inicial estimaba 28 DBA. Por grado (DBA / evidencias): 6.º 5/16 · 7.º 4/13 · 8.º 5/19 · 9.º 6/21 · 10.º 4/12 · 11.º 5/18.
- **Orden de lectura.** Columna izquierda, columna derecha y página siguiente. Así se repite siempre: número de DBA, «Evidencias de aprendizaje», viñetas y «Ejemplo».
- **Recortes aprobados por Luis Fer.** En puntos PDF sobre la MediaBox: columnas x = 327, superior y = 132, inferior y = 778, iguales en las 19 páginas. Quedan en `config/recortes_dba_cn.yaml` (medidos por `recortes_dba_09.py`), con `verificado_por`: «Luis Fer Oviedo — revisión visual asistida por Claude, 2026-11-26».

### Tercera adenda a D60 (26 nov 2026): extracción de los DBA
Decisiones de Luis Fer sobre `extraccion_dba_09.py`. Salida: `enunciados_09_dba_v1.jsonl` (99 unidades, fuera de git) y `outputs/tablas/extraccion_09_dba_v1.json`. La v1 se regeneró antes de su primer commit para agregar el nivel CINE por grado.
- **Nivel CINE por unidad (D56).** Cada evidencia lleva el nivel de su grado: 6.º–9.º, CINE 2 (69 unidades); 10.º–11.º, CINE 3 (30). En ICFES y PISA cada unidad sigue con el nivel de su documento en el inventario.
- **Subíndices.** Una palabra de menos de 9 pt de alto va en la línea que la contiene y se pega sin espacio a la letra que está a menos de 1 pt. Hay un solo caso: «H2O» (pág. 22).
- **Guiones al final de línea.** Un guion pegado a la palabra se conserva y no se mete espacio: en estas páginas es parte de ella («Boyle-Mariotte», pág. 28; tres cortes de una dirección web, pág. 39). No se usa la reparación de cortes de ICFES y PISA, que quita el guion. Una raya suelta conserva los espacios («Brönsted – Lowry», pág. 30).
- **Barras al final de línea.** Se unen sin espacio (aceptado por Luis Fer): «inflar/explotar» (pág. 28) y una dirección web (pág. 25).
- **«Ejemplo» solo figura.** En 9 DBA el «Ejemplo» no tiene texto y sus unidades quedan con `ejemplo: null`: G6.D1, G6.D3, G7.D1, G7.D2, G8.D1, G9.D1, G10.D1, G10.D2 y G11.D2 (27 evidencias). El script falla si la lista cambia. En los demás, el contexto guarda solo el texto: lo que dice una figura no entra.
- **El original no se corrige.** Tildes, erratas y puntuación quedan como en el PDF.

### Cuarta adenda a D60 (27 nov 2026): piloto de columnas de los EBC aprobado
- **Resultado.** Los EBC de Ciencias Naturales (págs. 18–23) tienen **231 viñetas**: 78 en 6.º–7.º, 75 en 8.º–9.º y 78 en 10.º–11.º. Coincide con el piloto inicial.

| Columna | 6.º–7.º | 8.º–9.º | 10.º–11.º |
|---|---|---|---|
| Me aproximo al conocimiento como científico-a natural | 22 | 21 | 19 |
| Entorno vivo | 16 | 15 | 12 |
| Entorno físico | 16 | 12 | 24 |
| Ciencia, tecnología y sociedad | 13 | 15 | 11 |
| Desarrollo compromisos personales y sociales | 11 | 12 | 12 |
| **Total** | **78** | **75** | **78** |

- **Seis columnas en 10.º–11.º.** «Entorno físico» está partido en «Procesos químicos» (pág. 22, 13 viñetas) y «Procesos físicos» (pág. 23, 11), y «Entorno vivo» lleva «Procesos biológicos». Decisión de Luis Fer: se cuentan como una sola columna y el subtítulo se guarda en `subcolumna`.
- **Estándares generales (contexto, no unidades).** Son **12**: 3 en 6.º–7.º, 4 en 8.º–9.º y 5 en 10.º–11.º. Las frases «Al final de … grado…» quedan fuera del contexto: solo sirven para comprobar que cada tabla es del grupo que dice.
- **Nivel CINE (D56).** 6.º–7.º y 8.º–9.º, CINE 2 (el grupo 8.º–9.º cae completo en CINE 2); 10.º–11.º, CINE 3.
- **Recortes aprobados por Luis Fer.** Uno por columna y por globo en cada página, porque cambian los anchos y la altura de los encabezados. Una palabra es de un recorte si cabe a lo ancho y el centro de su alto está entre sus límites: en las págs. 19, 21 y 23 la caja del rótulo «CIENCIAS NATURALES» del pie se monta sobre la última línea. Quedan en `config/recortes_ebc_2004.yaml` (medidos por `recortes_ebc_09.py`), con `verificado_por`: «Luis Fer Oviedo — revisión visual asistida por Claude, 2026-11-27».
