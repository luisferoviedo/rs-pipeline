# Protocolo de codificación sin anclaje: 196 informes con el libro v3 · D50

Para la sesión nueva de Claude Code que codifica **un lote** de la hoja de 196. La sesión debe partir de cero (`/clear` o una terminal nueva), de modo que no tenga a la vista los códigos de Luis Fer ni los de lotes anteriores. Se codifica un lote por sesión (49 informes; máximo 50 según `CLAUDE.md`).

`CLAUDE.md` lo carga Claude Code solo. Para esta tarea mandan este protocolo y el prompt del lote: no se propone un plan ni se espera aprobación.

## Qué se puede leer (solo esto)
1. Este protocolo.
2. `docs/libro_codigos_v3.md` (libro de códigos v3: presencia 0/1).
3. La hoja **del lote** que se codifica: `outputs/semantico/hoja_codificacion_196_lote{N}.csv` (49 informes T…, 19 campos de la ficha cada uno).
4. Si hace falta, `src/rs_pipeline/codificacion_claude.py` (solo para ver el formato del lote).

## Qué NO se debe abrir
- En `outputs/semantico/`: `codigos_luisfer_*`, `notas_*`, las hojas del piloto, de las 40 y de las 20 (`hoja_codificacion_piloto*`, `hoja_codificacion_40*`, `hoja_codificacion_presencia_20*`), cualquier `codigos_claude_*` (incluidos los de lotes anteriores), `desacuerdos_*`, `sugerencias_*`, `*correspondencia*`, `muestra_*`, la hoja completa `hoja_codificacion_196.csv`, las hojas de los otros lotes y los `lote_codificacion_*` de otros lotes.
- `logs/` (el registro se escribe solo con el comando de registro; no se lee).
- `docs/decisiones.md`, `docs/PROCEDIMIENTO.md` y los libros v0, v1 y v2.
- En `outputs/tablas/`: los archivos de acuerdo, de confiabilidad o de resumen.
- No se corre `git log`, `git show` ni `git diff` para ver mensajes o cambios de commits anteriores.
- No se usa Python ni otra herramienta para leer ninguno de los archivos prohibidos. Se puede usar Python para armar el JSON del lote.

## Cómo codificar
1. Leer el libro v3 completo (escala 0/1, reglas, criterios C01–C09, listas «cuenta / no cuenta» de C05, C06 y C08).
2. Leer la hoja del lote en tandas de 10 informes. Codificar solo con lo que dice la ficha; ante la duda entre 0 y 1, el 0.
3. Por cada informe, los nueve criterios C01 a C09 **en ese orden**, cada uno con un código 0 o 1 y **una justificación de una línea** (sin copiar texto de la ficha).
4. Escribir un solo archivo `outputs/semantico/lote_codificacion_196_lote{N}.json` con exactamente los informes de la hoja del lote (el modelo es el ID exacto que usa la sesión):
```json
{"modelo": "<ID exacto del modelo>",
 "informes": {"T001": {"codigos": {"C01": 1, "C02": 0, "...": 0, "C09": 1},
                       "justificaciones": {"C01": "una línea", "C02": "una línea", "...": "...", "C09": "una línea"}},
              "T002": {"...": "..."}}}
```
5. Registrar el lote (valida todos los informes antes de escribir; agrega una línea por informe a `logs/codificacion_claude.jsonl` y a `outputs/semantico/codigos_claude_196_v3.csv`, y actualiza el resumen numérico):
```
PYTHONPATH=src .venv/bin/python -m rs_pipeline.codificacion_claude --registrar outputs/semantico/lote_codificacion_196_lote{N}.json --hoja hoja_codificacion_196.csv --libro v3 --lote {N}
```
   Si el comando falla, se corrige el JSON y se repite: no escribe nada hasta que todo el lote es válido.
6. Hacer commit solo de `outputs/tablas/codificacion_claude_resumen.json` (los códigos y justificaciones quedan fuera de git) y **no hacer push**.
7. Terminar diciendo solo cuántos informes se registraron y con qué modelo. No mostrar códigos ni justificaciones, y no compararlos con nada.

## Lotes
Los informes están en `outputs/semantico/hoja_codificacion_196.csv` (T001…T196, en orden sorteado) y se reparten en cuatro lotes consecutivos de 49: lote 1 = T001–T049, lote 2 = T050–T098, lote 3 = T099–T147, lote 4 = T148–T196. El comando de registro valida que el JSON traiga exactamente los informes del lote indicado con `--lote`.

Si hay que repetir un informe, se agrega una nueva línea con su fecha; nunca se edita el registro anterior.

## Historial
La muestra de 40 (D47) se codificó con el libro v2 siguiendo la versión anterior de este protocolo; ese lote está cerrado y no se vuelve a codificar.
