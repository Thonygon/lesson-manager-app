# Reproducibilidad y evaluación ML

Esta guía separa los experimentos offline de la inferencia que utiliza Classio. Los resúmenes y modelos citados están versionados; los CSV con observaciones individuales no lo están. No copiar datos de estudiantes, predicciones por fila ni credenciales al repositorio o a un informe público.

## 1. Apertura supervisada de recomendaciones

Código: `streamlit/helpers/student_recommendation_open_7d_eval.py`, `streamlit/helpers/student_recommendation_open_7d_review.py` y `streamlit/scripts/run_student_recommendation_open_7d_pipeline.py`. Ejecución de referencia: `streamlit/reports/ml_architecture/student_recommendation_open_7d/runs/06762d2a88a4/`.

- **Fuente y objetivo:** exposiciones y eventos de apertura (`resource_exposures`, `resource_exposure_events`); etiqueta binaria `opened_within_7d_v1`, solo tras madurar la ventana de observación. El resumen declara 403 filas incluidas y 563 excluidas por ventana abierta; son cifras del artefacto histórico, no una medición nueva.
- **Variables:** metadatos de asignación y recurso, momento de exposición, contexto de recomendación y antecedentes calculados antes de la exposición. La lista exacta de 30 campos figura en `student_recommendation_open_7d_run_summary.json` bajo `evaluation.feature_names`.
- **Modelos y comparación:** `LogisticRegression` y `RandomForestClassifier` más baselines definidos en el evaluador. El informe identifica RandomForest como líder ROC AUC/precision-recall y LogisticRegression como mejor clasificador con umbral. Las métricas de apertura miden conducta de clic, no pertinencia pedagógica.
- **Partición:** temporal, con corte registrado en `evaluation.cutoff_timestamp`; desarrollo 322 y holdout 81 en la ejecución citada. El análisis de umbral es posterior y exploratorio. La distribución de clases y la escasez de positivos limitan la inferencia.
- **Artefactos necesarios:** dataset congelado `assigned_resource_open_7d_dataset_frozen.csv`, comparación de modelos, predicciones holdout, resumen, fingerprint y revisión de integridad. En Git están el resumen y los informes; los CSV por fila se conservan fuera del repositorio público. Los informes por sí solos permiten auditar lo declarado, pero no recalcular los resultados.

## 2. Afinidad no supervisada

Código: `streamlit/helpers/resource_affinity_unsupervised_eval.py` y `streamlit/scripts/run_resource_affinity_unsupervised_pipeline.py`. Ejecución ilustrativa: `streamlit/reports/ml_architecture/resource_affinity_unsupervised/runs/844999178a08/`.

- **Fuente:** perfiles de `worksheets`, `quick_exams`, `videos`, `lesson_plans`, `learning_programs` y `learning_program_topics`; extractos acotados solo cuando está disponible la vista autorizada. La ejecución citada registra 541 perfiles incluidos, de ellos 348 anclas curriculares y 193 recursos candidatos. La ausencia de extractos completos se registra en el resumen.
- **Objetivo:** agrupamiento de perfiles y similitud de ancla a recurso; no existe etiqueta supervisada de relevancia. TF-IDF de unigramas/bigramas, SVD cuando procede, normalización L2 y candidatos K-Means, aglomerativo y DBSCAN. Baseline práctico: reglas y metadatos del ranking, aún sin comparación controlada.
- **Métricas:** Silhouette con distancia coseno, Calinski-Harabasz, Davies-Bouldin, ruido, tamaños de cluster y contaminación de metadatos. La selección utiliza una fórmula heurística penalizada que consta en `resource_affinity_technical_report.md`. Ninguna mide aprendizaje o utilidad docente.
- **Partición y control:** no hay split supervisado; se congela un catálogo con fingerprint y configuración. La semilla declarada es 20260726. Los manifiestos, vectorizador/SVD/normalizador y vectores de `844999178a08` están versionados; el CSV congelado y algunas tablas de auditoría por fila no. Deserializar `.pkl` solo desde un artefacto aprobado y verificado, nunca desde archivos no confiables.

## 3. Ranking realmente utilizado

