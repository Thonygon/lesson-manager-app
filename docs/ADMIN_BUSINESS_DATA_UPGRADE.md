# Upgrade de Negocio en Admin: datos para decidir

**Señales de calidad añadidas en código (23-10-2026):** respuestas a generación y relevancia docente quedan en tablas separadas de `classio_ai_operations`, costes y libros de pago. Una futura vista Admin puede cruzar volumen, éxito técnico, coste y satisfacción por versión/modelo/superficie sin guardar prompts ni tratar un «No apto para este estudiante» como fallo temático. `streamlit/scripts/evaluate_quality_feedback.py` prepara el corte agregado; faltan etiquetas beta, aceptación y el diseño de umbrales antes de convertirlo en un indicador de calidad o presupuesto.

Estado: propuesta de producto e instrumentación basada en la inspección del repositorio del 22 de octubre de 2026. Las primeras capas de cobertura de IA y PDF/Word se aplicaron en Supabase y se publicaron en Expo el 23 de octubre; falta aceptación beta y conciliación. No valida las cifras del informe financiero.

Este es el diseño de implementación de la [auditoría financiera activa](../financial_analysis/README.md). Sus etapas son entregables de esa auditoría y no una cola independiente; el orden entre finanzas, tecnología, paridad y academia está en el [registro único](AUDITORIAS_ESTADO_2026-10-22.md).

## Propósito y límites

El informe de auditoría financiera plantea preguntas que el admin debería poder responder con evidencia reciente: cuánto ingresa cada línea, cuánto cuesta servir a un docente, qué uso impulsa el coste, si Pro conserva margen y qué parte del resultado es estimada. El panel debe mantener **Classio Technology** y **Classio Education** separados. `payments` es el libro privado de cada profesor para organizar clases y paquetes. Ningún registro de ese libro es un cobro de Classio por suscripción. Solo el libro del fundador, tras confirmar titularidad y conciliarlo, puede informar sobre su posible actividad Education; nunca se agregan los libros de otros docentes como ingresos de Classio.

Cada cifra visible debe incluir período exacto, moneda, fecha de actualización, origen y estado de evidencia: `observado`, `facturado`, `estimado`, `supuesto` o `no disponible`. Una cifra parcial o una muestra truncada no se presenta como total. Las conversiones de moneda se muestran aparte con fecha y fuente del tipo de cambio.

## Cobertura que permite afirmar el código hoy

| Área | Evidencia en el repositorio | Límite para el admin |
| --- | --- | --- |
| Panel Expo | `expo/src/components/admin-workspace-screen.tsx` muestra usuarios, suscripciones, eventos de pago, registros de IA, cobertura de intentos económicos y solicitudes PDF/Word con estados fallidos/abiertos. `expo/src/app/api/admin-workspace+api.ts` usa `count` exacto protegido y obtiene como máximo 500 perfiles/suscripciones recientes. | La cobertura indica lagunas, no dinero ni descargas completadas. Altas y mezcla de planes se calculan sobre filas recientes; no son una serie histórica completa si se alcanza el límite. El volumen de recursos almacenados no mide generaciones facturables. |
| Panel Streamlit | `streamlit/app_pages/admin.py`, `_render_business_analytics`, presenta altas, planes, estados y volumen de contenido. | Tampoco desglosa ingresos, costes ni márgenes. |
| Suscripciones y pagos SaaS | `user_subscriptions` aporta plan, estado, override e identificador de cliente. La consulta admin de `payment_events` solo pide identificador, proveedor, tipo, procesado y fecha. | Un evento procesado no demuestra cobro ni importe. El estado `active` o `trialing` no demuestra ingreso. No hay base verificada aquí para MRR, ARR, reembolsos o conciliación. |
| IA | La migración `classio_ai_economic_events.sql` y los adaptadores de Expo/Streamlit preparan operaciones e intentos separados, con uso del proveedor cuando está disponible. `usage_tracking` conserva los contadores de cuota. | La migración no está aceptada en beta; no hay coste facturado, tarifa histórica, vínculo transaccional con cuota/recurso ni cargo reconciliado. Un intento, un reintento, una generación completada y una reserva de cuota son unidades distintas. |
| PDF/Word | `classio_document_export_events.sql` y los adaptadores Expo/Streamlit preparan un evento por solicitud autenticada con formato, tipo y variante. Expo registra inicio y resultado; Streamlit registra clic de entrega. | `handoff_requested` no prueba guardado en el dispositivo; los visitantes anónimos no se atribuyen. Aún no hay cuota atómica común ni vínculo de recurso. |
| Libro docente | Hay registros privados de `payments` y clases de cada profesor en `streamlit/migrations/teacher_ledger_mutations_transaction.sql`; el archivo declara que estos recibos no son cargos de Classio. | No son ingresos de la plataforma ni de Education por defecto. La cuenta del fundador solo informa su actividad docente tras confirmar titularidad y conciliarla. Requieren acceso restringido por propietario. |
| Límites de planes | `expo/src/server/ai-generation-usage.ts` comprueba `ai_generations`; `expo/src/app/api/admin-actions+api.ts` acepta límites configurables de IA, PDF, Word, estudiantes y clases. | No se ha verificado aquí que cada cuota tenga una definición temporal y un evento de consumo consistente. |

