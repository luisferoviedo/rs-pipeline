# Reglas para agentes — rs-pipeline (Tesis 04)

## Forma de trabajo
- Primero propone un plan y espera aprobación. Implementa en pasos pequeños. Un commit por paso.
- Explica cada decisión no obvia en lenguaje sencillo. Luis Fer debe poder explicar cada línea.
- Implementa SOLO lo pedido. Nada de abstracciones, clases base o refactors no solicitados.
- Commits con trailer: `Assisted-by: Claude Code`.

## Datos
- La carpeta del Google Drive es SOLO LECTURA. Nunca escribir, mover ni borrar ahí sin aprobación explícita.
- Nunca subir a git textos completos, PDF ni data/raw/.
- Cada salida registra de qué archivo y versión viene (ruta + hash).

## Errores
- Prohibido `except:` / `except Exception: pass` y los valores por defecto que oculten fallas.
- Si falta una columna, un archivo o un ID, o un conteo no cuadra: el script FALLA con un mensaje claro.

## Dependencias y versiones
- PROHIBIDO agregar paquetes sin permiso. Si propones uno: nombre exacto, enlace a PyPI, versión y por qué hace falta.
- Versiones fijadas en requirements.txt. Python ≥3.10.
- Si no estás seguro de la API vigente (pandas, anthropic SDK, BERTopic), DETENTE y pregunta.

## Tests
- NO modifiques tests existentes para que pasen. Si un test parece incorrecto, DETENTE y explícalo.
- Los tests verifican números reales contra los CSV fuente, no "que no explote".

## API de Claude
- La llave solo en .env (en .gitignore). Nunca en código ni en logs.
- Cada llamada queda en logs/llm_calls.jsonl: modelo exacto, parámetros, hash de la entrada, respuesta cruda, tokens y fecha.
- Ninguna llamada a la API sin que Luis Fer apruebe el lote y el costo estimado.

## Calidad
- Ruff (reglas E, F, B, S, BLE, TRY, C901 con máx. 10) antes de cada commit. pip-audit cada vez que cambie requirements.txt y antes de cada push.
- gitleaks en pre-commit.
