# Experimento 3 - Descubrimiento no supervisado de afinidad entre recursos

## Planteamiento de la solución
Classio ya cuenta con recomendaciones basadas en reglas, metadatos y señales de uso. La limitación es que un recurso puede apoyar un tema del learning program aunque sus etiquetas, títulos o temas no coincidan exactamente. Para abordar este problema, se propone una capa de aprendizaje no supervisado que alinee recursos candidatos con temas curriculares del learning program.

El sistema no sustituye el ranker actual. Primero descubre candidatos semánticamente cercanos al tema del learning program y después las reglas de negocio de Classio filtran por profesor, estudiante, asignatura, idioma, nivel, programa de aprendizaje, estado de archivo y tipo de recurso.

Objetivos SMART:
- Específico: construir un modelo no supervisado que agrupe recursos de Classio y mida su alineación con temas del learning program.
- Medible: comparar K-Means, Agglomerative Clustering y DBSCAN con Silhouette Score, Calinski-Harabasz, Davies-Bouldin y tasa de contaminación entre asignaturas.
- Alcanzable: usar los recursos ya almacenados en Classio como dataset inicial.
- Realista: ejecutar el modelo en modo offline/experimental antes de impactar recomendaciones en producción.
- Acotado en el tiempo: producir un reporte reproducible de Experimento 3 para revisión antes de integrar el mejor modelo.

## Desarrollo del modelo
Dataset utilizado: 562 filas incluidas: 348 temas del learning program como anclas curriculares y 214 recursos candidatos.

Datos utilizados:
- worksheets: título, asignatura, tema, etapa, nivel/banda, tipo de worksheet, idioma, estado, visibilidad y fecha de creación. El experimento no trae worksheet_json completo.
- quick_exams: título, asignatura, tema, etapa, nivel, duración/tamaño, tipos de ejercicios, estado, visibilidad y fecha de creación. El experimento no trae exam_data completo.
- videos: título, asignatura, tema, descripción, etapa, nivel/banda, estado, visibilidad y timestamps.
- lesson_plans: título, asignatura, tema, etapa, nivel/banda, propósito, metadatos de planificación, idioma, estado, visibilidad, timestamps y plan_json.
- learning_programs: título, asignatura, etapa, nivel/banda, overview, estado, visibilidad, conteos de unidades/temas, orden, timestamps y program_data.
- learning_program_topics: unidad, número de tema, título, subtopic, lesson focus, propósito, objetivos, criterios de éxito, can-do statements, sugerencias de worksheet/exam, homework, notas docentes y resumen para estudiantes.
- resource_affinity_content_excerpts: vista opcional para extractos sanitizados y acotados de worksheets/exams. Si no existe, worksheets y exams entran por metadata-only y se registra warning.

Reglas de inclusión y exclusión:
- Se excluyen registros archivados antes de entrenar o comparar modelos.
- Se excluyen registros sin identificador estable.
- Se excluyen perfiles con menos de tres tokens.
- Se eliminan duplicados con la misma resource_key y el mismo profile_hash.
- Reglas registradas en la corrida: ['Archived rows are excluded before model development.', 'Rows without a stable resource id are excluded.', 'Rows with fewer than three profile tokens are excluded.', 'Duplicate rows with the same resource key and profile hash are excluded after the first occurrence.', 'The primary extractor does not select worksheet_json or exam_data. Content is included only through bounded sanitized excerpts when the lightweight excerpt view exists.', 'If the excerpt view is unavailable, worksheets and exams remain included through metadata-only profiles and the run records a warning.']

Cómo se desarrolló el modelo en Python:
- Lenguaje y librerías principales: Python; ['pandas', 'numpy', 'scikit-learn'].
- Se construyó un DataFrame congelado con perfiles canónicos de recursos.
- Cada fila se transformó en profile_text combinando rol, tipo, título, asignatura, idioma, nivel, etapa, tema, subtipo y contenido pedagógico disponible.
- El contenido de worksheets/exams solo se incorpora como content_excerpt sanitizado: sin imágenes, media, URLs, answer keys, correct answers ni soluciones.
- Los lesson plans aportan temas extraídos desde plan_json mediante claves asociadas a topic, title, objective, focus, vocabulary, success y assessment.
- Los program_topic heredan metadata del learning program padre cuando está disponible, para que el ancla curricular conserve materia, nivel y etapa.
- profile_text se vectorizó con TfidfVectorizer de scikit-learn usando unigramas y bigramas.
- Si la matriz tenía tamaño suficiente, se aplicó TruncatedSVD para reducir dimensionalidad.
- Se aplicó normalización L2 con Normalizer antes de calcular similaridad coseno y métricas de clustering.
- Se entrenaron configuraciones de KMeans, AgglomerativeClustering y DBSCAN.
- Cada configuración exitosa se evaluó con Silhouette, Calinski-Harabasz, Davies-Bouldin, ruido, tamaño de clústeres y contaminación entre materias/idiomas.
- El ganador se seleccionó con la fórmula balanceada documentada en este informe.
- La auditoría humana se construyó desde anclas program_topic hacia recursos candidatos, no desde pares tema-tema.
- Controles de reproducibilidad: ['Random seed is fixed at 20260726.', 'The run stores a dataset fingerprint built from profile hashes.', 'The run stores a configuration hash for the model grid and preprocessing settings.', 'The fitted representation is serialized so runtime scoring does not refit TF-IDF from live data.']

