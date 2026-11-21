# rs-pipeline

[![DOI](https://zenodo.org/badge/1439206711.svg)](https://doi.org/10.5281/zenodo.24377703)

**Pipeline reproducible para revisiones sistemáticas con codificación asistida por IA, aplicado a laboratorios virtuales de ciencias naturales.**

Este repositorio contiene el procesamiento de datos de la revisión sistemática (PRISMA 2020) de la tesis de maestría «Del laboratorio ausente al laboratorio digital: criterios de diseño para laboratorios virtuales de ciencias naturales pertinentes al currículo colombiano y viables en condiciones de conectividad limitada» (Maestría en Educación para la Innovación Pedagógica, Fundación Universitaria del Área Andina). A partir de 196 informes incluidos (193 estudios), el pipeline recalcula los conteos PRISMA, normaliza la matriz de extracción, agrupa las unidades de texto con síntesis temática, codifica la presencia de nueve criterios de diseño con un libro de códigos cerrado y calcula su confiabilidad y el peso de la evidencia que los respalda.

## Qué garantiza
- **Trazabilidad.** Cada salida registra la ruta y el hash SHA-256 de los archivos de los que proviene.
- **Decisiones fechadas.** Cada decisión metodológica queda en `docs/decisiones.md` (D1, D2, …) con su fecha y su justificación.
- **Pruebas contra números reales.** Las pruebas automatizadas (`tests/`; 267 en la última corrida completa, 5 nov 2026) comprueban los conteos contra las tablas fuente, no solo que el código corra.
- **Fallas visibles.** Si falta un archivo, una columna o un ID, o si un conteo no cuadra, el script se detiene con un mensaje claro.
- **Originales intactos.** Los datos de la revisión se leen en modo solo lectura; ningún paso los modifica.

## Estado
| Bloque | Contenido | Estado |
|---|---|---|
| 1–4 | Conteos y diagrama PRISMA, normalización, descriptivos, exclusiones por nivel | Terminado |
| 5 | Síntesis temática inductiva (BERTopic con modelos multilingües) | Terminado |
| 6–8.1 | Marco de criterios, libro de códigos, codificación deductiva, confiabilidad y peso de la evidencia; marco v1 en tres niveles | Terminado |
| 9 | Homologación curricular latinoamericana (Colombia, Perú, Brasil, México y Argentina) contra el marco, el ICFES y PISA 2025 | En curso |

El detalle de cada bloque (entradas, proceso, comandos, controles y salidas) está en `docs/PROCEDIMIENTO.md`; el flujograma, en `docs/flujograma.svg`.

## Uso de inteligencia artificial
La clasificación preliminar de registros en el cribado, el diligenciamiento de las fichas de extracción y la codificación deductiva se apoyaron en un modelo de lenguaje generativo de gran escala (Claude, Anthropic), ejecutado mediante Claude Code y bajo control humano: los investigadores fijaron las reglas (libro de códigos cerrado), la herramienta codificó en sesiones sin acceso a la codificación humana (`docs/protocolo_codificacion_ciega.md`) y los resultados se verificaron con muestras codificadas a ciegas por el investigador. Cada código asignado quedó registrado con la fecha, el identificador exacto del modelo, el hash del libro de códigos y una justificación (el registro no se publica porque contiene fragmentos de las fichas). Las medidas de confiabilidad y sus límites están en las decisiones D48 a D53.

## Cómo citar
Oviedo Berrocal, L. F. (2026). *rs-pipeline: Pipeline reproducible para revisiones sistemáticas con codificación asistida por IA, aplicado a laboratorios virtuales de ciencias naturales* (Versión 1.1-eje3) [Software]. Zenodo. https://doi.org/10.5281/zenodo.24399152

- DOI de la versión 1.1-eje3 (la que acompaña el Eje 3 de la tesis; incluye el análisis de sensibilidad con tres modelos, D58): [10.5281/zenodo.24399152](https://doi.org/10.5281/zenodo.24399152)
- DOI de la versión 1.0-eje3 (anterior): [10.5281/zenodo.24377704](https://doi.org/10.5281/zenodo.24377704)
- DOI del proyecto (todas las versiones; lleva siempre a la más reciente): [10.5281/zenodo.24377703](https://doi.org/10.5281/zenodo.24377703)
- También puede usar el botón «Cite this repository» de GitHub (archivo `CITATION.cff`).

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

## Cómo adaptarlo a otra revisión
El método no depende del tema; el código sí está ajustado a esta revisión. Para usarlo en otra área (por ejemplo, salud, ingeniería o inocuidad alimentaria) hay que reemplazar, como mínimo:
1. **Rutas y textos del PRISMA:** `config/params.yaml` (carpeta de datos, ventana de búsqueda, fuentes, etiquetas de exclusión E1–E5 y de no recuperados) y los conteos de referencia `config/prisma_counts_*.json`, `config/reclasificaciones.yaml` y `config/exclusiones_nivel.yaml`.
2. **La ficha de extracción:** los nombres de las columnas están en el código de `normalizar_01.py`, `descriptivos_03.py`, `criterios_05.py`, `codificacion_06.py` y `semantico_04.py`, y las categorías normalizadas en `config/categorias.yaml`.
3. **Los criterios y el libro de códigos:** `config/criterios_v1.yaml` y un libro propio con la estructura de `config/libro_codigos_v3.yaml` (qué cuenta y qué no cuenta como presencia, con ejemplos).
4. **Las pruebas:** las de `tests/` verifican los números de esta revisión; en una revisión nueva deben reescribirse con sus propios conteos.

Recomendación aprendida en esta revisión (D52): fijar el umbral de cada criterio con ejemplos límite y calibrar a los codificadores en 3 a 5 informes **antes** de la muestra de verificación.

## Licencia
Código: MIT (ver `LICENSE`). Los textos completos, los PDF y las salidas con fragmentos de los artículos no se publican; se conservan en el Drive de los investigadores.
