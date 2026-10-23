# Auditoría académica de Classio para el TFM

## Evidencia nueva de código — 23 de octubre de 2026

`classio_teacher_relevance_feedback` registra un juicio explícito por docente, alumno, contexto y recurso: `wrong_topic` es candidato a etiqueta negativa de afinidad temática; `student_unfit` evalúa adecuación al alumno y queda separado. El rechazo oculta el recurso y el ranking elige el siguiente candidato disponible; el deshacer conserva el historial. Para planes, fichas y exámenes de IA, `classio_generation_intent_feedback` captura Sí/No, razón opcional y origen de pantalla, ligado a la operación y al recurso mientras no exista edición sustantiva. `streamlit/scripts/evaluate_quality_feedback.py` resume esas señales y deja las celdas FN/TN de la matriz sin estimar porque solo observa recursos mostrados. Las asignaciones son positivos débiles, no juicios independientes. No se ha demostrado mejoría de relevancia ni se ha aprobado un reentrenamiento; primero hacen falta etiquetas beta, separación temporal y revisión de sesgos. El experimento de predicción de apertura permanece suspendido.

**Función en el registro único:** auditoría **académica** de afirmaciones OE1–OE3, experimentos y reproducibilidad. La seguridad y operación tienen una [auditoría tecnológica propia](CLASSIO_TECHNOLOGY_AUDIT.md); la equivalencia funcional tiene el [checklist de paridad](../CLASSIO_EXPO_PARITY_CHECKLIST.md). La evidencia técnica de este documento sustenta o limita afirmaciones del TFM, pero no crea una segunda cola de remediación de producción.

