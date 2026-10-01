# Resource Affinity Unsupervised Discovery Technical Report

Business question: Can Classio discover semantic relationships between educational resources without manual labels, so teacher recommendations and pre-generation similar-resource warnings work from meaning rather than only tags?

Method:
- Canonical resource profiles were built from worksheets, exams, videos, lesson plans, and learning programs.
- Text profiles were vectorized with TF-IDF and reduced/normalized into dense semantic vectors when possible.
- K-Means, Agglomerative Clustering, and DBSCAN were compared as unsupervised models.
- Cosine similarity was used to produce nearest-neighbor affinity candidates.

Dataset summary:
- extraction timestamp: 2026-07-28T18:07:13.736173+00:00
- source rows inspected: 418
- included resources: 418
- excluded resources: 0
- exclusions by reason: {}
- resource types: {'program_topic': 348, 'video': 48, 'lesson_plan': 15, 'program': 7}
- subjects represented: 2
- completeness: {'resource_id': {'known_count': 418, 'missing_count': 0, 'known_pct': 1.0}, 'title': {'known_count': 418, 'missing_count': 0, 'known_pct': 1.0}, 'subject': {'known_count': 418, 'missing_count': 0, 'known_pct': 1.0}, 'language': {'known_count': 0, 'missing_count': 418, 'known_pct': 0.0}, 'level': {'known_count': 418, 'missing_count': 0, 'known_pct': 1.0}, 'learner_stage': {'known_count': 418, 'missing_count': 0, 'known_pct': 1.0}, 'topic': {'known_count': 411, 'missing_count': 7, 'known_pct': 0.9833}, 'lesson_plan_extracted_topics': {'known_count': 15, 'missing_count': 403, 'known_pct': 0.0359}, 'subtype': {'known_count': 363, 'missing_count': 55, 'known_pct': 0.8684}, 'profile_text': {'known_count': 418, 'missing_count': 0, 'known_pct': 1.0}}

Model comparison:
- best candidate: KMeans k=24 {"n_clusters": 24}
- Silhouette Score: 0.2051045845695746
- Calinski-Harabasz: 14.582379685179346
- Davies-Bouldin: 2.1351737063562464
- cluster count: 24
- cluster size <= 3 rate: 0.0
- cross-subject contamination: 0.125 (3/24)
- cross-language contamination: None (0/0)

Metric notes:
- Silhouette, Calinski-Harabasz, and Davies-Bouldin are calculated only on non-noise observations.
- Silhouette uses cosine distance.
- Contamination rates use normalized category values and ignore empty metadata values in denominators.

Production note:
This run is an offline unsupervised experiment. It does not deploy a model automatically. The semantic affinity outputs are suitable for review and shadow comparison before production use.
