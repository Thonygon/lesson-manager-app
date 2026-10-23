# 09 — Preparación de lanzamiento Pro

| Puerta | Evidencia actual | Criterio de aceptación pendiente |
| --- | --- | --- |
| Piloto privado | Generación y cuotas de IA en código; perfiles beta/lifetime en Supabase. | Ejecución autenticada de punta a punta, cobro desactivado o jurídicamente validado, registro de intentos/costes y revisión de privacidad. |
| Comercial limitado | Plan Pro y límites configurados; `payment_events=0`, sin clientes de proveedor. | Procesador apto para entidad en Türkiye, facturas de prueba y conciliación, soporte, límites de gasto/alertas y costes unitarios medidos. |
| Público | Paridad Streamlit–Expo todavía tiene verificaciones abiertas en `docs/parity/CLASSIO_EXPO_PARITY_CHECKLIST.md`. | Seguridad/RLS, protección de datos, cobro real, cancelación y devoluciones, observabilidad y carga verificadas. |
| Escalamiento | Supabase, EAS y Render presentes; capacidad y facturas no auditadas. | Pruebas de carga y costes a 10/100/1.000 usuarios con presupuesto de escalones y contingencia. |

No se asigna porcentaje global ni fecha garantizada: la ruta crítica depende de la decisión jurídica/comercial de pagos, facturas de proveedores y validaciones de producción. Un calendario en semanas sería especulativo sin el ritmo medido de cierres y disponibilidad de terceros. El primer hito verificable es la conciliación de costes e instrumentación; solo después puede fijarse una ventana condicionada para cada puerta.
