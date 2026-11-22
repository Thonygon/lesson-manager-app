# Presentaciones orales en Classio — plan de implementación

## Decisión arquitectónica

La presentación oral será el quinto Smart Tool de Expo y un tipo de recurso propio. Su contenido pedagógico se guarda en `oral_presentations`; la tarea y sus intentos usan `teacher_assignments` y `teacher_assignment_attempts`. La grabación es un adjunto privado de un intento, no un recurso público ni una respuesta en JSON. La evaluación será exclusivamente humana. La versión Streamlit sigue como prototipo: compartirá la taxonomía y podrá leer recursos, pero Expo es la superficie de producción beta.

No se creará otro proveedor ni otra cuota de IA. La generación usará `/api/generate`, sus reservas económicas, aprobaciones, minimización de datos, validación y telemetría. El modo plantilla no consumirá cuota. Las notas orales evaluadas podrán sumarse al progreso académico; no se presentarán como dominio de preguntas de fichas/exámenes ni modificarán el clasificador de afinidad.

## Arquitectura existente aprovechable

- `smart-tools.ts` y `generate+api.ts`: generación autenticada, fallback, contabilidad y enlace de generación a recurso.
- `resource-library.ts`, `public-data.ts` y la página Recursos: propiedad, visibilidad, archivo y asignación.
- `teacher_assignments` y `teacher_assignment_attempts`: relación docente–estudiante, estado, historial y nota.
- `pg_cron` ya está habilitado para otros procesos. Las políticas de Storage usadas por Ayuda dan un patrón de acceso privado.
- `_SUBJECT_FAMILY_KEYWORDS` y `_NON_CLASSIO_ACTIVITY_BANK` de Streamlit orientan la selección pedagógica. Una taxonomía JSON nueva será la fuente común de identificadores y familias para Expo y Python.

## Brechas y cambios de datos

1. Las restricciones `assignment_type` y `source_type` no incluyen presentaciones orales. Se amplían sin alterar filas existentes.
2. `oral_presentations`: dueño, título, materia/familia/tema, etapa/nivel, idiomas, tipo de ejercicio, objetivo, duración máxima, documento JSON, estado, visibilidad y vínculo de operación de IA. RLS conserva la regla dueño o recurso público; no contiene datos de alumnos.
3. `classio_oral_recordings`: una fila por intento con ruta de Storage generada por el servidor, MIME, tamaño, duración, fechas de envío y expiración, estado de eliminación e intentos de limpieza. Referencia a `teacher_assignment_attempts` sin duplicar nota ni feedback.
4. Bucket privado `classio-oral-audio`; acceso de lectura solamente para el estudiante autor y el docente de la tarea, mientras no haya expirado. La subida requiere ticket/intent autorizado; la ruta se construye en el servidor. No se almacenará audio en base64.
5. RPC atómicas para iniciar la subida, confirmar el envío y publicar evaluación. Se comprueban relación, dueño, tamaño, MIME, duración y estado de la tarea; la evaluación recalcula la nota desde la rúbrica y conserva cada intento.

## Flujos

**Generación:** docente elige materia, familia derivada, tema, etapa, nivel, ejercicio compatible, objetivo, duración, instrucciones e idiomas. El servidor valida tipo y forma de la respuesta y normaliza rúbrica editable. Una plantilla determinista cubre tipos sin estímulo complejo; lectura, problemas y escenarios específicos requieren IA o texto docente. Vista previa → edición → guardar → asignar.

**Estudiante:** abre la tarea, lee estímulo, acepta permiso de micrófono, graba/escucha/repite o carga un archivo admitido. Antes de marcar la tarea como enviada, el cliente sube a Storage privado y el RPC verifica que el objeto corresponde al intento. Una repetición de solicitud devuelve el intento existente, sin duplicar entregas. En web se usa `MediaRecorder`; en nativo, `expo-audio` con la configuración de permisos del proyecto. El audio no se somete a IA.

**Docente:** ve cola de entregas, escucha por URL firmada de corta duración, aplica la rúbrica, escribe feedback y publica. La nota sale de `sum(score)/sum(max_score)`, validada en SQL. Para repetir, se abre un nuevo intento; el anterior permanece en el historial. El estudiante ve fecha, estado, nota, desglose y comentario.

## Privacidad y seguridad

