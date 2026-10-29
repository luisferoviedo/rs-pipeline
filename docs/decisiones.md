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
- Observación sin efecto en los conteos: 9 registros están como D en el cribado y como I en recuperación (I/D no entra en PRISMA). Solo se reporta.
- `identificados` y `duplicados` quedan como declarados, sin verificar (ver D3). El 198 sí se verifica (D12).

## D11. PDF de otro documento
Todo informe contado como "PDF de otro documento" (15) debe ser `NO_CORRESPONDE` en elegibilidad o tener su PDF en `03_recuperacion/artículos_pdf/_no_corresponde/`; si no, el script falla. Los 5 sin fila en elegibilidad (R0008, R0051, R0905, R0934, R0973) fueron revisados por Luis Fer y sus PDF están en esa carpeta. La carpeta tiene 15 PDF, igual que los contados. El script registra el SHA-256 de cada PDF en el reporte; los PDF no se suben a git.

## D12. Estudios (198)
Se verifican por script con `estudio_compartido_con` de `Extraccion_datos_v2_2026-10-18.csv`, excluyendo los 18 E4 de los dudosos: 201 informes = 198 estudios con 3 pares (R0177+R0188, R0844+R0930, R0990+R1031). Los IDs de extracción deben ser iguales a los INCLUIDOS de elegibilidad (219). Si no cuadra, falla.
