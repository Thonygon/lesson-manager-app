# 01 — Fuentes y calidad de datos

**Corte:** 22-10-2026, 11:38 UTC. Fuente de los recuentos: consultas exactas a Supabase; fechas: fila mínima/máxima por columna indicada. Las fechas del sondeo pueden quedar hasta minutos desfasadas respecto al recuento. No se verificó la integridad de facturas ni de backups.

| Fuente confirmada | Filas | Cobertura observada | Campos útiles y límite |
| --- | ---: | --- | --- |
| `profiles` | 31 | `created_at` 15-03 a 19-10-2026 | `user_id`, rol, plan, estado, alta. `login_count` no sustituye días activos. |
| `ai_usage_logs` | 2.255 | `created_at` 17-03 a 19-10-2026 | `user_id`, `feature_name`, `status`, `meta_json`, fecha. `provider`, `model_name` y `tokens_used` están vacíos en todas las filas leídas. |
| `usage_tracking` | 3 | `created_at` 04-06 a 26-07-2026 | Contadores actuales de IA/PDF/Word/estudiantes/clases y `monthly_reset_date`; no conserva series históricas. |
| `user_activity_log` | ≈25.155 | `created_at` 17-03 a 22-10-2026 | Actividad con tipo/acción y metadatos. Recuento **estimado**, sin lectura masiva. Semántica de sesión pendiente. |
| `worksheets` | 281 | 21-03 a 19-10-2026 | Recursos almacenados, con `source_type`, estado y fechas; no equivalen a llamadas facturadas. |
| `quick_exams` | 49 | 05-04 a 18-10-2026 | Recursos almacenados; sin vínculo económico directo. |
| `lesson_plans` | 72 | 16-03 a 19-10-2026 | Incluye proveedor/modelo en la fila del recurso, pero no tokens ni coste. |
| `learning_programs` | 10 | 12-04 a 31-08-2026 | Programas almacenados; una generación puede tener varias etapas de IA. |
| `payments` | 121 | `payment_date` 02-01-2023 a 19-10-2026 | Importes, moneda, unidades vendidas, ajuste y propietario. Es el libro privado de **cada profesor**; no cobro SaaS ni ingreso automático de Classio Education. |
| `classes` | 1.949 | `lesson_date` 02-01-2023 a 21-10-2026 | Unidades impartidas y propietario. No es prueba de facturación. |
| `students` | 30 | `created_at` 15-02 a 22-10-2026 | Registro actual; el número histórico de nombres representados en pagos/clases es distinto. No se exportó PII. |
| `user_subscriptions` | 10 | `created_at` 11-06 a 20-07-2026 | 2 beta/lifetime y 8 free, todos con override manual; ninguno vinculado a cliente de proveedor. |
| `payment_events` | 0 | Sin filas | La tabla existe, pero no acredita facturación SaaS. |
| `plans` | 4 | `created_at` 13-05-2026 | Pro: precio 1900 centavos de USD/mes en interfaz y límites 250 IA, 100 PDF, 100 Word, 75 estudiantes, 500 clases. |
| `resource_exposures` / `_events` | ≈50.670 / ≈1.717 | 23-05 a 22-10 / 15-10-2026 | Telemetría de recomendaciones; recuentos estimados, no coste de inferencia. |
| `application_diagnostic_events` | ≈27 | 09-08 a 01-10-2026 | Diagnósticos operativos, no facturas. |

**Relaciones verificadas:** `payments.user_id` y `classes.user_id` coinciden en una cuenta con perfil `admin`, `can_teach=true`, 120 pagos y 1.948 filas de clase. Es la cuenta docente que reproduce el panel; la identidad personal del fundador requiere confirmación del titular y no se publica. Otros propietarios suman una fila en cada tabla. Los 41 estudiantes históricos representados se obtienen de nombres distintos de pagos y clases, sin guardar nombres. Ningún libro privado de profesor alimenta las métricas de facturación de Classio.

**Fuentes de código:** `expo/src/server/ai-generation-usage.ts`, `expo/src/app/api/generate+api.ts`, `expo/src/app/api/lesson-plan-cover+api.ts`, `streamlit/services/ai_usage_service.py`, `streamlit/helpers/visual_support.py`, `streamlit/core/database.py`, `streamlit/services/payment_service.py`, `streamlit/database/migrations.sql`, `expo/src/app/api/admin-workspace+api.ts`. La generación de imágenes de Expo y las rutas Python no comparten aún un identificador de llamada y coste. Supabase Storage aparece en `avatars` y `branding`; su ocupación y transferencia reales no se consultaron. Expo/EAS y Render figuran en configuración de despliegue; no se obtuvo la facturación de esas cuentas.

**Calidad:** `meta_json.provider` está presente en 1.114/2.255 eventos y `provider_chain` en 646/2.255, pero ningún evento tiene modelo o tokens en los campos examinados. Los eventos `requested`, `success` y `failed` describen etapas; no constituyen llamadas facturables deduplicadas. Tampoco existe una clave uniforme para enlazar reintentos. La retención de registros (`streamlit/migrations/ai_prompt_trace_retention.sql`) puede limitar retrospectivamente la serie; su ejecución real no se verificó. No hay cobertura confirmada de facturas, costes de almacenamiento/egress, exportaciones históricas, caja bancaria ni devoluciones.

**Clasificación de evidencia:** las filas y sus agregados son datos confirmados en Supabase; rutas y esquemas son verificados en repositorio; las API de proveedores y tarifas contratadas siguen pendientes; ningún coste estimado se trató como pago real.
