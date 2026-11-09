# Evaluación de respuestas abiertas — plan de implementación beta

## Contrato pedagógico

1. Classio sigue corrigiendo automáticamente preguntas cerradas y respuestas libres que coinciden con la clave o con una variante explícitamente aceptada. Se normalizan formato, mayúsculas y acentos; una coincidencia de palabras sin equivalencia demostrada no publica una nota.
2. Una respuesta libre sin coincidencia se conserva íntegra. En un recurso asignado queda `pending_review`; en práctica independiente queda `unassessed`. Ninguno de esos estados significa «incorrecta».
3. El porcentaje final de un recurso asignado se publica solo cuando el docente decide sobre cada respuesta pendiente. La práctica independiente puede completarse sin docente ni IA; se muestran las partes corregidas y se invita a solicitar una revisión o buscar docente.
4. Una misión independiente puede darse por practicada aunque haya respuestas abiertas sin nota. Eso no equivale a dominio: las sesiones sin evaluación final no entrenan el ranking de recomendaciones con un porcentaje provisional.

## Cambios conectados

| Superficie | Regla |
| --- | --- |
| Generación | La clave es una respuesta modelo, no una única redacción válida. Preguntas objeto pueden ofrecer `accepted_answers` con variantes equivalentes. |
| Corrección Expo y Explorer | Coincidencia segura → automática; texto libre sin coincidencia → pendiente/sin evaluar. Preguntas cerradas conservan su corrección habitual. |
| Supabase | El intento y cada respuesta guardan estado de evaluación. La transacción de entrega crea una solicitud de revisión para el docente asignador. Los intentos pendientes aparecen como enviados, sin `graded_at` ni nota final en la tarea. |
| Docente | La cola existente muestra la respuesta modelo y exige una decisión explícita para cada respuesta pendiente. La revisión actualiza nota, tarea, intento y progreso en una transacción. |
| Estudiante | El resultado y el historial distinguen práctica completada, revisión pendiente y nota final. Una respuesta sin evaluar muestra una explicación sin X roja. |
| Recomendaciones y plan | El ranking excluye porcentajes provisionales; las misiones independientes permiten finalizar la práctica sin atribuir dominio. |
| Historial anterior | No se modifican sus respuestas ni puntuaciones. La recalificación automática omite intentos pendientes y evita reinterpretar notas antiguas con el nuevo criterio. |

## Despliegue y verificación

1. Aplicar `streamlit/migrations/practice_pending_review.sql` y después `streamlit/migrations/practice_pending_review_weighted_fix.sql`, registrando ambos checksums en `app_schema_migrations`; verificar las columnas y funciones antes de publicar Expo. La segunda migración conserva la ponderación por palabra de las sopas de letras durante la revisión y registra `completed_at` cuando se publica la nota.
2. Publicar Expo y comprobar typecheck, lint, export web y el fixture de respuestas equivalentes/negadas. No se activa ningún proveedor adicional de IA.
3. Beta en vivo: respuesta exacta; variante aceptada; «He is Alex» frente a «His name is Alex»; respuesta con negación; pregunta cerrada incorrecta; tarea con mezcla de preguntas; revisión docente completa; práctica independiente sin profesor; solicitud voluntaria de revisión; historial y misión; recalificación de clave antigua. Comprobar que ni notas parciales ni respuestas pendientes alimentan la precisión de recomendaciones.
4. Revertir la publicación de Expo si falla el flujo. La migración es aditiva para datos existentes; el rollback de las funciones debe prepararse con sus definiciones previas y requiere revisión de los intentos creados con estados nuevos. No borrar las columnas con datos de revisión.

**Estado al 09-11-2026:** implementación de código y pruebas locales dirigidas completas; ambas migraciones se ensayaron de forma reversible y se aplicaron en Supabase producción con checksums registrados. El ensayo de la función ponderada devolvió 2/3 para dos palabras halladas de tres. CI del PR #166 aprobó Expo, Streamlit y supply chain; se fusionó y se promovió Expo a producción. `app.masterclassio.com/sign-in` respondió HTTP 200. **Pendiente:** pruebas beta en vivo con cuentas reales, a cargo del titular.

**Seguimiento 10-11-2026:** una prueba beta con «Mi rutina semanal» reveló que la coincidencia exacta enviaba a revisión respuestas que solo omitían palabras ya presentes en la pregunta. El PR #168 se fusionó tras CI verde y Expo se publicó. La respuesta modelo aparece debajo del aviso de toda respuesta pendiente; los mensajes distinguen revisión automática de tareas asignadas y revisión opcional de práctica independiente, con o sin docente vinculado. La revisión del PR detectó dos riesgos y se preparó un refuerzo: el contexto adicional de una respuesta debe figurar en la pregunta y no puede calificar el modelo como falso/incorrecto; la recalificación histórica excluye la regla ampliada. Los intentos anteriores conservan su estado y nota. No se requiere otra migración SQL. **Pendiente:** publicar el refuerzo y documentar una prueba nueva con los casos de acierto, contradicción e historial.

**Revisión de recalificación 10-11-2026:** el PR #169 pasó CI, se fusionó y se publicó en Expo. Al recalificar una sesión final, conservar la decisión guardada de una respuesta abierta requiere que no hayan cambiado su texto, clave, tipo ni variantes aceptadas. De ese modo una corrección de otra pregunta puede aplicarse sin invalidar una respuesta previamente aprobada por el evaluador o el docente. El ensayo dirigido cubre dos respuestas abiertas aprobadas y una clave cerrada corregida. **Pendiente:** publicar este último ajuste y repetir el caso con cuentas beta reales.

**Identidad del contexto 10-11-2026:** el PR #170 se fusionó y se publicó. Un nuevo hallazgo de revisión amplió la identidad que debe mantenerse para conservar un veredicto final: enunciado, texto fuente e instrucciones tampoco pueden cambiar. Si cambian, la sesión histórica mantiene su instantánea y nota previas hasta una revisión explícita, en lugar de mostrar un enunciado nuevo con una nota antigua. El ensayo dirigido incluye un enunciado modificado. **Pendiente:** publicar este refuerzo y comprobarlo en beta con una edición real.

**Publicación final 10-11-2026:** PR #171 pasó CI, se fusionó y se promovió a Expo producción (`classio--5z9cd7zro2.expo.app`); `app.masterclassio.com/sign-in` respondió HTTP 200. Código y despliegue están cerrados. Queda a cargo del titular la verificación beta en vivo con un intento nuevo de «Mi rutina semanal», una contradicción, los tres contextos de revisión y una corrección de clave en una sesión mixta. No se necesita SQL nuevo.