Estas observaciones describen el **código**, no confirman tablas desplegadas, cobertura histórica, integridad de filas ni facturas de proveedores. La primera fase del informe financiero debe comprobar esos puntos mediante lectura acotada antes de fijar cifras o activar KPIs financieros.

## Contrato de métricas propuesto

| Pregunta de negocio | Métrica y unidad | Fuente mínima y condición de publicación |
| --- | --- | --- |
| ¿Cuánto vende Technology? | Cobros SaaS, devoluciones e ingreso reconocido por período, separados por moneda. MRR y ARR solo a partir de suscripciones pagadas y reconciliadas; ARR = 12 × MRR en una fecha, no facturación anual. | Transacción de proveedor con importe, moneda, estado, identificador estable, fecha y conciliación con factura o extracto. Los overrides y pruebas se excluyen del ingreso. |
| ¿Cuánto aporta Education? | Cobros propios del fundador confirmados, servicios prestados y pendientes, por mes y moneda. | Partir solo de su libro docente tras verificar titularidad y conciliarlo con recibos/banco; mostrar diferencias sin modificar el histórico. Otros profesores quedan excluidos. El Admin no debe mostrar como caja un importe meramente anotado. |
| ¿Cuánto cuesta la IA? | Solicitudes, llamadas facturables, éxitos, fallos, reintentos, tokens de entrada/salida e imágenes por funcionalidad, proveedor, modelo y mes. Coste estimado y factura en columnas distintas. | Evento por llamada con `operation_id`, `attempt_id`, tipo de recurso, proveedor/modelo, tokens o unidades de imagen, resultado y fecha; tabla versionada de tarifas y conciliación con facturas. No guardar prompts completos ni datos de estudiantes. |
| ¿Cómo se usa Pro? | Uso mensual por docente y percentiles de IA, PDF, Word, estudiantes y clases; porcentaje de cuota usada. | Definir primero qué constituye una generación, exportación, estudiante y clase; deduplicar eventos y excluir acciones de mera consulta/reutilización del consumo facturable. |
| ¿Se reutilizan recursos? | Recursos creados, editados, reutilizados, exportados y eliminados; generaciones evitadas como observación de flujo, no ahorro monetario automático. | Evento de ciclo de vida con ID de recurso seudónimo y acción; diferenciar lectura de una nueva llamada a proveedor. |
| ¿Qué margen deja Pro? | Ingreso cobrado menos coste variable atribuible, por cohorte y por mes; coste fijo y gasto de desarrollo en líneas aparte. | Publicar solo cuando ingreso y coste tengan cobertura conocida. Mostrar escenarios como `supuesto`, con precio, cuota, mezcla de uso y tipo de cambio editables. |

