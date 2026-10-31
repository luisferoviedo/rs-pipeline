# rs-pipeline

Pipeline reproducible para la revisión sistemática (PRISMA 2020) de la tesis de maestría (Tesis 04).

Qué hace hoy: recalcula los conteos PRISMA desde los CSV fuente, los compara con
`prisma_counts_2026-10-26.json` y, solo si todo cuadra, dibuja el diagrama PRISMA 2020 en español
(196 informes = 193 estudios tras las exclusiones de nivel, D33). Las reglas de trabajo están en `CLAUDE.md` y las decisiones en
`docs/decisiones.md`.

## Datos
Los datos viven en un Google Drive de solo lectura y no se suben al repositorio.
La carpeta `Cribado_Bibliografia_PRISMA` se indica con la variable `RS_DRIVE_ROOT`.

## Preparar el entorno (una sola vez)
```
/opt/homebrew/bin/python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env        # y completa RS_DRIVE_ROOT con la ruta de la carpeta del Drive
.venv/bin/pre-commit install
```
`gitleaks` se instala aparte con `brew install gitleaks`.

## Regenerar el diagrama
```
.venv/bin/python src/rs_pipeline/prisma_02.py
```
Las exclusiones de nivel (`config/exclusiones_nivel.yaml`, D33) se aplican en memoria; la versión vigente de los conteos se escribe en el repo con `--derivar-counts` (`config/prisma_counts_2026-10-29.json`; el Drive no se toca):
```
.venv/bin/python src/rs_pipeline/prisma_02.py --derivar-counts
```
El script imprime un reporte (conteos calculados frente al JSON, desglose de los no recuperados,
IDs a revisar y hashes de las entradas). Termina con error y **no dibuja nada** si falta un archivo,
una columna o un ID, o si algún conteo no cuadra.

Si todo cuadra escribe en `outputs/figuras/`:
- `Diagrama_PRISMA_2020_Eje3_<fecha>.svg` y `.png` (el PNG es de 2x el tamaño del SVG).
- `Diagrama_PRISMA_2020_Eje3_<fecha>.json`: trazabilidad (ruta y hash de cada entrada y de cada
  salida, versiones, conteos y avisos). `<fecha>` es la del JSON de conteos.

El diagrama no lleva título: el número y el título van fuera de la imagen (APA 7).
Los textos de E1 a E5, de los no recuperados y los grupos de fuentes se cambian en `config/params.yaml`.
Las reclasificaciones del cribado están en `config/reclasificaciones.yaml`.

## Normalizar la matriz de extracción
```
PYTHONPATH=src .venv/bin/python -m rs_pipeline.normalizar_01
```
Quita los 18 E4, aplica `config/categorias.yaml` y escribe en `data/processed/` (fuera de git) la matriz
normalizada de 201 filas (los 5 excluidos por nivel se marcan en `excluido_nivel`, no se borran; D34) y un `.json` con ruta y hash de cada entrada. Las columnas originales se
conservan; las normalizadas son nuevas (`*_norm`, columnas 0/1 y de detalle). Un valor sin mapear hace fallar el script.

## Descriptivos de la matriz normalizada
```
PYTHONPATH=src .venv/bin/python -m rs_pipeline.descriptivos_03
```
Lee la matriz de `data/processed/` (falla si cambió desde que se normalizó) y escribe en `outputs/tablas/` una tabla CSV con su `.json` de trazabilidad: año (de la base de datos), quinquenio, idioma, país, nivel, disciplina, MMAT, dirección, herramientas, resultados y el cruce disciplina x herramienta. Base: 196 informes; 193 estudios donde se indica (los conteos salen de `config/prisma_counts_2026-10-29.json`, D34).
También escribe `revision_elegibilidad_nivel.csv` (salida local, no versionada porque trae fragmentos de los artículos; solo se versiona su `.json`, D30): los 32 informes cuyo nivel toca la elegibilidad, con las decisiones de Luis Fer en `decision_luisfer` (D33). No cambia el PRISMA por sí solo: las exclusiones salen de `config/exclusiones_nivel.yaml`.

## Flujograma y procedimiento
- `docs/PROCEDIMIENTO.md`: qué hace cada bloque, con qué datos, decisiones y controles.
- `docs/flujograma.mmd` y `docs/flujograma.svg`: flujograma del pipeline completo (frontera Drive solo lectura / repositorio).
Para regenerar el SVG hace falta Node y Chrome; `mermaid-cli` se descarga por `npx` a la caché de npm y no se agrega al repositorio:
```
PUPPETEER_SKIP_DOWNLOAD=1 PUPPETEER_EXECUTABLE_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  npx -y @mermaid-js/mermaid-cli@12.0.0 -i docs/flujograma.mmd -o docs/flujograma.svg
```

## Mini-sprint semántico (BERTopic, local)
Venv aparte para no tocar el pipeline: `.venv/bin/python -m venv .venv-semantico` y
`.venv-semantico/bin/pip install -r requirements-semantico.txt`. Los modelos de Hugging Face se descargan fijados a su
revisión de `config/params.yaml` (caché fuera del repo). Todo corre sin red y sin llamadas a la API:
```
PYTHONPATH=src .venv-semantico/bin/python -m rs_pipeline.semantico_04                  # las tres pruebas
PYTHONPATH=src .venv-semantico/bin/python -m rs_pipeline.semantico_04 --hoja-2b        # rehace la hoja a ciegas (no pisa una calificada)
PYTHONPATH=src .venv/bin/python -m rs_pipeline.semantico_04 --calificacion-2b          # % interpretables por modelo y veredicto
```
Lo que trae texto de los artículos (hoja a ciegas, asignaciones) queda en `outputs/semantico/` (ignorado por git);
a git solo van las métricas numéricas de `outputs/semantico_metricas/`.

## Verificar
```
.venv/bin/pytest            # tests contra los CSV reales (requiere RS_DRIVE_ROOT)
.venv/bin/ruff check .
.venv/bin/pip-audit --local # cada vez que cambie requirements.txt y antes de cada push
```

## Licencia
Código: MIT (ver `LICENSE`). Los textos completos y los PDF no se publican.
