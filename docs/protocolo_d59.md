# Protocolo D59 · Exploración de la heterogeneidad de la dirección del efecto

**Estado:** aprobado por Luis Fer el 21 nov 2026. Las reglas se fijaron **antes** de calcular cualquier cruce de nivel o de peso, y la adenda (al final), antes de calcular las pruebas.

## 1. Propósito

Responder, con datos que ya existen, tres preguntas que hoy la tesis deja abiertas (ítems 13e, 20a y 20c de PRISMA 2020 y la quinta limitación del 6.6):

1. **Nivel:** ¿la proporción de resultados favorables a la simulación es distinta en secundaria que en el nivel universitario?
2. **Peso de la evidencia:** ¿los estudios de peso alto muestran la misma proporción de resultados favorables que los de peso medio o bajo?
3. **Comparador:** ¿la proporción de resultados favorables es distinta cuando se compara con la clase tradicional que cuando se compara con el laboratorio real?

Además, el script deja trazable la **corrección de Holm** sobre las 45 pruebas de Fisher de D54, que la tesis cita (4.5).

**Es exploratorio y descriptivo.** No estima efectos ni busca causas: describe si la dirección del efecto se reparte distinto entre grupos.

## 2. Qué se sabe antes de fijar las reglas

- **Nivel y peso:** no se ha calculado ningún cruce.
- **Comparador:** el 20 nov se hizo una consulta exploratoria **por informe**, fuera del pipeline y sin registro: frente a la clase tradicional, 36 de 50 informes fueron favorables; frente al laboratorio real, 11 de 34. Por eso, la pregunta 3 **no es ciega**. Se declara así, y D59 la vuelve trazable y la recalcula por estudio.

## 3. Datos de entrada (nada se recodifica)

- **Matriz normalizada:** `data/processed/Extraccion_datos_v2_2026-10-18_normalizada.csv`, con su hash. Base: 196 informes y 193 estudios, sin los 5 excluidos por nivel.
- **Peso, nivel y dirección por informe:** calculados como en D43, con las funciones de `criterios_05` (`tabla_de_informes`). No se cambia ninguna regla de puntos.
- **Comparador:** la columna `comparacion` de la matriz.
- **Las 45 pruebas de D54:** `outputs/tablas/marco_evidencia_v0.csv`, con su hash.

## 4. Unidad de análisis y base

- **Unidad: el estudio (193).** Los atributos de un estudio con dos informes salen del informe de más puntos y, a igual puntaje, del de menor id. Es la misma regla de D43 y D54.
- **Base de los tres cruces:** los estudios **comparativos**, es decir, aquellos cuya dirección es `favorable`, `mixto` o `sin_diferencia`.
  - Quedan fuera los `no_comparativo` (no tienen dirección) y el estudio `otro`, que compara dos versiones de la misma simulación.
  - El número exacto de estudios comparativos sale del script. El script falla si las categorías no suman la base.

## 5. Variable de resultado

- **Favorable** frente a **no favorable**. «No favorable» agrupa `mixto` y `sin_diferencia`.
- **Por qué dos categorías:** porque así queda una sola prueba por pregunta. Si se usaran tres, habría más pruebas y celdas muy pequeñas.

## 6. Grupos de cada cruce

| Cruce | Grupo 1 | Grupo 2 | Se informa, pero queda fuera de la prueba |
|---|---|---|---|
| Nivel | `secundaria` | `universitario` | `otro` (mixto y formación docente) |
| Peso (regla de la suma) | `alto` | `medio` + `bajo` | — |
| Comparador | `clase tradicional` | `laboratorio real` | `otra simulación`, `otra`, `ninguna`, `varios` |

