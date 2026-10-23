# Registro único de auditorías de Classio

**Corte de código:** 22-10-2026, `248ad2838` (`ver/42`). Hay **cuatro auditorías activas**. Los demás informes son evidencia, planes de producto o registros históricos; no mantienen una cola propia de hallazgos. El corte financiero de Supabase (22-10-2026, 11:38 UTC) no se ha repetido. Un hallazgo tiene una auditoría responsable, aunque otras necesiten su resultado.

| Auditoría activa | Documento que mantiene el estado | Decisión que permite tomar |
| --- | --- | --- |
| **Financiera** | [Auditoría y datos](../financial_analysis/README.md), con [brechas de registro](../financial_analysis/11_brechas_arquitectura_registro.md) | Qué se cobró, qué se gastó, qué margen puede demostrarse y qué pertenece al libro privado docente. Incluye la parte económica de la antigua remediación comercial. |
| **Tecnológica** | [Auditoría tecnológica](CLASSIO_TECHNOLOGY_AUDIT.md) | Si identidad, privacidad, transacciones, cuotas, RLS, rendimiento y despliegue soportan la operación. |
| **Paridad Expo–Streamlit** | [Checklist y aceptación](../CLASSIO_EXPO_PARITY_CHECKLIST.md) | Qué flujo de Expo reproduce el comportamiento de Streamlit y cuál requiere pruebas o servicio adicional. |
| **Académica** | [Auditoría TFM](TFM_TECHNICAL_AUDIT.md), con [reproducibilidad ML](TFM_ML_REPRODUCIBILITY.md) | Qué afirmaciones OE1–OE3 están medidas, cuáles son experimentales y cuáles son solo funcionalidad implementada. |

## Destino de los informes existentes

| Informe o plan | Función desde ahora | Responsable de los pendientes |
| --- | --- | --- |
| [S01–S13: remediación comercial/producción](CLASSIO_PRODUCTION_REMEDIATION.md) | Evidencia detallada y criterios de cierre por ID; su encabezado indica el responsable. | Según la tabla S-ID inferior. |
| [Upgrade de Negocio en Admin](ADMIN_BUSINESS_DATA_UPGRADE.md), [01–11 y agregados financieros](../financial_analysis/README.md) | Diseño de panel, fuentes, cifras con corte fijo y modelo de costes. | Financiera; no contar como auditoría adicional. |
| [Inspección de paridad de septiembre](../CLASSIO_PARITY_AUDIT_2026-09-22.md), [Admin/Developer](../CLASSIO_ADMIN_DEVELOPER_PARITY_AUDIT_2026-09-26.md), [generación/documentos/ML](../CLASSIO_GENERATIVE_DOCUMENT_ML_PARITY_AUDIT_2026-09-27.md), [alumno/Supabase](../CLASSIO_STUDENT_SUPABASE_PARITY_AUDIT_2026-10-11.md) | Fotografías fechadas, fixtures y antecedentes. Sus estados no sustituyen el resumen vigente del checklist. | Paridad; seguridad/carga encontrada allí pasa a tecnológica. |
| [Diseño y UX](../CLASSIO_EXPO_DESIGN_UX_INSPECTION.md), [contrato de migración](../MIGRATION.md), [calendario](../expo/CALENDAR_UPGRADE.md), [reglas de exámenes](../expo/EXAM_GENERATION_RULES.md) | Especificaciones y antecedentes, no auditorías activas. | Paridad para experiencia; tecnológica para límites de servidor. |
| [Auditoría de IO de Supabase](../streamlit/supabase_io_audit_report.md) | Medidas de forma de consulta y mejoras históricas; falta medición de carga actual. | Tecnológica. |
| [Guía TFM](TFM_REPOSITORY_GUIDE.md), [blueprint ML](../streamlit/docs/classio_ml_blueprint.md), [informes de experimentos](../streamlit/reports/ml_architecture/) | Método y resultados exploratorios fechados. | Académica; la operación de modelos en producción corresponde a tecnológica. |
| [Best next move](../BEST_NEXT_MOVE_DESIGN.md), [manual de calculadora](INCOME_CALCULATOR_USER_MANUAL.md) | Contratos de producto y uso. | Paridad para el flujo; académica para demostrar eficacia; financiera solo si se atribuye coste o ingreso. |

