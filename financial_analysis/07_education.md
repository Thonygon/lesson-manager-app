# 07 — Libro docente de referencia y posible actividad Education

**Fuente:** tablas privadas de los profesores `payments` y `classes`, consultadas el 22-10-2026; [education_anual.csv](education_anual.csv). La cuenta con 120 registros de pago y 1.948 filas de clases tiene rol admin y acceso docente. Hay un registro de pago y una fila de clase de otra cuenta que se excluyen de este perfil. Se requiere confirmar con el fundador que esta cuenta es suya. Este análisis de su posible actividad Education **no convierte los libros de otros profesores en ingresos de Classio**.

| Período | Pagos registrados | Importe registrado | Unidades vendidas |
| --- | ---: | ---: | ---: |
| 2023 | 51 | 286.762,69 TRY | 724 |
| 2024 | 24 | 411.400,00 TRY | 478 |
| 2025 | 25 | 603.400,00 TRY | 505 |
| 2026 hasta 19-10 | 20 | 472.300,00 TRY | 249 |
| Total | 120 | **1.773.862,69 TRY** | **1.956** |

Las cifras del panel redondean 2023 a 286.763 TRY y el total a 1.773.863 TRY; la diferencia es solo **0,31 TRY por redondeo**. Las clases registradas llegan al 21-10-2026: 1.948 filas, **2.014 unidades impartidas**. La diferencia global `impartidas − vendidas` es **58 unidades**. Hay además 3 unidades en `lesson_adjustment_units` en pagos; no se aplican automáticamente a la diferencia hasta entender su semántica. El conjunto de nombres distintos representados en pagos o clases es 41, frente a 30 filas actuales en `students`: son poblaciones y períodos diferentes.

`paid_amount` representa importes anotados por el docente para organizar sus clases; **no se verificó cobro bancario, factura formal, reembolso ni caja disponible**. Unidades vendidas e impartidas de distintos períodos no demuestran por sí solas deuda o servicio pendiente. Para conciliar por estudiante/paquete hay que revisar fechas de vigencia, ajustes, sesiones gratuitas, correcciones, borrados y traspasos históricos en un entorno privado, sin cambiar transacciones. La recurrencia y el ingreso por alumno/sesión no se publican hasta distinguir estos casos.

La capacidad mensual del fundador y los costes directos de Education no fueron aportados; por ello no se inventan proyecciones de 12 meses ni transferencia de caja a Technology. Los importes históricos no están íntegramente formalizados como facturación empresarial según la declaración del fundador. El contador y la abogada deben decidir su tratamiento en Türkiye sobre una conciliación documental privada, sin presumir aquí obligaciones fiscales concretas.
