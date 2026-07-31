# Resource Affinity Unsupervised Discovery Technical Report

Business question: Can Classio align worksheets, exams, videos, lesson plans, and learning programs to learning-program topic anchors without manual labels, so teacher recommendations and pre-generation similar-resource warnings start from the intended curriculum topic before heuristic rules are applied?

Method:
- Program topics are treated as curricular anchors, not complete resources.
- Candidate resource profiles were built from worksheets, exams, videos, lesson plans, and learning programs.
- Text profiles were vectorized with TF-IDF and reduced/normalized into dense semantic vectors when possible.
- K-Means, Agglomerative Clustering, and DBSCAN were compared as unsupervised models.
- Cosine similarity was used to produce both pairwise neighbors and explicit program-topic to candidate-resource alignment candidates.

Python model development methodology:
- language: Python
- core libraries: ['pandas', 'numpy', 'scikit-learn']
- data sources: {'worksheets': 'worksheets table: title, subject, topic, learner stage, level/band, worksheet type, language fields, status, visibility, and creation timestamp. Full worksheet_json is not fetched by the experiment.', 'exams': 'quick_exams table: title, subject, topic, learner stage, level, exam length, exercise types, status, visibility, and creation timestamp. Full exam_data is not fetched by the experiment.', 'videos': 'videos table: title, subject/custom subject, topic, description, learner stage, level/band, status, visibility, creation/update timestamps.', 'lesson_plans': 'lesson_plans table: title, subject, topic, learner stage, level/band, lesson purpose, source/planner metadata, language fields, status, visibility, creation/update timestamps, and plan_json content.', 'learning_programs': 'learning_programs table: title, subject/custom subject, learner stage, level/band, overview, status, visibility, unit/topic counts, sequence order, timestamps, and program_data content.', 'learning_program_topics': 'learning_program_topics table: program_id, unit/topic order, title, subtopic, lesson focus, lesson purpose, objectives, success criteria, can-do statements, suggested worksheet/exam types, homework idea, teacher notes, student summary, estimated lessons, and timestamps.', 'bounded_content_excerpts': 'Optional resource_affinity_content_excerpts view: resource_type, resource_id, content_excerpt, source, and character count. This view must return sanitized bounded text only; the experiment does not fetch full worksheet_json or exam_data as its primary path.'}
- inclusion rules: ['Archived rows are excluded before model development.', 'Rows without a stable resource id are excluded.', 'Rows with fewer than three profile tokens are excluded.', 'Duplicate rows with the same resource key and profile hash are excluded after the first occurrence.', 'The primary extractor does not select worksheet_json or exam_data. Content is included only through bounded sanitized excerpts when the lightweight excerpt view exists.', 'If the excerpt view is unavailable, worksheets and exams remain included through metadata-only profiles and the run records a warning.']
- profile construction: ['Each included row becomes one canonical text profile.', 'content_excerpt is included only when a bounded sanitized excerpt is available; images, media, URLs, answer keys, correct answers, and solutions are excluded.', 'program_topic rows are assigned resource_role=curricular_anchor.', 'worksheet, exam, video, lesson_plan, and program rows are assigned resource_role=candidate_resource.', 'Lesson-plan topics are extracted from plan_json keys related to topic, title, objective, focus, vocabulary, success, and assessment, plus the fallback topic field.', 'Program topics inherit parent learning-program metadata when the parent program is available, so topic anchors carry subject, level, and stage context.']
- model pipeline: ['Build a pandas DataFrame of frozen resource profiles.', 'Vectorize profile_text with scikit-learn TfidfVectorizer using unigrams and bigrams.', 'When matrix shape permits, reduce TF-IDF features with TruncatedSVD.', 'Normalize vectors with scikit-learn Normalizer using L2 normalization.', 'Train candidate KMeans, AgglomerativeClustering, and DBSCAN configurations.', 'Evaluate each successful configuration with Silhouette, Calinski-Harabasz, Davies-Bouldin, noise ratio, cluster-size diagnostics, and cross-subject/cross-language contamination.', 'Select the winner by the transparent balanced selection_score formula.', 'Generate pairwise semantic neighbors with cosine similarity.', 'Generate the human-review sample from program_topic anchors to candidate resources.', 'Persist the fitted vectorizer, SVD, normalizer, vector matrix, ordered resource keys, frozen dataset, model comparison, cluster assignments, and audit files.']
- reproducibility controls: ['Random seed is fixed at 20260726.', 'The run stores a dataset fingerprint built from profile hashes.', 'The run stores a configuration hash for the model grid and preprocessing settings.', 'The fitted representation is serialized so runtime scoring does not refit TF-IDF from live data.']

Dataset summary:
- extraction timestamp: 2026-07-28T22:02:35.861044+00:00
- source rows inspected: 542
- included resources: 541
- curricular anchors: 348
- candidate resources: 193
- excluded resources: 1
- exclusions by reason: {'archived_status': 1}
- resource types: {'program_topic': 348, 'worksheet': 90, 'video': 48, 'exam': 33, 'lesson_plan': 15, 'program': 7}
- resource roles: {'curricular_anchor': 348, 'candidate_resource': 193}
- subjects represented: 2
- completeness: {'resource_id': {'known_count': 541, 'missing_count': 0, 'known_pct': 1.0}, 'title': {'known_count': 541, 'missing_count': 0, 'known_pct': 1.0}, 'resource_role': {'known_count': 541, 'missing_count': 0, 'known_pct': 1.0}, 'subject': {'known_count': 541, 'missing_count': 0, 'known_pct': 1.0}, 'language': {'known_count': 90, 'missing_count': 451, 'known_pct': 0.1664}, 'level': {'known_count': 541, 'missing_count': 0, 'known_pct': 1.0}, 'learner_stage': {'known_count': 541, 'missing_count': 0, 'known_pct': 1.0}, 'topic': {'known_count': 534, 'missing_count': 7, 'known_pct': 0.9871}, 'lesson_plan_extracted_topics': {'known_count': 15, 'missing_count': 526, 'known_pct': 0.0277}, 'content_excerpt': {'known_count': 0, 'missing_count': 541, 'known_pct': 0.0}, 'subtype': {'known_count': 486, 'missing_count': 55, 'known_pct': 0.8983}, 'profile_text': {'known_count': 541, 'missing_count': 0, 'known_pct': 1.0}}

