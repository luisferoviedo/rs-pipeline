# rs-pipeline

Pipeline reproducible para la revisión sistemática (PRISMA 2020) de la tesis de maestría (Tesis 04).

Qué hace hoy: recalcula los conteos PRISMA desde los CSV fuente, los compara con
`prisma_counts_2026-10-26.json` y, solo si todo cuadra, dibuja el diagrama PRISMA 2020 en español
(201 informes = 198 estudios). Las reglas de trabajo están en `CLAUDE.md` y las decisiones en
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

## Verificar
```
.venv/bin/pytest            # tests contra los CSV reales (requiere RS_DRIVE_ROOT)
.venv/bin/ruff check .
.venv/bin/pip-audit --local # cada vez que cambie requirements.txt y antes de cada push
```

## Licencia
Código: MIT (ver `LICENSE`). Los textos completos y los PDF no se publican.