Cada fila se transformó en un perfil canónico de texto que combina rol, tipo, título, asignatura, idioma, nivel, etapa, tema, subtipo y contenido pedagógico disponible. Los lesson plans aportan temas extraídos desde plan_json cuando existen. Esos perfiles se vectorizaron con TF-IDF y, cuando el tamaño del dataset lo permite, se redujeron con Truncated SVD y se normalizaron para usar similaridad coseno.

Normalización de datos:
- Limpieza textual: todos los campos se convierten a texto, los espacios múltiples se reducen a un solo espacio y se eliminan espacios al inicio/final.
- Normalización Unicode: las categorías se normalizan con NFKC antes de compararlas.
- Materia, idioma, nivel, tipo de recurso y rol del recurso se auditan con valor original, valor normalizado y conteo.
- Las categorías se comparan con casefold, separadores como / y | se convierten a espacios y se aplican alias conocidos.
- Alias usados: {'subject': {'espanol': 'spanish', 'español': 'spanish', 'spanish language': 'spanish', 'english language': 'english', 'math': 'mathematics', 'maths': 'mathematics'}, 'language': {'english': 'en', 'eng': 'en', 'spanish': 'es', 'espanol': 'es', 'español': 'es', 'turkish': 'tr', 'turkce': 'tr', 'türkçe': 'tr'}}
- Los valores vacíos no se usan como denominador en contaminación de materia o idioma, para no castigar al modelo por metadata ausente.
- Vectorización: los perfiles se convierten con TF-IDF usando unigramas y bigramas; luego se aplica SVD si el tamaño lo permite y normalización L2 para similaridad coseno.
- Artefactos de auditoría: ['resource_affinity_category_normalization_audit.csv', 'resource_affinity_profile_audit.csv', 'resource_affinity_feature_audit.csv', 'resource_affinity_representation_manifest.json']

Modelos evaluados:
- K-Means
- Agglomerative Clustering
- DBSCAN

Indicadores clave:
- Mejor modelo: KMeans k=4 {"n_clusters": 4}
- Silhouette Score: 0.2391654221095159
- Calinski-Harabasz: 58.010133229183865
- Davies-Bouldin: 2.6805534511126643
- Número de clusters: 4
- Contaminación entre asignaturas: 0.25
- Selection score del ganador: 0.151665
- Resumen de alineación tema-recurso: {'top_k': 8, 'directed_edge_count': 2784, 'unique_undirected_pair_count': 2784, 'reciprocal_edge_count': 0, 'reciprocal_edge_rate': 0.0, 'mean_similarity': 0.429915, 'median_similarity': 0.414728, 'min_similarity': 0.148407, 'max_similarity': 0.921903, 'same_subject_rate': 0.9759, 'same_language_rate_known': 0.9759, 'same_level_rate_known': 0.3833, 'noise_source_edges': 0, 'noise_target_edges': 0, 'thresholds': {'0.6': 282, '0.7': 99, '0.72': 72, '0.8': 24, '0.9': 3}}

Fórmula de selección del ganador:
- selection_score = silhouette_score - 0.35 * cross_subject_contamination_rate - 0.20 * noise_ratio - 0.12 * cluster_size_2_rate - 0.08 * cluster_size_le_3_rate
- El Silhouette Score es la base positiva porque en esta fase no existen etiquetas humanas de relevancia.
- La contaminación entre asignaturas recibe la penalización más fuerte porque las reglas de recomendación de Classio dependen de respetar límites de materia.
- La proporción de ruido penaliza modelos que dejan muchos registros sin asignar, lo cual reduce utilidad para generar candidatos.
- Las penalizaciones por clústeres pequeños reducen el riesgo de elegir modelos que parecen coherentes solo porque fragmentan demasiado el catálogo.
- Orden de desempate: ['highest selection_score', 'highest silhouette_score as tie-breaker', 'lowest cross_subject_contamination_rate as tie-breaker']
- Por qué no basta Silhouette: The highest Silhouette model can over-reward small, isolated, or noisy clusters. The balanced score prefers a model that is coherent enough while still preserving coverage and useful cluster structure for downstream heuristics.

Por qué se considera ganador:
- Ganador por score balanceado: KMeans k=4 con selection score 0.151665.
- Líder métrico por Silhouette: KMeans k=5 con selection score 0.118059.
- Justificación: The winner is the top balanced selection-score candidate. The metric leader is reported separately because a higher Silhouette score alone can over-reward fragmented, noisy, or business-contaminated cluster structures.

## Conclusiones
El experimento generó un mapa de afinidad semántica para 562 filas y una muestra de revisión humana basada en anclas curriculares hacia recursos candidatos. La utilidad productiva debe valorarse revisando esas alineaciones y la coherencia de los clusters antes de activar el modelo en producción.

¿Tiene un índice de acierto aceptable? En aprendizaje no supervisado no existe una etiqueta de acierto directa. Por eso se usan métricas de coherencia de cluster, contaminación entre asignaturas/idiomas y revisión de vecinos semánticos como proxy de calidad.

¿Podríamos llevarlo a producción? No directamente desde esta fase. El siguiente paso recomendado es usar el mejor modelo en modo sombra para mejorar el pool de candidatos en recomendaciones de profesor y en las alertas de recursos similares antes de generación.

¿Necesitamos otros datos? Sí. Para validar mejor el modelo hacen falta más recursos, revisiones humanas de pares similares/no similares y eventos de uso posteriores que indiquen si los recursos semánticamente cercanos realmente son aceptados por profesores y estudiantes.