## Una responsable por S-ID

La numeración original se conserva para no perder trazabilidad. La [matriz de remediación](CLASSIO_PRODUCTION_REMEDIATION.md) guarda el detalle de cada prueba; esta tabla decide dónde se actualiza el estado principal.

| ID | Responsable | Resultado exigido y vínculo |
| --- | --- | --- |
| S01–S02 | Tecnológica | Borrado atómico, permisos y recursos públicos conservados. |
| S03–S04 | Tecnológica | Cupo anónimo y reserva concurrente verificables; financiera consume el recuento de intentos/coste. |
| S05 | Tecnológica | Admin, Auth, Explorer y auditoría con rollback y reintento seguro. |
| S06 | Financiera | Cobro SaaS, webhook, reembolsos y conciliación; diferido hasta seleccionar procesador. |
| S07 | Financiera | Integridad del libro privado docente, sin confundirlo con ingresos Classio; tecnológica verifica RPC/concurrencia y paridad comprueba ambos clientes. Desplegado, aún sin aceptación final. |
| S08–S11 | Tecnológica | Suspensión previa al proveedor, privacidad S09, esquema/RLS real y práctica transaccional. |
| S12 | Paridad | Explorer móvil, fallos por categoría y paginación de exámenes. |
| S13 | Tecnológica | Timeout, límites de salida y presupuesto de llamadas externas; financiera registra gasto. |

## Plan de acción único

| Orden | Entrega que cierra una decisión | Responsable | Dependencia y prueba de salida |
| --- | --- | --- | --- |
| 1 | Verificar S09/S10 en el entorno efectivo: privacidad de prompts, secretos, RLS y Storage. | Tecnológica | Roles sintéticos, pruebas de rechazo y matriz de configuración. Son límites de datos personales en servicios ya publicados. |
| 2 | Registrar operaciones e intentos de IA, imágenes y exportaciones con unidades, errores y cobertura visible; separar docente/SaaS. | Financiera | Operaciones e intentos de texto/imagen y solicitudes PDF/Word, más cobertura Admin, desplegados en esquema Supabase y Expo el 23-10-2026; falta beta. Vínculo transaccional con cuota/recurso, eventos de ciclo de vida, facturas y conciliación siguen abiertos. |
| 3 | Aceptar S07 y cerrar atomicidad/cuotas S01–S05, S08, S11 y S13. | Financiera para S07; tecnológica para los demás | Casos sintéticos, concurrencia, idempotencia, rollback y ejecución observada de cron; registrar por commit y entorno. |
| 4 | Comparar recorridos reales Expo–Streamlit y conectar el worker Python de experimentos/informes; resolver S12. | Paridad | Misma cuenta/fixture, resultado persistido, errores y documentos; la académica valida por separado pertinencia y utilidad. |
| 5 | Medir OE1–OE3 y conciliar presupuesto/ingresos antes de afirmar resultados o margen. | Académica para hipótesis; financiera para importes | Estudio controlado, juicios independientes y facturas/extractos; sin convertir pruebas de código en evidencia de eficacia o rentabilidad. |

**Regla de mantenimiento:** cada cambio actualiza la fila del auditor responsable con código, prueba, entorno, fecha, estado (`en código`, `desplegado`, `aceptado`) y riesgo restante. Los informes históricos se enlazan; no se reabren ni se copian sus listas como tareas vigentes.

## Actualización de código: feedback pedagógico, 23-10-2026

**Paridad:** Expo y Streamlit muestran selección y rechazo contextual de recursos docentes, motivos `wrong_topic` y `student_unfit`, sustitución al recalcular el ranking y deshacer. En ambos clientes, abrir el diálogo de asignación deja de generar una señal de asignación; Expo la registra tras confirmar la escritura. Planes, fichas y exámenes de IA sin cambios sustantivos muestran «¿Es lo que buscabas?» en generación y en el recurso, con origen `generation_preview` o `resource_page`. Las claves nuevas están en EN/ES/TR. Programa por unidades se excluye de esta pregunta hasta poder atribuir el documento completo a todas sus llamadas de IA.

