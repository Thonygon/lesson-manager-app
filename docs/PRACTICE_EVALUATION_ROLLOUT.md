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