Fecha de revisión original: 21 de octubre de 2026. Alcance: código y artefactos versionados en este repositorio, más estado público de la ejecución de GitHub Actions [39434508082](https://github.com/Thonygon/lesson-manager-app/actions/runs/39434508082). Una prueba unitaria demuestra comportamiento acotado; no equivale a aceptación de usuarios ni a eficacia pedagógica.

## Actualización del código — 22 de octubre de 2026

Corte: `248ad2838`. La sección de CI inferior describe una ejecución **histórica** sobre `ef1713ec`; no es el estado de la rama actual. El workflow versionado instala con pnpm 11.19.0, comprueba TypeScript, lint y export web, y ejecuta pruebas de Streamlit, API Python y evaluador TFM. No se verificó una ejecución completa de Actions para este corte. En esta revisión, el verificador local de 65 migraciones, la comparación congelada del libro docente y el fixture de cuota de IA pasaron; `expo/scripts/check-manual-payment-transaction.cjs` falló porque todavía exige la RPC antigua `classio_add_manual_payment` en el código Python, que ahora llama `classio_mutate_teacher_ledger`. El fixture debe actualizarse antes de usarlo como puerta de CI; su fallo no demuestra un error de la nueva RPC.

| Área | Evidencia posterior a la revisión original | Límite vigente |
| --- | --- | --- |
| Integridad del libro docente | `expo/src/services/classio-data.ts` y `streamlit/core/database.py` invocan `classio_mutate_teacher_ledger`; `streamlit/migrations/teacher_ledger_mutations_transaction.sql` reúne mutación, recálculo de paquetes e idempotencia. [Seguimiento S07](CLASSIO_PRODUCTION_REMEDIATION.md) registra migración y publicación en producción. | Falta aceptación funcional con la cuenta del titular, concurrencia real y ejecución observada del cron. Una publicación no valida todos los flujos. |
| Generación y cuotas | `generate+api.ts` reserva uso antes de llamar al proveedor y `ai-generation-usage.ts` aplica el límite del plan; existen fixtures locales de autenticación y cuota. | El log final no conserva cada intento ni tokens/coste; la cuota no prueba gasto. La privacidad S09 y la validación de límites S04 siguen parcialmente abiertas. |
| Superficies y paridad | El checklist de Expo registra implementaciones de estudiante, docente y Admin y múltiples despliegues; el API Python expone puntuación de afinidad y recomendaciones. | La aceptación por rol y la paridad de experimentos/informes del Developer siguen abiertas. `student-recommendations/score` ajusta muestras enviadas por el cliente; no demuestra eficacia pedagógica ni un modelo desplegado sobre datos verificados. |
| Producción | [S01–S13](CLASSIO_PRODUCTION_REMEDIATION.md) distingue corrección local, despliegue y cierre. | S01–S05, S09–S13 mantienen validaciones o trabajo pendiente; S06 está diferido. No se infiere certificación de producción del build local. |

**Próximo cierre académico:** completar medición controlada OE1, juicios independientes y ablación OE2, y análisis de viabilidad OE3. El fixture desfasado, CI, S07 y RLS se siguen en las auditorías responsables. Las hipótesis OE1/OE2 conservan sus pruebas empíricas pendientes; el despliegue no las confirma. [Registro y orden de auditorías](AUDITORIAS_ESTADO_2026-10-22.md).

## Prioridades de la revisión académica original

| Prioridad | Hallazgo | Acción / límite |
| --- | --- | --- |
| P0 histórico | Expo fallaba al instalar dependencias con pnpm 11 (`ERR_PNPM_IGNORED_BUILDS` por el valor provisional de `core-js`) en la ejecución citada. | `expo/pnpm-workspace.yaml` fija `core-js: false`; instalación limpia local comprobada en esa revisión. Falta verificar Actions para el corte actual. |
| P0 | Las conclusiones experimentales podían confundirse con el ranking operativo. | Esta matriz separa experimentos, inferencia y evidencia humana pendiente. |
| P1 | Afinidad Python puede modificar el conjunto final de recursos; el modelo supervisado de apertura no es el modelo de ranking. | Protocolo offline en [reproducibilidad](TFM_ML_REPRODUCIBILITY.md); comparación empírica pendiente. |
| P1 | Los endpoints dependen de Supabase y de un artefacto aprobado externo. | Revisar con pruebas aisladas y aceptación con cuentas autorizadas antes de alegar integración completa. |
| P2 | No había una puerta de entrada académica. | [Guía del repositorio](TFM_REPOSITORY_GUIDE.md). |

## Matriz de trazabilidad

| Afirmación académica | Funcionalidad | Código fuente | Evidencia verificable | Limitación | Estado de validación |
| --- | --- | --- | --- | --- | --- |
| OE1: reducir ≥30 % el tiempo manteniendo calidad | Planes, hojas, exámenes y gestión de estudiantes | `streamlit/app_pages/`, `streamlit/helpers/`; `expo/src/app/(app)/` | Implementación y pruebas de unidad en `streamlit/tests/`; CI Streamlit pasó en ejecución 39434508082 | No hay medición controlada de tiempo ni equivalencia de calidad en este repositorio | Implementado; hipótesis OE1 pendiente |
| OE2: recomendaciones más pertinentes que reglas | Ranking de recursos para docente | `streamlit/helpers/recommendation_models.py`, `expo/src/services/teacher-recommendations.ts` | Funciones de puntuación y pruebas de recomendación en `streamlit/tests/` | La puntuación del propio sistema no es juicio independiente; filtros cambian con afinidad | Implementado; pertinencia no validada |
| OE2: personalización del estudiante | Ranking con reglas, señales de programa y ajuste lineal local | `streamlit/helpers/student_recommendations.py`, `streamlit/helpers/student_recommendation_ml.py`, `expo/src/services/student-recommendation-ranking.ts`, `expo/src/services/student-recommendation-ml.ts` | Pruebas `test_student_recommendation_ml.py` y `test_student_recommendation_scoping.py`; análisis estático | Paridad y aceptación transversal pendientes; no usa el clasificador offline de apertura a 7 días | Implementado con pruebas acotadas |
| OE2: predecir apertura en siete días | Experimento supervisado offline | `streamlit/helpers/student_recommendation_open_7d_eval.py`; `streamlit/scripts/run_student_recommendation_open_7d_pipeline.py` | Resumen de la ejecución `06762d2a88a4` y revisión de integridad versionados | Dataset congelado y predicciones por fila no están versionados; ventana corta y pocos positivos | Exploratorio; no desplegado en ranking |
| OE2: descubrir afinidad sin etiquetas | TF-IDF, SVD, agrupamiento y similitud coseno | `streamlit/helpers/resource_affinity_unsupervised_eval.py` | Resumen, manifiestos y representación de la ejecución `844999178a08` | No mide relevancia pedagógica; CSV congelado no está versionado | Experimento offline documentado |
| OE2: utilizar afinidad aprobada | Inferencia en Streamlit/Python y consumo Expo en recomendaciones docentes | `streamlit/helpers/resource_affinity_runtime.py`, `python_api/app.py`, `expo/src/app/(app)/students.tsx` | Verificación de manifiesto/hash y control de registro en Python; ruta de consumo en Expo | Requiere `CLASSIO_RESOURCE_AFFINITY_RUN_ID`, registro y bundle privado aprobados; sin prueba extremo a extremo en este trabajo | Implementado condicional; aceptación pendiente |
| OE3: arquitectura modular viable | Streamlit, Expo/React Native, API Python y Supabase | `app.py`, `expo/package.json`, `python_api/app.py`, `MIGRATION.md` | Código y flujo de CI | No hay análisis TCO ni validación de todos los flujos críticos | Arquitectura implementada parcialmente; OE3 pendiente |
| IA generativa para materiales | Generación de materiales en servicios Python y flujos Expo | `streamlit/helpers/`, `expo/src/services/privileged-workspaces.ts`, `python_api/app.py` | Código y pruebas de calidad seleccionadas | La calidad didáctica requiere evaluación humana; dependencias externas | Implementado; aceptación pedagógica pendiente |

## Dependencias y límites de confianza

- Streamlit es la aplicación Python existente; usa Supabase para datos y servicios externos para generación. No se modificó su aplicación de producción.
- Expo usa Supabase con credenciales públicas y RLS para operaciones permitidas. Llama a Python API con el token Supabase del usuario (`expo/src/services/python-models.ts`). No debe contener claves privilegiadas.
- Python API valida el bearer token con Supabase Auth; las consultas de recursos usan ese token y comprueban titularidad o visibilidad pública. La afinidad necesita además un identificador de ejecución fijado, registro aprobado y bundle privado con hashes. Si faltan, responde 503; Expo conserva el ranking local cuando falla la afinidad.
- `/v1/student-recommendations/score` ajusta un modelo lineal con muestras enviadas por el cliente. No consulta por sí mismo la titularidad de esas muestras y no aparece invocado fuera de su wrapper Expo. No se debe describir como modelo de producción ni como evidencia de efecto supervisado en el ranking.
- El cálculo de afinidad Python y el ranking Expo tienen escalas y funciones distintas. El primero entrega una señal; Expo la combina con reglas y un ajuste local. No hay prueba de equivalencia numérica integral entre ambas superficies.

## Clasificación de madurez

**Implementado con evidencia de código y pruebas acotadas:** gestión central en Streamlit, flujos seleccionados de Expo, ranking local y fronteras de autenticación. **Implementado y pendiente de aceptación:** integración Expo–Python, disponibilidad real del bundle, paridad de flujos y exportación web tras el arreglo de CI. **Experimental:** predicción de apertura a siete días y agrupamiento de afinidad. **Planificado/incompleto:** experimento OE1, juicios independientes de relevancia y NDCG@5 empírico, ablación A/B/C controlada, TCO y diseño arquitectónico formal de la segunda entrega.

## CI

La ejecución pública 39434508082 (SHA `ef1713ec`) informa `streamlit: success` y `expo: failure` en «Install locked dependencies»; los pasos typecheck, lint y export quedaron omitidos. La API pública de GitHub devuelve 403 al pedir el log, pero una instalación limpia local con los mismos pnpm 11.19.0 y lock reprodujo `ERR_PNPM_IGNORED_BUILDS: core-js@3.50.0`. Tras fijar `core-js: false`, la instalación limpia terminó correctamente. Esto no demuestra todavía que GitHub Actions haya pasado con el cambio.

Durante la preparación del despliegue posterior, TypeScript y la exportación web completaron. Se corrigió la configuración ESLint de los scripts Node y el acceso a un ref durante el render de `resources.tsx`; los efectos que sincronizan estado con parámetros, datos cargados o el retorno de OAuth tienen excepciones locales documentadas. ESLint terminó con cero errores y nueve advertencias. Esta verificación local no sustituye una ejecución nueva de GitHub Actions.
