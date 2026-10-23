# CLASSIO — Seguimiento de la remediación de producción

Estado a 2026-10-22. La matriz conserva los identificadores S01–S13 de la auditoría comercial. «Corregido en código» significa que existe una implementación y una prueba local; el estado de despliegue y validación se indica por separado. S07 está aplicado en Supabase de producción y publicado en Expo, pero aún requiere aceptación funcional y pruebas de concurrencia.

**Ubicación en las cuatro auditorías:** este es el registro de evidencia de los S-ID, no una quinta auditoría ni un plan paralelo. [Financiera](../financial_analysis/README.md) mantiene S06–S07; [tecnológica](CLASSIO_TECHNOLOGY_AUDIT.md) mantiene S01–S05, S08–S11 y S13; [paridad](../CLASSIO_EXPO_PARITY_CHECKLIST.md) mantiene S12. La [tabla de responsables y plan único](AUDITORIAS_ESTADO_2026-10-22.md) resuelve cruces. Una prueba o despliegue citado aquí no cambia por sí solo el estado a «aceptado».

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
| S09 | Parcial en código local | Política del titular: ID numérico seudónimo, etapa y lengua pueden usarse; nombres, direcciones y contactos no deben enviarse a IA. Se quitó el nombre que Recomendaciones añadía a las notas. Expo limpia identificadores directos reconocibles justo antes de llamar a OpenRouter/Gemini/OpenAI y al generador de portadas; muestra aviso breve sin clic adicional. Fixtures comprueban los patrones y el límite de la llamada. **No se puede garantizar detectar nombres/direcciones arbitrarios en texto libre**; el titular aceptó enviar el texto limpiado con aviso de este límite. Faltan despliegue y aceptación, inventario de Python/otras rutas, trazabilidad y retención efectiva. |
| S10 | No verificado | Las 65 migraciones versionadas pasan la verificación local. Falta comparar esquema, RLS, Storage y secretos efectivos con cuentas sintéticas en staging. |
| S11 | Parcial desplegado | Fichas y exámenes cierran sesión, respuestas, progreso e intento/asignación en `classio_complete_student_practice`; el borrador es la clave de reintento. La RPC pasó éxito, repetición y rollback SQL reversibles en producción. El registro de vídeos y el retoque de notas siguen con varias escrituras; falta aceptación beta. |
| S12 | Abierto | Explorer aún requiere URL por entorno en móvil, aislamiento de fallos por categoría y paginación de exámenes. |
| S13 | Corregido en código; pendiente prueba beta | Expo limita las llamadas de texto a 30 s y 512 KiB, las portadas a 45 s y 12 MiB, y el retoque a dos proveedores; generación ya limita dos intentos. Streamlit configura timeout y tope de tokens/respuesta en texto, timeout y tamaño de imagen, desactiva reintentos ocultos del SDK y hace una llamada por proveedor. Google Calendar tiene timeout de 15 s en ambos clientes. Faltan pruebas reales de 429/503, latencia y salida con la beta desplegada; el gasto por intento pertenece a la auditoría financiera. |

## Política acordada para S09

Decisión final del titular (22-10-2026): Classio puede compartir con IA el ID numérico seudónimo del alumno y señales pedagógicas como lengua materna y etapa; no debe compartir nombres, direcciones ni números de contacto. Tema, notas, instrucciones y recursos guardados también pueden entrar en el prompt: por eso se limpian justo antes de la llamada al proveedor. La eliminación automática cubre patrones reconocibles de correo, teléfono, dirección y campos etiquetados con nombre, pero **no puede identificar de forma fiable todo nombre o dirección en una frase libre**. El titular eligió enviar el texto limpiado con aviso de ese límite. La demo anónima conserva el mismo flujo rápido. Esta política sustituye las propuestas intermedias de confirmación por solicitud.

El límite se refiere a **datos enviados al proveedor externo de IA**. El nombre y los datos de contacto siguen disponibles en las vistas internas autorizadas para administrar alumnos, Best Next Move y notificaciones. Esos dos flujos de Expo calculan y muestran información mediante servicios de Classio y lecturas de Supabase; el código inspeccionado no llama desde ellos a un proveedor de IA. Si una acción abre una herramienta de generación, se aplica el límite del proveedor al prompt de esa herramienta.

- Expo no añade automáticamente el nombre del alumno seleccionado a las notas ni al prompt enviado al proveedor. La referencia numérica seudónima y los campos educativos estructurados siguen permitidos. La capa común de proveedores sanea el prompt de usuario antes de cada intento; la ruta de portadas usa el mismo limpiador. Las nuevas portadas ya no guardan `image_prompt`.
- La personalización docente conserva materia, tema, etapa, nivel, lengua materna, idioma del material, objetivos y opciones de la actividad. Cuando se llega desde un alumno seleccionado, su nombre se usa únicamente como pista interna para quitar variantes de ese nombre del prompt antes del proveedor; no se añade como instrucción pedagógica ni se guarda en el recurso generado. La comparación tolera tildes, mayúsculas, separadores, ciertos caracteres visualmente parecidos y un cambio de carácter en el nombre completo. No cubre nombres de otros alumnos no seleccionados.
- La UI muestra qué campos viajan a IA y advierte de la limitación de la limpieza sin exigir clic adicional. No se afirma que el texto libre sea infaliblemente anónimo: S09 permanece abierto hasta auditar las demás rutas, observar payloads sintéticos y resolver los nombres no reconocibles.
- La trazabilidad técnica debe registrar versión de prompt, proveedor, modelo, hora y resultado, sin el texto completo. Se conserva **90 días** y después se elimina. Expo registra parte de esos metadatos por generación y una migración programa el borrado diario; faltan eventos por intento, cobertura de Python y verificación del Cron en staging.
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

Esta puerta se aplica a los cambios pendientes. S07 ya se aplicó a producción por decisión documentada arriba; sus verificaciones restantes son aceptación y concurrencia, sin repetir la migración.

1. Aplicar las migraciones nuevas únicamente en staging y probar sus RPC con identidades sintéticas.
2. Inyectar errores en cada paso de borrado, cuotas, administración y cierre de prácticas; comprobar rollback, límites e idempotencia.
3. Verificar RLS, permisos de Storage y acceso cruzado de roles en staging antes de datos personales reales.
4. Mantener Stripe desactivado hasta que su flujo completo y conciliación pasen las pruebas.
