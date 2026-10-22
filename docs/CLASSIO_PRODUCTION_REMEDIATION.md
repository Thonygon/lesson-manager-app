# CLASSIO — Seguimiento de la remediación de producción

Estado a 2026-10-22. La matriz conserva los identificadores S01–S13 de la auditoría comercial. «Corregido en código» significa que existe una implementación y una prueba local; el estado de despliegue y validación se indica por separado. S07 está aplicado en Supabase de producción y publicado en Expo, pero aún requiere aceptación funcional y pruebas de concurrencia.

| ID | Estado de cierre | Avance y evidencia pendiente |
|---|---|---|
| S01 | Pendiente de staging | Borrado de cuenta movido a una RPC transaccional; fixture comprueba que un error no se confirma. Falta inyectar fallos de SQL con cuentas sintéticas y comprobar todas las tablas en staging. |
| S02 | Pendiente de staging | La RPC borra recursos privados o archivados y conserva los públicos activos; anonimiza la atribución. Falta matriz real por tipo/visibilidad/estado, incluidos `quick_exams`, y comprobar acceso público posterior. |
| S03 | Pendiente de staging | Cupo anónimo diario por IP del proxy y cookie, con hashes y limpieza a las 48 horas; fixture local cubre el borrado de cookie y el cambio de IP. Falta aplicar y probar RPC, Cron y límites de coste/abuso en staging. |
| S04 | Pendiente de staging | Reserva atómica antes de cada llamada externa, incluidos programas; reinicio mensual y fallback de 10 para planes sin cifra. Falta prueba concurrente real y conciliación de llamadas, contador y logs con 503. |
| S05 | Abierto | Intento de auditoría previo; acceso, roles internos, suspensión y reinicio de cupos ya usan RPC transaccionales con auditoría obligatoria. Siguen secuenciales la creación y actualización de cuentas con Supabase Auth y varias acciones de Explorer. Falta probar rollback en staging e idempotencia de invitaciones. |
| S06 | Diferido | Stripe no se activará ahora. Webhook firmado, eventos duplicados, reembolsos y conciliación son obligatorios antes de aceptar pagos. |
| S07 | Desplegado; cierre pendiente | Los cobros que el docente registra de sus estudiantes son apuntes de cobros externos, sin procesamiento de dinero por Classio. Altas, ediciones y borrados de cobros y clases, junto con el recálculo de paquetes, usan RPC transaccional e idempotencia por operación en Expo y Streamlit. Las claves y hashes de reintento se borran a los 90 días. Pasan fixtures Python, tipado, lint sin errores y verificación local de migraciones. La migración está aplicada en producción; pruebas sintéticas dentro de transacciones revertidas confirmaron reintentos, rollback por entrada inválida y rechazo de otro propietario. Expo responde tras el despliegue. Faltan aceptación funcional del titular, concurrencia real y comprobación de ejecución del cron; la edición masiva confirma cada fila por separado. Stripe, reservado para las suscripciones que pagan los docentes a Classio, queda diferido en S06. |
| S08 | Cerrado en código local | `generate+api.ts` rechaza perfiles suspendidos o eliminados antes del proveedor; fixture prueba acceso antes y después de la suspensión. La aceptación desplegada queda bajo S10. |
| S09 | Parcial en código local | Política definida por el titular: solo señales educativas y referencia numérica seudónima, sin nombre. Los prompts de planes, fichas y exámenes de Streamlit reducen el perfil a campos estructurados; fixture sintético comprueba ausencia de nombre, correo y UUID del perfil. Expo ya no agrega el nombre del estudiante al prompt y sus logs nuevos omiten tema y materia libres, registrando versión, proveedor y modelo cuando hay éxito. Migración programa borrar esos logs a los 90 días. Siguen pendientes campos libres, contextos de programas, trazabilidad de cada intento y todas las rutas Python; no se considera cerrado. |
| S10 | No verificado | Las 65 migraciones versionadas pasan la verificación local. Falta comparar esquema, RLS, Storage y secretos efectivos con cuentas sintéticas en staging. |
| S11 | Abierto | Cierre de prácticas sigue en varias escrituras; faltan transacción, reintentos seguros e inyección de fallos. |
| S12 | Abierto | Explorer aún requiere URL por entorno en móvil, aislamiento de fallos por categoría y paginación de exámenes. |
| S13 | Abierto | Faltan timeout uniforme, límites de salida y presupuesto para portadas y otras llamadas externas. |

## Política acordada para S09

