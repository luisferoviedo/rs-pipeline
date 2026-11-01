# Libro de códigos v1 (D45)

Codificación deductiva de cada informe frente a cada criterio del marco v0.

## Escala (por informe y criterio)

- **0** = No aparece, o la ficha dice explícitamente que no se reporta.
- **1** = Descrito: el laboratorio o la actividad lo tenía, pero el estudio no reporta su efecto.
- **2** = Con resultado: el estudio lo vincula a un resultado (mejoró algo, o su ausencia causó problemas).

## Reglas

- Codificar solo lo que dice la ficha; no completar con conocimiento propio.
- Ante duda entre dos códigos, el menor.
- Un informe recibe un código por criterio (C01 a C09), siempre los nueve.
- El código 2 exige un vínculo con un resultado dicho en la ficha; que el estudio tenga resultados en general no basta.
- Los criterios C01 y C09 siguen en borrador: se codifican igual y se marcan en la nota si el enunciado no alcanza para decidir.
- «2» exige que los autores atribuyan el resultado, aunque sea en parte, a ESE componente. Que la intervención en conjunto funcione no basta: un paquete cuenta como 1 para los componentes a los que no se atribuye el resultado.
- Un dato descriptivo de contexto o de barrera (p. ej., el porcentaje de estudiantes sin internet en casa) es 1. Solo es 2 si el estudio dice que influyó en la actividad o en el aprendizaje.
- «1» exige que la ficha mencione el componente. Si no lo menciona, o dice que no se documenta, es 0, aunque se pueda suponer que existía.

## Campos de la ficha que se leen (en este orden)

`tema`, `nivel_norm`, `disciplina_norm`, `diseno`, `comparacion`, `oe1_hallazgo`, `oe1_condiciones`, `oe1_direccion_norm`, `oe2_herramienta`, `oe2_andamiaje`, `oe2_retroalimentacion`, `oe2_interactividad`, `oe2_dispositivo`, `oe2_conectividad`, `oe2_idioma_accesibilidad`, `oe2_costo_licencia`, `oe2_usabilidad_calidad`, `oe4_secuencia`, `oe4_rol_docente`

No se leen `oe2_criterios_candidatos` (inferencias del extractor) ni `lf_*` (notas de Luis Fer). Se quitan las marcas [F]/[I] y las citas de página.

## Criterios

## Ejemplos de las reglas nuevas (inventados)

- Regla a. Ejemplo: «El grupo con simulación, guía y trabajo en parejas mejoró frente al control; los autores no atribuyen la mejora a ninguna parte» → retroalimentación, guía e interactividad = 1, no 2.
- Regla b. Ejemplo: «El 30 % de los estudiantes no tenía internet en casa» → 1; «quienes no tenían internet no pudieron terminar la práctica» → 2.
- Regla c. Ejemplo: «Costo y licencia: no se documenta» → 0, aunque la herramienta fuera gratuita en la práctica.


### C01 · Mediación docente y participación activa del estudiante

- **Dimensión:** Acompañamiento y mediación pedagógica del aprendizaje
- **Enunciado:** El laboratorio virtual debe integrar sus funcionalidades tecnológicas con decisiones didácticas explícitas sobre su uso, de modo que el estudiante participe en un proceso guiado, autónomo y reflexivo, y no sea un usuario pasivo que solo ejecuta la simulación.
- **Estado:** borrador: revisar Luis Fer

### C02 · Estructuración y secuenciación guiada de las experiencias de aprendizaje experimental.

- **Dimensión:** Estructuración didáctica y niveles de orientación de las actividades experimentales.
- **Enunciado:** El laboratorio virtual debe ofrecer experiencias experimentales organizadas mediante guías didácticas estructuradas, con objetivos de aprendizaje, fundamentación conceptual, procedimientos, preguntas orientadoras y actividades de análisis que conduzcan progresivamente al estudiante desde la exploración hasta la interpretación y comunicación de resultados.
- **Estado:** aprobado
- **Código 0.** Ejemplo: «Se usó el simulador en una clase; no reporta guía ni estructura de las actividades.»
- **Código 1.** Ejemplo: «Cada práctica tenía una guía con objetivo, pasos numerados y preguntas finales; no se analiza su efecto.»
- **Código 2.** Ejemplo: «El grupo con guía estructurada terminó más prácticas y mejoró en el postest; el grupo sin guía se perdió en la exploración.»

