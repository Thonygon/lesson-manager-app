# 02 — Consumo histórico de IA

**Serie observada:** `ai_usage_logs.created_at`, 17-03-2026 00:03:44 UTC a 19-10-2026 14:47:40 UTC. El detalle mensual reproducible está en [ai_mensual.csv](ai_mensual.csv). Cada valor cuenta **filas de evento**, no llamadas únicas, recursos entregados ni operaciones facturadas.

| Estado | Eventos |
| --- | ---: |
| Solicitado | 1.119 |
| Éxito | 911 |
| Fallo | 225 |
| Total | 2.255 |

Por funcionalidad, los eventos `success` son: worksheet 291, examen 47, plan 106, programa 13, etapa de programa 157, imagen/soporte visual 259, edición 17, informe experimental 19 y CV 2. **Los 157 éxitos de etapas de programa no son 157 programas vendidos o almacenados**: hay 10 filas de `learning_programs`. Imagen/soporte visual registra 263 solicitudes y 259 éxitos, sin número de imágenes por respuesta ni precio.

Los campos dedicados `provider`, `model_name` y `tokens_used` están vacíos en 2.255/2.255 filas. `meta_json.provider` aparece en 1.114, pero no establece el modelo, tokens ni cargo. No hay datos suficientes para coste medio, mediano, percentiles, coste por imagen, coste por sesión o conciliación mensual. La experiencia de «aproximadamente 400 TRY/mes de Gemini» permanece **observación del fundador sin factura cotejada**, no un tope de Classio ni un coste aplicado a otros usuarios. Las tarifas públicas actuales no se aplican a 2026 retrospectivamente.

El código distingue algunas operaciones de reutilización (`expo/src/server/generation-reuse.ts`) de nuevas generaciones, pero no hay telemetría histórica completa que permita medir ahorro por reutilización. Las llamadas a proveedores de `streamlit/helpers/visual_support.py` y `expo/src/app/api/lesson-plan-cover+api.ts` requieren correlación con factura y con el evento funcional. Las recomendaciones basadas en datos almacenados no se clasifican automáticamente como coste de IA.

**Para cerrar el coste:** reportes históricos por proyecto/modelo de Gemini y demás proveedores, facturas, uso de tokens de entrada/salida e imágenes por llamada, IDs de intento/reintento y tarifa vigente en cada fecha. No se infiere coste cero de los campos vacíos.