**Tecnológica:** `classio_ai_quality_feedback.sql` crea vínculos generación–recurso, estado de edición y registros separados de respuesta y relevancia con RLS de servicio. La comparación de contenido no confunde enriquecimiento automático de imágenes con una edición pedagógica. El reporte `streamlit/scripts/evaluate_quality_feedback.py` lee señales etiquetadas sin reentrenar ni activar el experimento de predicción de apertura. La matriz observada de recursos mostrados solo puede medir verdaderos y falsos positivos entre etiquetas disponibles; falsos y verdaderos negativos permanecen desconocidos hasta diseñar un conjunto de candidatos no mostrados con juicio independiente.

**Estado de despliegue (23-10-2026):** las tres migraciones `classio_ai_economic_events.sql`, `classio_document_export_events.sql` y `classio_ai_quality_feedback.sql` se ejecutaron en Supabase producción y sus checksums quedaron en `app_schema_migrations`. Expo Hosting publicó `vge431y82l` en `https://classio.expo.app` con entorno `preview`; TypeScript, exportación web, fixtures de feedback, pruebas Python y verificador local de migraciones pasaron. Falta aceptación beta por el titular y volumen suficiente de etiquetas independientes antes de actualizar pesos o aprobar un modelo. Las señales `student_unfit` no se mezclan con la etiqueta de afinidad temática; los clics, aperturas y ediciones de imágenes tampoco se convierten automáticamente en fallos del clasificador.

## Correcciones de código y esquema: 23-10-2026

**Tecnológica:** se corrigió la reserva de cuota que impedía a Explorer anónimo llegar al proveedor y se conservaron, con limpieza acotada, temas fuertes/débiles, formatos y contexto de programa en la personalización del prompt. La pregunta de intención de Explorer anónimo se registra por operación en `classio_explorer_generation_feedback`, sin cuenta, prompt ni documento persistido, y el informe de calidad la separa de la respuesta autenticada. La migración `anonymous_explorer_generation_feedback.sql` se aplicó en Supabase producción y se registró en `app_schema_migrations`. La aceptación con generación real sigue a cargo del usuario beta.

**Paridad Expo–Streamlit:** el perfil filtra teléfonos a dígitos y un `+` inicial, el calendario busca alumnos por nombre, la facturación permanece oculta, los botones PDF/Word/Asignar se acortaron y los mensajes de operación pierden el fondo y se desvanecen tras cuatro segundos. Los controles de programa detectan similitud solo con materia, etapa, nivel, trayectoria y objetivo coincidentes. El detalle de recursos recupera de forma conservadora el vínculo de feedback de documentos de IA anteriores cuando existe una única operación próxima y ninguna señal de edición posterior. La verificación beta visual y funcional queda pendiente.

**Programas para alumnos sin cuenta:** `learning_program_roster_students.sql` permite asignar programas al ID estable de la libreta docente, calcular recomendaciones y registrar señales con esa identidad. Smart Tools ofrece también esos alumnos y personaliza con los temas próximos del programa, sin pedir notas de evaluaciones inexistentes. Un trigger enlaza las asignaciones existentes a la cuenta cuando se confirma el vínculo; el progreso por tema permanece en la misma asignación. `learning_program_roster_link_guard.sql` exige un vínculo activo antes de transferir. Ambas migraciones se aplicaron en Supabase producción y quedaron registradas con checksum. No se atribuye automáticamente al clasificador la idoneidad individual ni se inicia entrenamiento automático. Falta aceptación beta del recorrido asignar → avanzar → recomendar → vincular.

**Publicación del corte beta (23-10-2026):** código `606cb23f9` enviado a `origin/ver/42`; Expo Hosting desplegó `classio--42l6mq6qzd.expo.app` y lo promovió a `https://classio.expo.app` (HTTP 200). Las tres migraciones nuevas tienen confirmación de ejecución y checksum en `app_schema_migrations`. Pasaron TypeScript, lint sin errores (nueve avisos anteriores), exportación web, 71 checksums locales, fixtures de similitud/feedback/evidencia y siete pruebas Python. La aceptación funcional en vivo corresponde al usuario beta.