- Grabaciones privadas y separadas de los recursos públicos; ni catálogo ni exportación pública incluyen rutas de audio.
- Los avisos para alumnado y docentes deben describir finalidad, acceso y plazo de 30 días antes de activar la función. Para menores, el flujo de autorización existente debe revisarse con asesoría jurídica antes de la beta.
- Sin transcripción, reconocimiento de voz, biometría, clasificación ni entrenamiento con audio.
- El cliente comprueba la firma inicial del archivo, el MIME declarado, la duración y el tamaño. La confirmación SQL vuelve a comprobar MIME, tamaño y duración contra el objeto privado de Storage; PostgreSQL no inspecciona los bytes del objeto. Una verificación independiente del archivo en el servidor sigue siendo una mejora pendiente si se aceptan archivos de fuentes no confiables más allá del cliente oficial.
- Audio expira 30 días después del envío. Una tarea diaria de GitHub Actions llama a un trabajador con credencial de servidor que elimina los objetos vía API de Storage y registra éxito/fallo con reintentos. La tarea requiere configurar `SUPABASE_URL` y `SUPABASE_SERVICE_ROLE_KEY` como secretos del repositorio. El acceso se corta por fecha aunque la eliminación física falle. Se conservan nota, rúbrica y feedback. El borrado de cuenta o tarea crea una orden de eliminación de objeto antes de la cascada de metadatos.
- Antes de desplegar, comprobar el acceso cruzado con dos alumnos y dos docentes, incluidos vínculos revocados, archivos vencidos y perfiles suspendidos.

## Migración y compatibilidad

La migración será aditiva y transaccional, sin tocar clases, pagos administrativos ni perfiles. El nuevo tipo se añadirá a las restricciones, sin cambiar el significado de estados existentes. Las consultas antiguas seguirán funcionando y podrán ignorar el tipo nuevo. No se marcará la migración como aplicada hasta verificarla en Supabase. Se hará rollout con generación/recurso primero, después grabación/revisión y finalmente retención, antes de habilitarla a alumnos reales.

## Verificación

- Pruebas unitarias: taxonomía por familia, filtrado por etapa, plantillas, validador de documento/rúbrica, límites de archivo y deduplicación.
- Pruebas de integración: creación/edición/archivo/asignación, carga y confirmación de audio, revisión y nota, reintentos, progreso, políticas RLS, expiración y limpieza fallida.
- `pnpm typecheck`, lint y checks de Expo; pruebas Streamlit que consuman la taxonomía; comprobación de claves EN/ES/TR.
- Prueba beta del usuario: móvil y web, micrófono denegado, carga alternativa, docente escucha/evalúa, alumno ve resultado, archivo a punto de vencer.

## Lista de implementación

- [x] Taxonomía versionada en JSON, validación de generación y plantillas permitidas en Expo. Streamlit queda como prototipo y no ofrece este quinto generador.
- [x] Recurso oral, quinto Smart Tool y edición desde la biblioteca en código.
- [x] Migración aditiva aplicada y verificada para recurso, asignación, intentos, audio privado y RLS. El titular aplicó también la migración posterior de favoritos públicos y metadatos; Supabase devolvió éxito. **Pendiente de prueba beta de ambos flujos**.
- [x] Grabación web y nativa, carga de archivo web, subida privada y confirmación atómica en código. **Pendiente de prueba real de micrófono, Storage y permisos**.
- [x] Un reintento de envío recibe un ticket y una ruta nuevos; el audio abandonado entra en la cola de borrado y el envío exige un intento activo. El titular aplicó `oral_upload_retry_isolation.sql` y Supabase devolvió «Success. No rows returned». **Pendiente de prueba beta del reintento**.
- [x] Revisión humana, rúbrica, feedback e historial en código. Aviso en la tarea y notificación directa al docente desde cinco días antes del vencimiento si el intento sigue sin evaluar; la notificación desaparece al publicar la evaluación. **Pendiente de prueba con docente y estudiante reales**.
- [x] Nota de tarea y notificaciones directas para envío y revisión en código. **Pendiente de comprobar la lectura de progreso en beta**.
- [x] Trabajador de limpieza, cola de cascadas y tarea diaria en código. Se configuraron `SUPABASE_URL` y `SUPABASE_SERVICE_ROLE_KEY` como secretos cifrados de GitHub Actions. **Pendiente de comprobar la ejecución real y el reintento**.
- [x] Traducciones EN/ES/TR, avisos, términos, guía de ayuda y migración de versiones legales preparados. El SQL legal está aplicado y Sites publicó la versión 27. **Pendiente de comprobar enlaces y aceptación en vivo**.

**Estado:** implementación de Expo en PR #190; publicación de Expo pendiente. TypeScript, lint, exportación web, comprobación de taxonomía/plantilla/validador oral y pruebas de fuentes legales pasaron localmente; CI Tests #504 pasó tras el ajuste de reintentos. El titular aplicó los cuatro SQL; una consulta de solo lectura confirmó tablas orales, publicaciones activas y bucket privado, y los dos últimos SQL devolvieron éxito en el editor. Sites publicó el aviso legal en versión 27. Los secretos de retención están configurados en GitHub, pero hay que ejecutar y verificar la tarea, y después realizar las pruebas de acceso, retención, eliminación y experiencia con cuentas reales. La evaluación jurídica de autorizaciones para menores sigue pendiente de la revisión del responsable.
