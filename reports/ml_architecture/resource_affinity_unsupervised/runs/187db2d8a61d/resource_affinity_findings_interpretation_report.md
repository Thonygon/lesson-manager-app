# Experimento 3 - Descubrimiento no supervisado de afinidad entre recursos

## Planteamiento de la solución
Classio ya cuenta con recomendaciones basadas en reglas, metadatos y señales de uso. La limitación es que dos recursos pueden estar relacionados pedagógicamente aunque sus etiquetas, títulos o temas no coincidan exactamente. Para abordar este problema, se propone una capa de aprendizaje no supervisado que descubra afinidad semántica entre recursos educativos.

El sistema no sustituye el ranker actual. Primero descubre recursos semánticamente cercanos y después las reglas de negocio de Classio filtran por profesor, estudiante, asignatura, idioma, nivel, programa de aprendizaje, estado de archivo y tipo de recurso.

Objetivos SMART:
- Específico: construir un modelo no supervisado que agrupe recursos de Classio por similitud semántica educativa.
- Medible: comparar K-Means, Agglomerative Clustering y DBSCAN con Silhouette Score, Calinski-Harabasz, Davies-Bouldin y tasa de contaminación entre asignaturas.
- Alcanzable: usar los recursos ya almacenados en Classio como dataset inicial.
- Realista: ejecutar el modelo en modo offline/experimental antes de impactar recomendaciones en producción.
- Acotado en el tiempo: producir un reporte reproducible de Experimento 3 para revisión antes de integrar el mejor modelo.

## Desarrollo del modelo
Dataset utilizado: 418 recursos educativos extraídos de Classio a partir de worksheets, exams, videos, lesson plans y learning programs.
Cada recurso se transformó en un perfil canónico de texto que combina título, asignatura, idioma, nivel, etapa, tema, subtipo y contenido pedagógico disponible. Esos perfiles se vectorizaron con TF-IDF y, cuando el tamaño del dataset lo permite, se redujeron con Truncated SVD y se normalizaron para usar similaridad coseno.

Modelos evaluados:
- K-Means
- Agglomerative Clustering
- DBSCAN

Indicadores clave:
- Mejor modelo: KMeans k=24 {"n_clusters": 24}
- Silhouette Score: 0.2051045845695746
- Calinski-Harabasz: 14.582379685179346
- Davies-Bouldin: 2.1351737063562464
- Número de clusters: 24
- Contaminación entre asignaturas: 0.125

## Conclusiones
El experimento generó un mapa de afinidad semántica para 418 recursos. La utilidad productiva debe valorarse revisando los vecinos semánticos y la coherencia de los clusters antes de activar el modelo en producción.

¿Tiene un índice de acierto aceptable? En aprendizaje no supervisado no existe una etiqueta de acierto directa. Por eso se usan métricas de coherencia de cluster, contaminación entre asignaturas/idiomas y revisión de vecinos semánticos como proxy de calidad.

¿Podríamos llevarlo a producción? No directamente desde esta fase. El siguiente paso recomendado es usar el mejor modelo en modo sombra para mejorar el pool de candidatos en recomendaciones de profesor y en las alertas de recursos similares antes de generación.

¿Necesitamos otros datos? Sí. Para validar mejor el modelo hacen falta más recursos, revisiones humanas de pares similares/no similares y eventos de uso posteriores que indiquen si los recursos semánticamente cercanos realmente son aceptados por profesores y estudiantes.
