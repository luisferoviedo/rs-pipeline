# rs-pipeline

Pipeline reproducible para la revisión sistemática (PRISMA 2020) de la tesis de maestría (Tesis 04).

Estado: en construcción. Primero se recalculan y verifican los conteos PRISMA desde los CSV fuente
y después se genera el diagrama. Las reglas de trabajo están en `CLAUDE.md` y las decisiones en
`docs/decisiones.md`.

## Datos
Los datos viven en un Google Drive de solo lectura y no se suben al repositorio.
Indica su ubicación con la variable de entorno `RS_DRIVE_ROOT` (carpeta `Cribado_Bibliografia_PRISMA`).

## Licencia
Código: MIT (ver `LICENSE`). Los textos completos no se publican.

## Uso
```
# desde la raíz del repo, con el venv activo y RS_DRIVE_ROOT en .env
python src/rs_pipeline/prisma_02.py
pytest
```
