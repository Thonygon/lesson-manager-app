# Resource Affinity Unsupervised Discovery Technical Report

Business question: Can Classio discover semantic relationships between educational resources without manual labels, so teacher recommendations and pre-generation similar-resource warnings work from meaning rather than only tags?

Method:
- Canonical resource profiles were built from worksheets, exams, videos, lesson plans, and learning programs.
- Text profiles were vectorized with TF-IDF and reduced/normalized into dense semantic vectors when possible.
- K-Means, Agglomerative Clustering, and DBSCAN were compared as unsupervised models.
- Cosine similarity was used to produce nearest-neighbor affinity candidates.

Dataset summary:
- extraction timestamp: 2026-07-28T14:12:36.787498+00:00
- source rows inspected: 194
- included resources: 193
- resource types: {'worksheet': 90, 'video': 48, 'exam': 33, 'lesson_plan': 15, 'program': 7}
- subjects represented: 4

Model comparison:
- best candidate: DBSCAN eps=0.32 min_samples=2 {"eps": 0.32, "metric": "cosine", "min_samples": 2}
- Silhouette Score: 0.7516899542882908
- Calinski-Harabasz: 13.683334775181088
- Davies-Bouldin: 0.7063268752318753
- cluster count: 57
- cross-subject contamination: 0.0526

Production note:
This run is an offline unsupervised experiment. It does not deploy a model automatically. The semantic affinity outputs are suitable for review and shadow comparison before production use.
