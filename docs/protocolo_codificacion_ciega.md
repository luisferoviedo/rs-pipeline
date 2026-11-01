# Protocolo de codificación sin anclaje (muestra de 40) · D47

Para la sesión nueva de Claude Code que codifica la muestra de confiabilidad. La sesión debe partir de cero (`/clear` o una terminal nueva), de modo que no tenga a la vista los códigos del piloto de Luis Fer ni los suyos.

## Qué se puede leer (solo esto)
1. `docs/libro_codigos_v2.md` (el libro de códigos v2).
2. `outputs/semantico/hoja_codificacion_40.csv` (40 informes M01…M40, 19 campos de la ficha cada uno).
3. Este protocolo y `CLAUDE.md`.

## Qué NO se debe abrir
`logs/`; `docs/decisiones.md`, `docs/PROCEDIMIENTO.md` y los libros v0 y v1; en `outputs/semantico/`: la hoja del piloto y su respaldo, `codigos_claude_*`, `desacuerdos_*`, `sugerencias_*`, `*correspondencia*`, `muestra_confiabilidad_40.csv`, `lote_*` y cualquier otro archivo; los archivos de `outputs/tablas/` de acuerdo o de resumen. Tampoco se corre `git log` ni `git show` para ver mensajes o diffs de los commits anteriores.

## Cómo codificar
1. Leer el libro v2 completo (escala 0/1/2, reglas, criterios C01–C09, ejemplos).
2. Leer la hoja en tandas de 10 informes. Codificar solo con lo que dice la ficha; ante la duda entre dos códigos, el menor.
3. Por cada informe, los nueve criterios C01 a C09, cada uno con un código 0, 1 o 2 y **una justificación de una línea** (sin copiar texto de la ficha).
4. Escribir un solo archivo `outputs/semantico/lote_codificacion_40.json` con esta forma (el modelo es el ID exacto que usa la sesión):
```json
{"modelo": "<ID exacto del modelo>",
 "informes": {"M01": {"codigos": {"C01": 1, "C02": 0, "...": 0, "C09": 1},
                      "justificaciones": {"C01": "una línea", "C02": "una línea", "...": "...", "C09": "una línea"}},
              "M02": {"...": "..."}}}
```
5. Registrar el lote (agrega una línea por informe a `logs/codificacion_claude.jsonl` y al archivo ignorado `outputs/semantico/codigos_claude_40.csv`, y actualiza el resumen numérico):
```
PYTHONPATH=src .venv/bin/python -m rs_pipeline.codificacion_claude --registrar outputs/semantico/lote_codificacion_40.json --hoja hoja_codificacion_40.csv --libro v2
```
6. Hacer commit solo de `outputs/tablas/codificacion_claude_resumen.json` (los códigos y justificaciones quedan fuera de git) y **no hacer push**.
7. Terminar diciendo solo cuántos informes se registraron. No mostrar códigos ni justificaciones, y no compararlos con nada.

Máximo 50 informes por sesión. Si hay que repetir un informe, se agrega una nueva línea con su fecha; nunca se edita el registro anterior.