- **Nivel:** se usa la agrupación `NIVEL_GRUPO` de `criterios_05`, sin cambios. El grupo `universitario` incluye «2.º año o superior» y «año no reportado».
- **Peso:** se usa la regla de la suma de D43, la principal. La regla del mínimo no entra, porque casi no deja estudios con peso alto.
- **Comparador:** se clasifica con reglas de texto sobre `comparacion`, sin tildes y sin distinguir mayúsculas:
  - Si menciona «laboratorio real» y no menciona «tradicional» → `laboratorio real`.
  - Si menciona «tradicional» y no menciona «laboratorio real» → `clase tradicional`.
  - Si menciona los dos → `varios`.
  - Si empieza por «ninguna» → `ninguna`.
  - Si menciona «otra simulación» → `otra simulación`.
  - En cualquier otro caso → `otra`.
  - El script lista cuántos estudios quedan en cada categoría. Antes de correr la prueba, Luis Fer revisa a ojo los casos `varios` y `otra`.

## 7. Prueba estadística

- **Fisher exacta, bilateral**, sobre una tabla 2 × 2 por cruce (grupo × favorable o no favorable). Se reutiliza `fisher_dos_colas` de `marco_evidencia_08`, que ya tiene sus pruebas. **No se agrega ningún paquete.**
- **Tres pruebas en total.** Se corrigen entre sí con **Holm (1979)** y se informan el p sin corregir y el p corregido.
- **Para cada cruce se informan:** la tabla de conteos, el porcentaje de favorables en cada grupo y la diferencia en puntos porcentuales.
- **Holm sobre D54:** con los 45 valores p de `marco_evidencia_v0.csv` se calcula el p ajustado de cada prueba y cuántas quedan por debajo de 0,05. Con esto se confirma, desde el pipeline, la frase del 4.5.

## 8. Reglas de lectura, fijadas de antemano

- **Se reporta lo que salga**, en los tres cruces, con sus dos valores p.
- **Si el p corregido es menor que 0,05:** se escribe «se observó una diferencia en la proporción de resultados favorables entre…». Nunca se presenta como efecto del nivel, del peso o del comparador.
- **Si no:** se escribe «no se observó una diferencia…». Nunca se escribe «no hay diferencia», porque con estos tamaños la prueba tiene poca potencia.
- **Peso y nivel no son independientes:** el componente C del peso (pertinencia) da más puntos a secundaria. Se dice al interpretar los resultados.
- **No se corre ninguna prueba que no esté aquí.** Si después aparece otra pregunta, se registra como decisión nueva y se marca como posterior a los resultados.
- **Nada de esto cambia los códigos, las tablas ni las cifras ya publicadas.**

## 9. Salidas

- `outputs/tablas/heterogeneidad_59.csv` y `.json`: conteos, porcentajes y valores p, con los hashes de las entradas. Solo números. Van a git.
- `outputs/tablas/holm_d54.csv`: criterio, dirección, p sin corregir y p de Holm. Solo números. Va a git.
- **Nada con texto de los artículos.** La revisión de los casos `varios` y `otra`, que sí lleva texto de `comparacion`, va a `outputs/semantico/` y queda fuera de git.

## 10. Código y pruebas (después de aprobar este protocolo)

- **Script:** `src/rs_pipeline/heterogeneidad_59.py`. Comando: `PYTHONPATH=src .venv/bin/python -m rs_pipeline.heterogeneidad_59`.
- **Pruebas:** `tests/test_heterogeneidad_59.py`. Verifican:
  - las reglas del comparador con textos inventados (incluidos `varios`, `ninguna` y las tildes);
  - Holm con un ejemplo hecho a mano;
  - Fisher sobre una tabla con cuentas a mano;
  - que la base sea solo de comparativos y que los grupos sumen la base;
  - las salidas reales contra la matriz y contra `marco_evidencia_v0.csv`;
  - que el p de Holm de C01 frente a mixto sea mayor que 0,05.
  - **No se modifica ninguna prueba existente.**
- **Quién corre qué:** Luis Fer corre las pruebas y el script en su Terminal y hace el commit (`Assisted-by: Claude Code`).
- **Documentación:** al cerrar, se agregan la entrada «Resultados de D59» en `decisiones.md` y la sección «Bloque 8.3» en `PROCEDIMIENTO.md`.

## 11. A la tesis (v5.0)

- **4.4:** dos o tres frases con los resultados de los tres cruces.
- **3.5.3:** media línea de método.
- **Lista PRISMA:** actualizar los ítems 13e, 20a y 20c.
