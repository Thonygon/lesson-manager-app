# Calculadora de meta de ingresos de Classio

La calculadora del Explorer estima cuánto tiempo de docencia y cuántos estudiantes activos se necesitan para alcanzar una **meta anual de ingresos brutos por clases**. No estima beneficio neto ni garantiza ingresos.

## Cómo usarla

1. Selecciona asignatura, formación, moneda y una o más modalidades y edades de estudiantes.
2. Classio sugiere una tarifa por hora y un rango orientativo. Puedes sustituir la tarifa por la que realmente cobrarías.
3. Introduce una meta anual positiva en la moneda seleccionada y pulsa **Crear mi plan docente**.

Al cambiar la moneda, la calculadora convierte la meta y la tarifa que ya hayas escrito. La conversión usa factores fijos de planificación heredados de Streamlit; **no son cotizaciones en tiempo real**. Comprueba precios y tipos de cambio actuales antes de tomar decisiones comerciales.

## Cómo se obtiene la tarifa sugerida

Streamlit define un rango mínimo, central y máximo en USD para cada asignatura y modalidad. Cada valor se multiplica por el factor de edad (niños 0,75; adolescentes 0,85; adultos 1), el de formación (estudiante 0,70; grado 0,90; máster 1; doctorado 1,15) y el factor de la moneda. Si seleccionas varias modalidades o edades, Classio calcula cada combinación: la tarifa central es el **promedio con el mismo peso**, y el rango va del mínimo más bajo al máximo más alto. Es la extensión de la regla «ambas modalidades» de Streamlit. No supone que ya tengas esa distribución real de clases. Redondea los valores mostrados a unidades monetarias enteras.

La tarifa es una sugerencia de planificación, no un precio de mercado verificado. La tarifa efectiva del cálculo es la cifra editable que aparece en el campo.

## Fórmulas del plan

- **Horas de clase anuales** = techo(meta anual ÷ tarifa por hora).
- **Semanas docentes efectivas** = promedio de semanas de los grupos seleccionados, con el mismo peso: 44 para adultos y 36 para niños o adolescentes. La referencia de 44 semanas de Streamlit ya deja ocho semanas sin clases; el escenario infantil o adolescente descuenta ocho semanas adicionales por vacaciones de verano. Es un supuesto de planificación, no un calendario escolar universal.
- **Horas de clase semanales durante las semanas activas** = techo(meta anual ÷ (tarifa por hora × semanas docentes efectivas)).
- **Estudiantes activos estimados** = techo(horas semanales ÷ 1,5 clases por estudiante a la semana).

El techo redondea siempre hacia arriba. Classio clasifica la carga semanal como **cómoda** hasta 24 horas, **enfocada** de 25 a 31, **ambiciosa** de 32 a 42 y **excesiva** por encima de 42. El color de la tarjeta comunica esa clasificación; no representa una predicción de probabilidad.

**Ejemplo:** meta anual de 52.800 USD con una tarifa de 50 USD/hora, enseñando solo a adultos: 1.056 horas anuales, 24 horas semanales y 16 estudiantes activos estimados. Con la misma meta y tarifa, pero solo niños: 36 semanas efectivas, 30 horas semanales y 20 estudiantes estimados.

La estimación trata cada hora como una hora de clase facturable. No incluye preparación, administración, impuestos, comisiones, descuentos, impagos ni cancelaciones. Si impartes clases grupales, el número de estudiantes reales puede variar: este cálculo usa una carga media de clases por estudiante, no el tamaño del grupo. Ajusta la tarifa y la meta para explorar distintos escenarios.

## Referencia técnica

Las tablas de tarifas, multiplicadores, factores de moneda, 44 semanas y 1,5 clases proceden de `streamlit/helpers/goal_explorer.py`. Las 36 semanas para niños y adolescentes son una extensión de Expo para reflejar la reducción de verano solicitada. La implementación de Expo está en `expo/src/lib/income-planner.ts`; la interfaz está en `expo/src/app/index.tsx`.
