# 06 — Modelo financiero de Classio Technology

**Precio de referencia:** Pro USD 19/mes, confirmado por `plans.price=1900` y la interfaz Expo. **Observado hoy:** 0 `payment_events`, 0 clientes de proveedor asociados y 0 suscripciones Pro pagadas entre 10 filas de `user_subscriptions`. El ingreso SaaS verificado en estas tablas es **0**, aunque no sustituye una revisión de banco o proveedor externo.

| Suscriptores hipotéticos pagando 12 meses | MRR bruto de lista | ARR de salida | Facturación bruta anual teórica a precio completo |
| ---: | ---: | ---: | ---: |
| 10 | USD 190 | USD 2.280 | USD 2.280 |
| 100 | USD 1.900 | USD 22.800 | USD 22.800 |
| 1.000 | USD 19.000 | USD 228.000 | USD 228.000 |

Esta tabla es **aritmética de precio**, no previsión ni ingreso neto. No incluye descuentos, impuestos, comisiones, impagos, costes de IA, soporte, salarios o marketing. Para crecimiento progresivo: `ingreso_del_año = Σ(mes=1..12) suscriptores_pagados_mes × precio_efectivo_mes`; MRR de salida usa solo el último mes y ARR es MRR de salida × 12. Churn y adquisición se aplican a la secuencia mensual, nunca a la cifra final como si hubiera pagado todo el año.

**Fórmulas a completar:** coste variable por usuario = Σ(operaciones facturables por tipo × coste histórico por operación) + egress/almacenamiento atribuible + comisión de cobro + otros variables. Margen de contribución = ingreso cobrado neto de devoluciones − costes variables. Resultado operativo antes de impuestos = margen de contribución − costes fijos operativos − soporte − comercialización − personal. Desarrollo e inversión se muestran aparte. Punto de equilibrio = costes fijos / margen de contribución unitario, solo si este margen es positivo y conocido. El tipo de cambio USD/TRY lleva fecha/fuente y no altera el importe original.

**Conclusión sobre USD 19:** indeterminada. No se debe afirmar margen positivo en uso ligero, intensivo o máximo sin tokens/imágenes, facturas, comisiones y cuotas semánticamente definidas. Imágenes y etapas de programas son riesgos probables por multiplicidad de llamadas, pero su contribución económica no está medida. Las cuotas que habría que ajustar se decidirán tras la conciliación de gasto y el escenario de estrés.
