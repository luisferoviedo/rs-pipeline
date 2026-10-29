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