## Instrumentación y arquitectura

1. **Auditar cobertura antes de añadir gráficos.** Inventariar columnas reales, primeras y últimas fechas, volumen, nulos, duplicados y ausencia de eventos por funcionalidad. Consultar por períodos y agregados, sin exportar datos personales masivos. Registrar fuente, consulta, fecha y limitaciones de cada métrica.
2. **Normalizar eventos económicos.** Crear un identificador de operación compartido entre solicitud, intento de proveedor, generación, recurso y exportación. Conservar intentos separados para reconocer reintentos y posibles costes dobles. Añadir unidad y moneda a cualquier importe; los costes calculados llevan versión de tarifa. Los registros de factura se importan o consultan por un proceso controlado e idempotente, nunca se infieren de `payment_events` o `ai_usage_logs`.
3. **Preparar agregados seguros.** Servir series diarias/mensuales desde consultas agregadas del servidor, con filtros de fechas, línea de negocio y proveedor. Evitar traer cientos de miles de filas al cliente. Exponer totales, cobertura, lag y advertencias; conservar la autenticación y autorización admin de `admin-workspace+api.ts`. Aplicar mínimos de agregación para no revelar actividad individual de terceros.
4. **Construir el panel en capas.** Primero salud de datos y métricas observadas; luego ingresos/costes conciliados; finalmente simulador de Pro y alertas accionables. Cada tarjeta ofrece definición, fórmula y enlace interno a su desglose. Las alertas deben señalar umbral, período, evidencia y acción sugerida; no deben decidir precios ni alterar planes automáticamente.

## Prioridad de entrega

| Etapa | Entrega verificable | Dependencia |
| --- | --- | --- |
| 0. Cobertura | Matriz de fuentes reales, períodos, calidad, unidades y lag; panel con estado `no disponible` cuando falte evidencia. | Auditoría financiera de solo lectura. |
| 1. Telemetría | Eventos correlacionados para IA, imágenes, exportación y reutilización; definiciones de cuotas versionadas; pruebas de duplicación y fallos. | Esquema y retención aprobados; validación en entorno de prueba. |
| 2. Finanzas | Conciliación separada de cobros SaaS, costes de proveedores y libro docente del fundador; importes por moneda y reconciliación explícita. | Facturas/APIs y reglas contables confirmadas; tratamiento de su actividad docente en Türkiye pendiente de profesionales. Los libros de otros profesores no entran en el resultado de Classio. |
| 3. Decisión | Coste por generación, distribución de uso, margen por plan/cohorte, sensibilidad de precio/cuotas y alertas con trazabilidad. | Cobertura y calidad suficientes para cada métrica. |

## Criterios de aceptación del upgrade

- Ningún KPI financiero confunde cuentas activas, eventos de pago o recursos almacenados con dinero cobrado o llamadas facturadas.
- Cada tarjeta declara fuente, período, moneda, última actualización, fórmula y grado de evidencia; los datos incompletos son visibles como tales.
- Los totales históricos salen de agregaciones completas; los límites de paginación del panel de cuentas no sesgan las series de negocio.
- Technology y Education se pueden analizar por separado; los cobros de clases nunca alimentan MRR SaaS.
- El coste calculado se puede reconciliar con facturas sin sobrescribir la estimación original ni aplicar retrospectivamente una tarifa actual en silencio.
- Las vistas agregadas no exponen identidad de estudiantes, prompts, credenciales ni detalle financiero privado de otros docentes.
- Una comparación reproducible valida al menos un mes cerrado y un mes en curso contra consultas fuente, incluida la explicación de diferencias.

La implementación de este plan debe seguir los hallazgos de la auditoría de datos. No se han consultado ni modificado datos de producción para redactarlo.
