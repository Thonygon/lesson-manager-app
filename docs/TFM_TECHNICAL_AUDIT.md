# Auditoría técnica de Classio para el TFM

Fecha de revisión: 21 de octubre de 2026. Alcance: código y artefactos versionados en este repositorio, más estado público de la ejecución de GitHub Actions [39434508082](https://github.com/Thonygon/lesson-manager-app/actions/runs/39434508082). Una prueba unitaria demuestra comportamiento acotado; no equivale a aceptación de usuarios ni a eficacia pedagógica.

## Prioridades y estado

| Prioridad | Hallazgo | Acción / límite |
| --- | --- | --- |
| P0 | Expo fallaba al instalar dependencias con pnpm 11 (`ERR_PNPM_IGNORED_BUILDS` por el valor provisional de `core-js`). | `expo/pnpm-workspace.yaml` fija `core-js: false`; instalación limpia local comprobada. Falta una nueva ejecución real de Actions. |
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