- A proveedores externos se envían únicamente señales educativas estructuradas y una referencia numérica seudónima por estudiante. Nunca deben recibir el nombre, correo, UUID, notas personales ni el perfil completo.
- La trazabilidad técnica debe registrar versión de prompt, proveedor, modelo, hora y resultado, sin el texto completo. Se conserva **90 días** y después se elimina. Expo registra parte de esos metadatos por generación y una migración programa el borrado diario; faltan eventos por intento, cobertura de Python y verificación del Cron en staging.
- Los campos de texto libre y los contextos de programas todavía pueden contener datos identificables. Hay que cerrar esas rutas con fixtures sintéticos antes de declarar S09 resuelto y antes de habilitar su uso con datos reales en producción.
- Los registros de uso anteriores pueden contener `subject` y `topic` en `meta_json`. Hay que inventariarlos y definir una depuración segura en staging antes de aplicar cualquier limpieza a producción.

## Evidencia y criterios de cierre de S07

Decisión del titular (2026-10-22): no crear ahora un proyecto o rama que genere costes adicionales; autorizó aplicar la migración S07 en Supabase de producción y publicar Expo. Se aplicó `teacher_ledger_mutations_transaction.sql` (SHA-256 `062beec626f61a990b5470dead1ddc3e2ab7a42c039e9b760edad60c3421b952`) y se registró en `app_schema_migrations`. La verificación confirmó firmas y permisos de las RPC, un trabajo programado de limpieza, y ausencia de residuos del usuario sintético. Dos fixtures SQL dentro de transacciones terminadas en `ROLLBACK` confirmaron altas, borrados, edición, recálculo, repetición de clave, reversión ante una entrada inválida y rechazo de un propietario distinto. Se publicó Expo en `https://classio.expo.app/` y la ruta principal respondió HTTP 200. Estas pruebas no demuestran la ejecución futura del cron ni el comportamiento bajo concurrencia real.

La validación funcional con la cuenta del titular sigue pendiente. Los siguientes criterios son necesarios para declarar S07 cerrado; los que requieren staging quedan pospuestos hasta disponer de un entorno sin coste adicional aprobado.

1. Aplicar `teacher_ledger_mutations_transaction.sql` en una base de staging con el mismo esquema y RLS que producción. Verificar las firmas, permisos y el trabajo programado de limpieza de claves a 90 días.
2. Con dos docentes y estudiantes sintéticos, comprobar que uno no puede editar, borrar ni recalcular los apuntes del otro; el rol anónimo tampoco puede llamar a las RPC.
3. Dar de alta, editar, mover entre estudiantes y borrar clases y cobros manuales. En cada paso, comprobar que las fechas y saldos de paquetes de ambos estudiantes reflejan el resultado confirmado.
4. Repetir cada petición con la misma clave tras simular pérdida de respuesta: debe devolverse el resultado original sin duplicar el apunte. Reutilizar la clave con otro contenido debe fallar.
5. Inyectar un fallo en el recálculo y confirmar que el apunte, la posible alta del estudiante y la clave de idempotencia revierten juntos. Ejecutar operaciones concurrentes sobre el mismo estudiante y verificar que no quedan fechas obsoletas.
6. En la edición masiva, provocar un fallo a mitad del lote y comprobar que las filas ya confirmadas se muestran como guardadas al refrescar. Cada fila es atómica; el lote completo no lo es.

### Prueba funcional que puede hacer el titular tras el despliegue

1. Crear dos estudiantes de prueba con nombres ficticios, por ejemplo `S07-A` y `S07-B`, sin datos personales ni pagos reales.
2. Registrar para `S07-A` un paquete de dos clases y dos clases de una unidad. Comprobar que la fecha de vencimiento del paquete coincide con la segunda clase.
3. Editar la fecha o las unidades de una clase y comprobar que el vencimiento cambia. Mover esa clase a `S07-B` y verificar el historial de ambos estudiantes.
4. Editar el paquete, luego borrar una clase y el apunte de cobro ficticio. Refrescar la página tras cada paso y comprobar que las fechas quedan coherentes.
5. Si aparece un error, anotar la operación, la hora aproximada y el mensaje visible, sin enviar nombres ni datos reales de estudiantes. No repetir un cobro real para probar idempotencia.

## Puerta de aceptación inmediata

1. Aplicar las migraciones nuevas únicamente en staging y probar sus RPC con identidades sintéticas.
2. Inyectar errores en cada paso de borrado, cuotas, administración y cierre de prácticas; comprobar rollback, límites e idempotencia.
3. Verificar RLS, permisos de Storage y acceso cruzado de roles en staging antes de datos personales reales.
4. Mantener Stripe desactivado hasta que su flujo completo y conciliación pasen las pruebas.