### C03 · Manipulación de variables y exploración experimental interactiva.

- **Dimensión:** Interactividad y manipulación experimental en entornos de simulación.
- **Enunciado:** El laboratorio virtual debe permitir que el estudiante manipule variables independientes, modifique las condiciones de los sistemas simulados, utilice instrumentos virtuales y observe los cambios producidos en los fenómenos estudiados, facilitando la exploración de relaciones entre variables, la formulación de predicciones y la comprensión de procesos científicos.
- **Estado:** aprobado

### C04 · Retroalimentación formativa y seguimiento del aprendizaje experimental.

- **Dimensión:** Retroalimentación y evaluación formativa en entornos de experimentación virtual.
- **Enunciado:** El laboratorio virtual debe favorecer procesos de retroalimentación continua mediante respuestas del sistema ante las acciones del estudiante, orientaciones del docente, espacios de discusión y mecanismos de autoevaluación que permitan reconocer avances, identificar errores y mejorar la comprensión de los fenómenos científicos.
- **Estado:** aprobado
- **Código 0.** Ejemplo: «Retroalimentación de la herramienta: no reporta.»
- **Código 1.** Ejemplo: «El docente comentaba las respuestas al cierre de la sesión; el estudio no evalúa ese comentario.»
- **Código 2.** Ejemplo: «Los estudiantes que recibieron corrección inmediata de la simulación corrigieron más errores en la segunda práctica.»

### C05 · Desarrollo de habilidades de medición, análisis e interpretación experimental.

- **Dimensión:** Desarrollo de habilidades científicas mediante la experimentación virtual.
- **Enunciado:** El laboratorio virtual debe proporcionar herramientas y escenarios que permitan al estudiante ejecutar procedimientos experimentales, utilizar instrumentos de medición, recolectar y procesar datos, representar resultados e interpretar fenómenos científicos para construir explicaciones sustentadas en evidencias.
- **Estado:** aprobado

### C06 · Mecanismos multimodales de retroalimentación y visualización del aprendizaje experimental.

- **Dimensión:** Mecanismos multimodales de retroalimentación y visualización del aprendizaje experimental.
- **Enunciado:** El laboratorio virtual debe proporcionar información oportuna sobre las acciones y resultados del estudiante mediante representaciones visuales, gráficas, respuestas automáticas y orientaciones de docentes o pares, facilitando la identificación de errores, la comprensión de los resultados y el mejoramiento progresivo del desempeño experimental.
- **Estado:** aprobado

### C07 · Usabilidad, eficiencia y fiabilidad del entorno tecnológico.

- **Dimensión:** Calidad técnica, usabilidad y condiciones de operación de los laboratorios virtuales.
- **Enunciado:** El laboratorio virtual debe garantizar una interacción sencilla, eficiente y confiable, considerando la facilidad de uso, los tiempos de respuesta, los requisitos técnicos, la compatibilidad con los dispositivos disponibles y su capacidad para mantener un funcionamiento adecuado ante diferentes condiciones de conectividad y demanda de usuarios.
- **Estado:** aprobado

### C08 · Verificación y contraste de resultados mediante representaciones experimentales.

- **Dimensión:** Contraste de resultados y validación del aprendizaje mediante la simulación.
- **Enunciado:** El laboratorio virtual debe permitir contrastar los resultados obtenidos por los estudiantes con representaciones, respuestas y soluciones de referencia, facilitando la verificación de procedimientos, la identificación de errores conceptuales y la autorregulación del aprendizaje mediante la interpretación de resultados y el diálogo pedagógico.
- **Estado:** aprobado

### C09 · Acceso en contextos de baja conectividad y recursos limitados

- **Dimensión:** Accesibilidad y viabilidad tecnológica del laboratorio virtual
- **Enunciado:** El laboratorio virtual debe poder usarse con los dispositivos, la conectividad, el idioma y los recursos económicos disponibles en las instituciones, sin depender de equipos costosos, licencias pagas ni conexión permanente.
- **Estado:** borrador: revisar Luis Fer
- **Código 0.** Ejemplo: «Idioma, costo y conectividad: no reporta.»
- **Código 1.** Ejemplo: «La simulación se descargó para usarla sin conexión en el aula; no se informa si cambió la participación.»
- **Código 2.** Ejemplo: «Cuatro estudiantes sin internet en casa no pudieron repetir la práctica y quedaron fuera del análisis.»
