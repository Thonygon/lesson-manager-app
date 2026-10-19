# Best next move: plan de producto y contrato

## Propósito

Best next move prioriza una acción docente concreta, explica por qué conviene hacerla y abre el lugar donde puede resolverse. Las notificaciones muestran eventos por tiempo; esta función escoge entre ellos y el trabajo pedagógico o administrativo pendiente. No inventa clases, urgencias ni riesgos. Si no hay clases ni pendientes verificables, el docente puede descansar.

## Reglas implementadas en Expo

| Prioridad | Señal | Acción | Retiro |
| --- | --- | --- | --- |
| 10 | Entrega con revisión solicitada | Abrir revisión | Solicitud atendida |
| 15–55 | Próximo tema de programa sin material claramente relacionado en biblioteca privada; clase dentro de siete días | Generar plan precargado; revisar similares | Aparece material, tema completado o clase cancelada |
| 20 | Estudiante pide más práctica | Abrir programa asignado | Petición atendida o retirada |
| 25–75 | Paquete sobreutilizado, agotado o por terminar | Revisar ficha del estudiante | Saldo corregido o estudiante inactivo |
| 35 | Clase programada en los últimos tres días sin registro | Comprobar y, si ocurrió, registrar la clase | Clase registrada o retirada del calendario |
| 48–68 | Existe plan relacionado pero no ficha ni examen; clase dentro de siete días | Generar ficha precargada | Aparece práctica o tema completado |
| 50 | Material relacionado con clase dentro de 48 horas | Abrir tema para preparar clase | Clase pasada o tema completado |
| 65 | Clase en las próximas 24 horas | Revisar calendario | Clase pasada o cancelada |
| 70 | Práctica relacionada sin tarea vinculada al tema | Abrir recomendaciones para asignar | Tarea asignada o clase pasada |
| 90 | No hay eventos próximos ni pendientes y queda un tema de programa | Ofrecer revisión opcional del tema | Cambia el estado |

El orden interno se resuelve por prioridad, plazo y luego identificador estable. La interfaz muestra **una sola acción** en la tarjeta original. Su identificador se conserva en el dispositivo: las demás esperan en la cola aunque cambie su prioridad. Cuando la acción visible deja de ser elegible tras resolverse o cambiar los datos, aparece la primera acción pendiente. No hay botón para saltar una acción sin resolverla. Los datos incompletos no justifican afirmar que la biblioteca carece de material.

## Afinidad, generación y límites

La primera versión cruza tema, asignatura, etapa y nivel con los recursos de la biblioteca privada. La frase «no encontramos material claramente relacionado» expresa incertidumbre de la coincidencia textual; no afirma que el material no exista en toda Classio. Smart Tools comprueba recursos similares otra vez antes de generar. El enlace lleva programa, tema y estudiante para fijar contexto curricular. Un plan y una ficha cubren necesidades distintas.

El motor de acciones es heurístico y explicable. El modelo Python de afinidad puede mejorar la selección de material cuando haya cobertura y umbrales validados; no debe decidir una ausencia de material a partir de una puntuación sin calibrar. Si Python no está disponible, el panel sigue funcionando. No se debería entrenar un clasificador de «mejor acción» hasta reunir resultados de varios docentes.

El motor no puede saber si una clase sin registro se impartió, ni si una clase próxima ya fue confirmada: los verbos son «comprobar» y «revisar». Un día sin clases no activa generación urgente. La biblioteca comunitaria se revisa en el flujo de reutilización, no para afirmar que hay recursos propios. La coincidencia textual puede fallar con sinónimos o traducciones.

## Evaluación durante las semanas de prueba

La siguiente fase debe registrar en servidor, con RLS por docente, cada exposición, apertura y resolución real: revisión realizada, práctica asignada, material creado, clase registrada o saldo corregido. Cada registro necesita versión de reglas, origen y hora de decisión, sin copiar contenido sensible. Medir elegibilidad correcta, sugerencias repetidas, tiempo hasta resolución, apertura que termina en una tarea resuelta y tiempo operativo ahorrado. Los clics por sí solos no prueban utilidad. La telemetría requiere diseño de tabla y permisos antes de desplegarse; la v1 no recoge esos eventos en servidor.

## Criterios de aceptación

1. Las revisiones abiertas se anteponen al trabajo opcional.
2. Un saldo negativo se calcula igual que el panel y desaparece tras corregirse.
3. La generación abre el programa y tema correctos y ofrece reutilizar similares.
4. Sin clase próxima no se inventa una preparación urgente.
5. La tarjeta conserva la misma acción mientras siga pendiente y muestra la siguiente al resolverse.
6. La copia está traducida al inglés, español y turco.
