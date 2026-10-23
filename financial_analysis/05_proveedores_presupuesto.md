# 05 — Proveedores y presupuesto

**Criterio:** configuración/código no acredita plan contratado, factura ni gasto. No se encontró una fuente accesible de facturas para esta auditoría. Costes históricos, mensuales, anuales, umbrales y escalas 10/100/1.000 quedan **pendientes de factura/API de cuenta**; ninguna dependencia instalada se contabiliza como suscripción activa.

| Proveedor | Función y evidencia | Estado verificable | Tipo económico y dato faltante |
| --- | --- | --- | --- |
| Google Gemini | API key local; `streamlit/helpers/visual_support.py` y rutas Expo de generación e imágenes. | Configurado; uso facturado no confirmado por API de billing. | Variable por modelo/tokens/imágenes; faltan factura y métricas de llamada. |
| OpenRouter | API key local y cadena de fallback en `expo/src/server/ai-provider-chain.ts`. | Configurado. | Variable; modelo gratuito puede cambiar o fallar; faltan cargos/reportes. |
| OpenAI API | Ruta fallback en código; no se observó clave local para Expo. | Implementado, activación no verificada. | Variable, pendiente de facturas. |
| OpenAI Codex | Herramienta de desarrollo, fuera del flujo de clientes. | Gasto de desarrollo/mantenimiento no verificado. | No se asigna automáticamente por usuario SaaS. |
| Supabase | Base, Auth y Storage; tablas verificadas y buckets `avatars`/`branding` en código. | En operación. | Plan/coste fijo, base, egress y almacenamiento reales pendientes de panel de cuenta/facturas. |
| Expo/EAS Hosting | `expo/package.json` define despliegue web. | Despliegue configurado; plan/cargos no verificados. | Hosting, builds y transferencia pueden ser fijos/escalonados/variables. |
| Render | URL del servicio Python en `expo/src/services/python-models.ts`. | Dependencia desplegada indicada por código; factura no revisada. | Instancia y escala pendientes. |
| Stripe | `streamlit/services/payment_service.py` implementa Checkout/webhooks si hay secretos. `payment_events` tiene 0 filas y no hay clientes de proveedor vinculados. | Sin cobros SaaS verificados; proveedor definitivo pendiente. | Comisiones variables no aplicadas a márgenes. |
| GitHub | Repositorio y workflows. | Herramienta de desarrollo. | Plan/Actions/almacenamiento no verificados; separar de coste de servir clientes. |
| Google Calendar / correo / dominio / DNS / monitorización | Calendar OAuth en código; Auth vía Supabase; diagnósticos internos. | Integraciones parciales o no verificadas. | Facturas, plan y uso pendientes. |

La [lista oficial de países de Stripe](https://stripe.com/global) consultada el 22-10-2026 no incluye Türkiye para abrir una cuenta local de aceptación de pagos. Esto no decide por sí solo la estructura jurídica ni la alternativa de cobro: contador y abogada deben validar proveedor, entidad, facturación e impuestos. [Stripe explica los requisitos para abrir cuenta en otro país](https://support.stripe.com/questions/requirements-to-open-a-stripe-account-in-another-country?locale=en-GB).

Las páginas oficiales de [Gemini](https://ai.google.dev/gemini-api/docs/pricing), [Supabase](https://supabase.com/docs/guides/platform/billing-on-supabase) y [Expo](https://docs.expo.dev/billing/plans/) sirven para construir escenarios futuros. Son precios públicos actuales, **no tarifas históricas contratadas**. Para presupuesto 10/100/1.000 se necesitan facturas y uso por unidad; el coste de base, egress, imágenes y hosting podría cambiar por escalones de plan.