El ranking docente de Expo está en `expo/src/services/teacher-recommendations.ts`. `expo/src/app/(app)/students.tsx` solicita afinidad Python para hasta ocho candidatos preseleccionados por necesidad; añade esa señal al ranking local cuando la API está disponible. `python_api/app.py` valida token, registro y bundle de afinidad; `streamlit/helpers/resource_affinity_runtime.py` calcula la similitud. El ranking del estudiante está en `expo/src/services/student-recommendation-ranking.ts`, con reglas y modelo lineal local de `student-recommendation-ml.ts`. **El clasificador offline de apertura en siete días no interviene en ninguno de estos rankings.** El endpoint Python `/v1/student-recommendations/score` existe, pero no se encontró una llamada de producto a su wrapper.

## 4. Acceso y repetición autorizada

Un investigador autorizado debe obtener de la persona responsable del proyecto una copia privada del dataset congelado de la ejecución elegida, el manifiesto/fingerprint y la versión de esquema, o permisos de solo lectura a las tablas Supabase necesarias. Verificar fingerprint, ventana temporal y permisos antes de ejecutar. Usar un directorio privado fuera de Git para salida y mantener `SUPABASE_URL` y `SUPABASE_KEY` en el almacén de secretos aprobado. No usar claves en comandos compartidos ni subir CSV por fila. Ejecutar, desde `streamlit/` y con dependencias de `requirements.lock.txt` instaladas:

```bash
python scripts/run_student_recommendation_open_7d_pipeline.py --output-dir /ruta/privada/open_7d --run-id id_autorizado
python scripts/run_resource_affinity_unsupervised_pipeline.py --output-dir /ruta/privada/affinity --run-id id_autorizado
```

Estos comandos **reextraen datos de Supabase**; no son una reproducción exacta del catálogo histórico si la base cambió. Para comprobar la ejecución histórica se necesitan sus CSV congelados originales y las funciones de revisión sobre ellos. Nunca reemplazar una ejecución histórica con datos actuales conservando su identificador.

## 5. Protocolo de ablación pendiente

A = reglas/metadatos; B = A + afinidad no supervisada; C = sistema integrado, incorporando un modelo supervisado solo si se demuestra que influye en ese mismo ranking. Deben congelarse contexto, fecha, versión de código, candidatos y filtros obligatorios **antes** de puntuar. Cada configuración debe recibir idénticos candidatos elegibles y registrar versiones, Top 5 y faltantes. Dos evaluadores independientes, sin ver las puntuaciones ni la variante, deben juzgar la relevancia pedagógica con rúbrica fijada previamente y resolver desacuerdos. Calcular NDCG@5 solo con esos juicios; reportar cobertura, intervalos y casos excluidos. No convertir puntuaciones del modelo, aperturas o similitud en etiquetas de relevancia.

**Viabilidad actual:** el flujo Expo solo solicita afinidad para candidatos preseleccionados por A y la afinidad puede cambiar el filtro de cercanía y el conjunto final; el clasificador supervisado offline no está conectado al ranking. Por ello no existen tres variantes comparables A/B/C a partir de una captura normal del producto. El evaluador aislado `scripts/tfm_ablation.py` comprueba igualdad de candidatos y calcula Top 5; exige juicios independientes para NDCG. Su fixture sintético demuestra solo el código del evaluador, no rendimiento real.

Formato del evaluador: un JSON privado con `code_version`, `candidate_set_version`, `model_versions` y `contexts`. Cada contexto contiene `id`, `candidates` (objetos `{ "id": "...", "eligible": true|false }`) y `scores` con mapas `A`, `B` y `C` que cubren exactamente todos los identificadores elegibles. Si hay evaluación humana, añadir `judgment_source: "independent_human"` y `judgments` con una calificación entera de 0 a 3 para **cada** candidato elegible. Ese campo expresa la procedencia declarada por el investigador; el programa no puede verificar por sí solo la independencia del evaluador. Ejecutar `python scripts/tfm_ablation.py /ruta/privada/entrada.json --output /ruta/privada/salida.json`. La salida conserva versiones, Top 5 y NDCG@5 cuando procede; no muestra mejora porcentual ni acepta datos sin juicios como resultado empírico.
