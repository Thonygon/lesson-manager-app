# Resource Affinity Unsupervised Discovery Technical Report

Business question: Can Classio discover semantic relationships between educational resources without manual labels, so teacher recommendations and pre-generation similar-resource warnings work from meaning rather than only tags?

Method:
- Canonical resource profiles were built from worksheets, exams, videos, lesson plans, and learning programs.
- Text profiles were vectorized with TF-IDF and reduced/normalized into dense semantic vectors when possible.
- K-Means, Agglomerative Clustering, and DBSCAN were compared as unsupervised models.
- Cosine similarity was used to produce nearest-neighbor affinity candidates.

Dataset summary:
- extraction timestamp: 2026-07-25T21:14:22.005972+00:00
- source rows inspected: 181
- included resources: 180
- resource types: {'worksheet': 84, 'video': 44, 'exam': 31, 'lesson_plan': 14, 'program': 7}
- subjects represented: 4

Model comparison:
- best candidate: DBSCAN {"eps": 0.32, "metric": "cosine", "min_samples": 2}
- Silhouette Score: 0.752721104597836
- Calinski-Harabasz: 13.501060896065765
- Davies-Bouldin: 0.6898200510253327
- cluster count: 54
- cross-subject contamination: 0.0556

Production note:
This run is an offline unsupervised experiment. It does not deploy a model automatically. The semantic affinity outputs are suitable for review and shadow comparison before production use.