Model comparison:
- best candidate: KMeans k=24 {"n_clusters": 24}
- Silhouette Score: 0.21786013255087452
- Calinski-Harabasz: 20.920035419976088
- Davies-Bouldin: 2.24065392491325
- cluster count: 24
- cluster size <= 3 rate: 0.0
- cross-subject contamination: 0.1667 (4/24)
- cross-language contamination: 0.0 (0/4)

Metric notes:
- Silhouette, Calinski-Harabasz, and Davies-Bouldin are calculated only on non-noise observations.
- Silhouette uses cosine distance.
- Contamination rates use normalized category values and ignore empty metadata values in denominators.
- The selected model is the highest balanced selection score, not necessarily the highest Silhouette model.
- Anchor-resource alignment summary: {'top_k': 8, 'directed_edge_count': 2784, 'unique_undirected_pair_count': 2784, 'reciprocal_edge_count': 0, 'reciprocal_edge_rate': 0.0, 'mean_similarity': 0.418796, 'median_similarity': 0.407333, 'min_similarity': 0.139802, 'max_similarity': 0.920814, 'same_subject_rate': 0.9788, 'same_language_rate_known': None, 'same_level_rate_known': 0.3689, 'noise_source_edges': 0, 'noise_target_edges': 0, 'thresholds': {'0.6': 250, '0.7': 79, '0.72': 56, '0.8': 15, '0.9': 1}}

Normalization methodology:
- text cleaning: ['All text fields are converted to strings, collapsed to single spaces, and stripped of leading/trailing whitespace.', 'Unicode text is normalized with NFKC for category comparison.', 'Dash variants are normalized before category comparison.']
- category normalization: ['subject, language, level, resource_type, and resource_role are audited.', 'Category values are case-folded.', 'Slash and pipe separators are converted to spaces.', 'Known aliases are mapped before metrics are calculated.', 'Accent-insensitive fallback keys are used when an alias exists without diacritics.', 'Empty metadata values are excluded from contamination denominators.']
- known aliases: {'subject': {'espanol': 'spanish', 'español': 'spanish', 'spanish language': 'spanish', 'english language': 'english', 'math': 'mathematics', 'maths': 'mathematics'}, 'language': {'english': 'en', 'eng': 'en', 'spanish': 'es', 'espanol': 'es', 'español': 'es', 'turkish': 'tr', 'turkce': 'tr', 'türkçe': 'tr'}}
- vector normalization: ['Canonical profile text is vectorized with TF-IDF using unigrams and bigrams.', 'When TF-IDF shape allows it, Truncated SVD reduces the sparse matrix to dense latent dimensions.', 'All vectors are L2-normalized before cosine similarity, clustering quality calculations, and runtime scoring.']
- audit artifacts: ['resource_affinity_category_normalization_audit.csv', 'resource_affinity_profile_audit.csv', 'resource_affinity_feature_audit.csv', 'resource_affinity_representation_manifest.json']

Winner scoring formula:
- formula: selection_score = silhouette_score - 0.35 * cross_subject_contamination_rate - 0.20 * noise_ratio - 0.12 * cluster_size_2_rate - 0.08 * cluster_size_le_3_rate
- sort order: ['highest selection_score', 'highest silhouette_score as tie-breaker', 'lowest cross_subject_contamination_rate as tie-breaker']
- component definitions: {'silhouette_score': 'Primary unsupervised cohesion/separation metric calculated with cosine distance on non-noise observations.', 'cross_subject_contamination_rate': 'Share of evaluated clusters containing more than one normalized subject among rows with known subject metadata.', 'noise_ratio': 'Share of rows assigned to DBSCAN noise label -1.', 'cluster_size_2_rate': 'Share of clusters with exactly two rows, used as a fragmentation warning.', 'cluster_size_le_3_rate': 'Share of clusters with three or fewer rows, used as a broader fragmentation warning.'}
- weight rationale: ['Silhouette remains the positive base because the experiment is unsupervised and has no human relevance labels yet.', "Cross-subject contamination receives the largest penalty because Classio's recommendation rules treat subject boundaries as business-critical.", 'Noise receives a moderate penalty because a model that leaves many rows unassigned is less useful for candidate generation.', 'Tiny-cluster penalties discourage models that look clean only because they fragment the catalog into very small groups.', 'The weights are heuristic and transparent; they are intended for exploratory model triage, not as proof of recommendation impact.']
- why not Silhouette only: The highest Silhouette model can over-reward small, isolated, or noisy clusters. The balanced score prefers a model that is coherent enough while still preserving coverage and useful cluster structure for downstream heuristics.

Winner explanation:
- winner: KMeans k=24
- metric leader: KMeans k=4
- winner selection score: 0.159515
- metric leader selection score: 0.018735
- reason: The winner is the top balanced selection-score candidate. The metric leader is reported separately because a higher Silhouette score alone can over-reward fragmented, noisy, or business-contaminated cluster structures.

Production note:
This run is an offline unsupervised experiment. It does not deploy a model automatically. The semantic affinity outputs are suitable for review and shadow comparison before production use.
