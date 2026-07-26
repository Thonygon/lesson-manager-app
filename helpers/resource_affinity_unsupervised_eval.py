from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any
import uuid

import numpy as np
import pandas as pd

from helpers.assigned_resource_open_7d_eval import _fetch_all_rows, _json_safe
from helpers.archive_utils import is_archived_status


FEATURE_SCHEMA_VERSION = "resource_affinity_unsupervised.v1"
DEFAULT_SEED = 20260726
DEFAULT_OUTPUT_DIR = Path("reports") / "ml_architecture" / "resource_affinity_unsupervised"
FROZEN_DATASET_FILENAME = "resource_affinity_dataset_frozen.csv"
PROFILE_AUDIT_FILENAME = "resource_affinity_profile_audit.csv"
FEATURE_AUDIT_FILENAME = "resource_affinity_feature_audit.csv"
MODEL_COMPARISON_FILENAME = "resource_affinity_model_comparison.csv"
CLUSTER_ASSIGNMENTS_FILENAME = "resource_affinity_cluster_assignments.csv"
NEIGHBORS_FILENAME = "resource_affinity_pairwise_neighbors.csv"
RUN_SUMMARY_FILENAME = "resource_affinity_run_summary.json"
TECHNICAL_REPORT_FILENAME = "resource_affinity_technical_report.md"
ACADEMIC_REPORT_FILENAME = "resource_affinity_findings_interpretation_report.md"
INTEGRITY_REVIEW_FILENAME = "resource_affinity_integrity_review.md"
RECONCILIATION_FILENAME = "resource_affinity_reconciliation.csv"
TARGET_NAME = "semantic_cluster"

RESOURCE_TABLE_SPECS = {
    "worksheet": (
        "worksheets",
        "id,user_id,title,subject,topic,learner_stage,level_or_band,worksheet_type,source_type,student_material_language,plan_language,author_name,subject_display,is_public,status,created_at",
    ),
    "exam": (
        "quick_exams",
        "id,user_id,title,subject,topic,learner_stage,level,exam_length,exercise_types,is_public,status,created_at",
    ),
    "video": (
        "videos",
        "id,user_id,title,subject,custom_subject_name,topic,description,learner_stage,level_or_band,is_public,status,created_at,updated_at",
    ),
    "lesson_plan": (
        "lesson_plans",
        "id,user_id,title,subject,topic,learner_stage,level_or_band,lesson_purpose,source_type,planner_mode,author_name,subject_display,is_public,status,created_at,updated_at",
    ),
    "program": (
        "learning_programs",
        "id,user_id,title,subject,custom_subject_name,learner_stage,level_or_band,program_overview,is_public,status,total_units,total_topics,sequence_order,created_at,updated_at",
    ),
}

MATERIAL_KINDS = {"worksheet", "exam", "video", "lesson_plan", "program"}
PROFILE_COLUMNS = [
    "resource_key",
    "resource_type",
    "resource_id",
    "title",
    "subject",
    "language",
    "level",
    "learner_stage",
    "topic",
    "subtype",
    "is_public",
    "status",
    "created_at",
    "updated_at",
    "profile_text",
    "profile_hash",
    "profile_token_count",
]
MODEL_COMPARISON_COLUMNS = [
    "model_name",
    "algorithm_name",
    "model_key",
    "status",
    "parameters_json",
    "silhouette_score",
    "calinski_harabasz",
    "davies_bouldin",
    "cluster_count",
    "noise_ratio",
    "singleton_cluster_count",
    "cross_subject_contamination_rate",
    "cross_language_contamination_rate",
    "train_duration_ms",
    "inference_duration_ms",
    "failure_reason",
]
NEIGHBOR_COLUMNS = [
    "source_resource_key",
    "source_resource_type",
    "source_title",
    "target_resource_key",
    "target_resource_type",
    "target_title",
    "similarity_score",
    "same_subject",
    "same_language",
    "same_level",
]
CLUSTER_COLUMNS = ["resource_key", "resource_type", "resource_id", "title", "subject", "language", "level", "topic", "cluster_id"]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    return (value or _utc_now()).astimezone(timezone.utc).isoformat()


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _norm_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().casefold()).strip("_")


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value in (None, "", "nan"):
            return default
        number = float(value)
        return number if math.isfinite(number) else default
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, "", "nan"):
            return default
        return int(float(value))
    except Exception:
        return default


def _hash_text(value: str, length: int = 16) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()[:length]


def _parse_jsonish(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    text = _clean_text(value)
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception:
        return value


def _flatten_json_text(value: Any, *, max_items: int = 80) -> str:
    payload = _parse_jsonish(value)
    parts: list[str] = []

    def walk(item: Any) -> None:
        if len(parts) >= max_items:
            return
        if isinstance(item, dict):
            for key, child in item.items():
                key_text = _clean_text(key)
                if key_text and key_text.lower() not in {"id", "user_id", "created_at", "updated_at", "image", "image_url"}:
                    parts.append(key_text)
                walk(child)
        elif isinstance(item, list):
            for child in item:
                walk(child)
        else:
            text = _clean_text(item)
            if text and len(text) <= 800:
                parts.append(text)

    walk(payload)
    return " ".join(parts)


def _field(row: dict[str, Any], *names: str) -> str:
    for name in names:
        value = row.get(name)
        if value not in (None, ""):
            return _clean_text(value)
    return ""


def _resource_language(row: dict[str, Any]) -> str:
    return _field(row, "student_material_language", "plan_language", "language", "lang").lower()


def build_resource_profile(row: dict[str, Any], resource_type: str) -> dict[str, Any]:
    rid = _clean_text(row.get("id"))
    subject = _field(row, "subject", "subject_key", "custom_subject_name")
    level = _field(row, "level_or_band", "level")
    stage = _field(row, "learner_stage")
    topic = _field(row, "topic")
    title = _field(row, "title")
    subtype = _field(row, "worksheet_type", "exam_length", "lesson_purpose", "planner_mode", "source_type")
    language = _resource_language(row)
    detail_fields = [
        "description",
        "program_overview",
        "worksheet_json",
        "exam_data",
        "plan_json",
        "program_data",
        "lesson_plan_json",
        "content_json",
        "exercise_types",
    ]
    detail_text = " ".join(_flatten_json_text(row.get(name)) for name in detail_fields if row.get(name) not in (None, ""))
    profile_text = _clean_text(
        " ".join(
            [
                f"Resource type: {resource_type}",
                f"Title: {title}",
                f"Subject: {subject}",
                f"Language: {language}",
                f"Level: {level}",
                f"Learner stage: {stage}",
                f"Topic: {topic}",
                f"Subtype: {subtype}",
                detail_text,
            ]
        )
    )
    return {
        "resource_key": f"{resource_type}:{rid}",
        "resource_type": resource_type,
        "resource_id": rid,
        "title": title,
        "subject": subject,
        "language": language,
        "level": level,
        "learner_stage": stage,
        "topic": topic,
        "subtype": subtype,
        "is_public": bool(row.get("is_public")),
        "status": _clean_text(row.get("status")),
        "created_at": _clean_text(row.get("created_at")),
        "updated_at": _clean_text(row.get("updated_at")),
        "profile_text": profile_text,
        "profile_hash": _hash_text(profile_text),
        "profile_token_count": len(re.findall(r"\w+", profile_text)),
    }


def extract_resource_profiles(extraction_time: datetime | None = None) -> tuple[pd.DataFrame, dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    raw_counts: dict[str, int] = {}
    for resource_type, (table_name, columns) in RESOURCE_TABLE_SPECS.items():
        try:
            table_rows = _fetch_all_rows(table_name, columns, page_size=500)
        except Exception as exc:
            errors.append({"resource_type": resource_type, "table_name": table_name, "error": str(exc)})
            table_rows = []
        raw_counts[resource_type] = len(table_rows)
        for row in table_rows:
            if is_archived_status(row.get("status")):
                continue
            profile = build_resource_profile(row, resource_type)
            if profile["resource_id"] and profile["profile_token_count"] >= 3:
                rows.append(profile)
    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=PROFILE_COLUMNS)
    if not df.empty:
        df = df.drop_duplicates(subset=["resource_key", "profile_hash"]).reset_index(drop=True)
    diagnostics = {
        "extracted_at": _iso(extraction_time),
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "source_row_count": int(sum(raw_counts.values())),
        "included_row_count": int(len(df)),
        "resource_count": int(df["resource_key"].nunique()) if not df.empty else 0,
        "raw_counts_by_type": raw_counts,
        "included_counts_by_type": df["resource_type"].value_counts().to_dict() if not df.empty else {},
        "subject_count": int(df["subject"].replace("", pd.NA).nunique()) if not df.empty else 0,
        "language_count": int(df["language"].replace("", pd.NA).nunique()) if not df.empty else 0,
        "level_count": int(df["level"].replace("", pd.NA).nunique()) if not df.empty else 0,
        "errors": errors,
        "data_fingerprint": _hash_text("|".join(sorted(df["profile_hash"].tolist())) if not df.empty else "empty", 24),
    }
    return df, diagnostics


def _sklearn_imports():
    from sklearn.cluster import AgglomerativeClustering, DBSCAN, KMeans
    from sklearn.decomposition import TruncatedSVD
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics import calinski_harabasz_score, davies_bouldin_score, silhouette_score
    from sklearn.metrics.pairwise import cosine_similarity
    from sklearn.preprocessing import Normalizer

    return {
        "AgglomerativeClustering": AgglomerativeClustering,
        "DBSCAN": DBSCAN,
        "KMeans": KMeans,
        "TruncatedSVD": TruncatedSVD,
        "TfidfVectorizer": TfidfVectorizer,
        "Normalizer": Normalizer,
        "calinski_harabasz_score": calinski_harabasz_score,
        "davies_bouldin_score": davies_bouldin_score,
        "silhouette_score": silhouette_score,
        "cosine_similarity": cosine_similarity,
    }


def _build_vectors(profile_df: pd.DataFrame) -> tuple[np.ndarray, dict[str, Any]]:
    sk = _sklearn_imports()
    texts = profile_df["profile_text"].fillna("").astype(str).tolist()
    vectorizer = sk["TfidfVectorizer"](
        lowercase=True,
        strip_accents="unicode",
        ngram_range=(1, 2),
        min_df=1,
        max_df=0.92,
        max_features=1600,
    )
    tfidf = vectorizer.fit_transform(texts)
    n_features = int(tfidf.shape[1])
    if min(tfidf.shape) > 3:
        n_components = max(2, min(64, min(tfidf.shape) - 1))
        svd = sk["TruncatedSVD"](n_components=n_components, random_state=DEFAULT_SEED)
        vectors = svd.fit_transform(tfidf)
        vectors = sk["Normalizer"](copy=False).fit_transform(vectors)
        explained = float(np.sum(getattr(svd, "explained_variance_ratio_", np.array([]))))
        method = "tfidf_truncated_svd"
    else:
        vectors = tfidf.toarray()
        vectors = sk["Normalizer"](copy=False).fit_transform(vectors)
        explained = None
        method = "tfidf_dense"
    manifest = {
        "embedding_method": method,
        "vectorizer": "TfidfVectorizer",
        "ngram_range": "1,2",
        "feature_count": n_features,
        "vector_dimensions": int(vectors.shape[1]) if len(vectors.shape) == 2 else 0,
        "explained_variance_ratio_sum": explained,
    }
    return np.asarray(vectors, dtype=float), manifest


def _label_quality(labels: np.ndarray, vectors: np.ndarray, profile_df: pd.DataFrame) -> dict[str, Any]:
    unique_labels = sorted({int(item) for item in labels})
    cluster_labels = [item for item in unique_labels if item >= 0]
    cluster_count = len(cluster_labels)
    noise_count = int(np.sum(labels < 0))
    usable_mask = labels >= 0
    usable_labels = labels[usable_mask]
    usable_vectors = vectors[usable_mask]
    metrics: dict[str, Any] = {
        "cluster_count": cluster_count,
        "noise_count": noise_count,
        "noise_ratio": round(noise_count / max(1, len(labels)), 4),
        "singleton_cluster_count": 0,
        "cross_subject_contamination_rate": None,
        "cross_language_contamination_rate": None,
        "silhouette_score": None,
        "calinski_harabasz": None,
        "davies_bouldin": None,
    }
    if cluster_count >= 1:
        counts = pd.Series(labels[labels >= 0]).value_counts()
        metrics["singleton_cluster_count"] = int((counts == 1).sum())
    if cluster_count >= 2 and len(usable_vectors) > cluster_count:
        sk = _sklearn_imports()
        try:
            metrics["silhouette_score"] = float(sk["silhouette_score"](usable_vectors, usable_labels, metric="cosine"))
        except Exception:
            pass
        try:
            metrics["calinski_harabasz"] = float(sk["calinski_harabasz_score"](usable_vectors, usable_labels))
        except Exception:
            pass
        try:
            metrics["davies_bouldin"] = float(sk["davies_bouldin_score"](usable_vectors, usable_labels))
        except Exception:
            pass

    contamination_subject = []
    contamination_language = []
    tmp = profile_df.copy()
    tmp["_cluster"] = labels
    for _cluster, group in tmp[tmp["_cluster"] >= 0].groupby("_cluster"):
        if len(group) <= 1:
            continue
        contamination_subject.append(1.0 if group["subject"].replace("", pd.NA).dropna().nunique() > 1 else 0.0)
        contamination_language.append(1.0 if group["language"].replace("", pd.NA).dropna().nunique() > 1 else 0.0)
    if contamination_subject:
        metrics["cross_subject_contamination_rate"] = round(sum(contamination_subject) / len(contamination_subject), 4)
    if contamination_language:
        metrics["cross_language_contamination_rate"] = round(sum(contamination_language) / len(contamination_language), 4)
    return metrics


def _candidate_models(n_rows: int) -> list[tuple[str, dict[str, Any]]]:
    if n_rows < 3:
        return []
    candidates: list[tuple[str, dict[str, Any]]] = []
    for k in sorted({2, 3, 4, 5, max(2, min(8, int(round(math.sqrt(n_rows)))))}):
        if 1 < k < n_rows:
            candidates.append(("KMeans", {"n_clusters": k}))
            candidates.append(("AgglomerativeClustering", {"n_clusters": k}))
    for eps in (0.32, 0.42, 0.52, 0.62):
        candidates.append(("DBSCAN", {"eps": eps, "min_samples": 2, "metric": "cosine"}))
    return candidates


def _candidate_display_name(model_name: str, params: dict[str, Any]) -> str:
    if model_name in {"KMeans", "AgglomerativeClustering"}:
        clusters = params.get("n_clusters")
        return f"{model_name} k={clusters}" if clusters else model_name
    if model_name == "DBSCAN":
        eps = params.get("eps")
        min_samples = params.get("min_samples")
        parts = []
        if eps is not None:
            parts.append(f"eps={eps}")
        if min_samples is not None:
            parts.append(f"min_samples={min_samples}")
        return f"{model_name} {' '.join(parts)}".strip()
    return model_name


def evaluate_unsupervised_models(profile_df: pd.DataFrame, vectors: np.ndarray) -> tuple[pd.DataFrame, dict[str, np.ndarray]]:
    sk = _sklearn_imports()
    rows: list[dict[str, Any]] = []
    labels_by_model: dict[str, np.ndarray] = {}
    for model_name, params in _candidate_models(len(profile_df)):
        status = "ok"
        failure_reason = ""
        labels = np.array([], dtype=int)
        started = datetime.now()
        try:
            if model_name == "KMeans":
                model = sk["KMeans"](n_init=10, random_state=DEFAULT_SEED, **params)
                labels = model.fit_predict(vectors)
            elif model_name == "AgglomerativeClustering":
                model = sk["AgglomerativeClustering"](metric="cosine", linkage="average", **params)
                labels = model.fit_predict(vectors)
            elif model_name == "DBSCAN":
                model = sk["DBSCAN"](**params)
                labels = model.fit_predict(vectors)
            else:
                raise ValueError(model_name)
        except Exception as exc:
            status = "failed"
            failure_reason = str(exc)
        elapsed_ms = int((datetime.now() - started).total_seconds() * 1000)
        if labels.size:
            quality = _label_quality(labels, vectors, profile_df)
            model_key = f"{model_name}:{json.dumps(params, sort_keys=True)}"
            labels_by_model[model_key] = labels
        else:
            quality = {
                "cluster_count": 0,
                "noise_count": 0,
                "noise_ratio": None,
                "singleton_cluster_count": 0,
                "cross_subject_contamination_rate": None,
                "cross_language_contamination_rate": None,
                "silhouette_score": None,
                "calinski_harabasz": None,
                "davies_bouldin": None,
            }
            model_key = f"{model_name}:{json.dumps(params, sort_keys=True)}"
        rows.append(
            {
                "model_name": _candidate_display_name(model_name, params),
                "algorithm_name": model_name,
                "model_key": model_key,
                "status": status,
                "parameters_json": json.dumps(params, sort_keys=True),
                "silhouette_score": quality.get("silhouette_score"),
                "calinski_harabasz": quality.get("calinski_harabasz"),
                "davies_bouldin": quality.get("davies_bouldin"),
                "cluster_count": quality.get("cluster_count"),
                "noise_ratio": quality.get("noise_ratio"),
                "singleton_cluster_count": quality.get("singleton_cluster_count"),
                "cross_subject_contamination_rate": quality.get("cross_subject_contamination_rate"),
                "cross_language_contamination_rate": quality.get("cross_language_contamination_rate"),
                "train_duration_ms": elapsed_ms,
                "inference_duration_ms": 0,
                "failure_reason": failure_reason,
            }
        )
    comparison = pd.DataFrame(rows)
    if not comparison.empty:
        comparison["_rank_silhouette"] = comparison["silhouette_score"].fillna(-2)
        comparison["_rank_contamination"] = comparison["cross_subject_contamination_rate"].fillna(1)
        comparison = comparison.sort_values(["_rank_silhouette", "_rank_contamination"], ascending=[False, True])
        comparison = comparison.drop(columns=["_rank_silhouette", "_rank_contamination"])
    return comparison.reset_index(drop=True), labels_by_model


def _top_neighbors(profile_df: pd.DataFrame, vectors: np.ndarray, *, top_k: int = 5) -> pd.DataFrame:
    if profile_df.empty or len(profile_df) < 2:
        return pd.DataFrame()
    sk = _sklearn_imports()
    sim = sk["cosine_similarity"](vectors)
    rows: list[dict[str, Any]] = []
    records = profile_df.to_dict("records")
    for i, source in enumerate(records):
        order = np.argsort(-sim[i])
        emitted = 0
        for j in order:
            if i == int(j):
                continue
            target = records[int(j)]
            score = float(sim[i, int(j)])
            rows.append(
                {
                    "source_resource_key": source["resource_key"],
                    "source_resource_type": source["resource_type"],
                    "source_title": source["title"],
                    "target_resource_key": target["resource_key"],
                    "target_resource_type": target["resource_type"],
                    "target_title": target["title"],
                    "similarity_score": round(score, 6),
                    "same_subject": _norm_key(source.get("subject")) == _norm_key(target.get("subject")),
                    "same_language": _norm_key(source.get("language")) == _norm_key(target.get("language")) if source.get("language") and target.get("language") else None,
                    "same_level": _norm_key(source.get("level")) == _norm_key(target.get("level")) if source.get("level") and target.get("level") else None,
                }
            )
            emitted += 1
            if emitted >= top_k:
                break
    return pd.DataFrame(rows)


def _best_model_row(comparison: pd.DataFrame) -> dict[str, Any]:
    if comparison.empty:
        return {}
    ok = comparison[comparison["status"] == "ok"].copy()
    if ok.empty:
        return comparison.iloc[0].to_dict()
    return ok.iloc[0].to_dict()


def _render_technical_report(summary: dict[str, Any]) -> str:
    dataset = summary.get("dataset") or {}
    evaluation = summary.get("evaluation") or {}
    best = evaluation.get("best_model") or {}
    lines = [
        "# Resource Affinity Unsupervised Discovery Technical Report",
        "",
        "Business question: Can Classio discover semantic relationships between educational resources without manual labels, so teacher recommendations and pre-generation similar-resource warnings work from meaning rather than only tags?",
        "",
        "Method:",
        "- Canonical resource profiles were built from worksheets, exams, videos, lesson plans, and learning programs.",
        "- Text profiles were vectorized with TF-IDF and reduced/normalized into dense semantic vectors when possible.",
        "- K-Means, Agglomerative Clustering, and DBSCAN were compared as unsupervised models.",
        "- Cosine similarity was used to produce nearest-neighbor affinity candidates.",
        "",
        "Dataset summary:",
        f"- extraction timestamp: {dataset.get('extracted_at')}",
        f"- source rows inspected: {dataset.get('source_row_count')}",
        f"- included resources: {dataset.get('included_row_count')}",
        f"- resource types: {dataset.get('included_counts_by_type')}",
        f"- subjects represented: {dataset.get('subject_count')}",
        "",
        "Model comparison:",
        f"- best candidate: {best.get('model_name')} {best.get('parameters_json')}",
        f"- Silhouette Score: {best.get('silhouette_score')}",
        f"- Calinski-Harabasz: {best.get('calinski_harabasz')}",
        f"- Davies-Bouldin: {best.get('davies_bouldin')}",
        f"- cluster count: {best.get('cluster_count')}",
        f"- cross-subject contamination: {best.get('cross_subject_contamination_rate')}",
        "",
        "Production note:",
        "This run is an offline unsupervised experiment. It does not deploy a model automatically. The semantic affinity outputs are suitable for review and shadow comparison before production use.",
    ]
    return "\n".join(lines) + "\n"


def _render_academic_report(summary: dict[str, Any]) -> str:
    dataset = summary.get("dataset") or {}
    evaluation = summary.get("evaluation") or {}
    best = evaluation.get("best_model") or {}
    lines = [
        "# Experimento 3 - Descubrimiento no supervisado de afinidad entre recursos",
        "",
        "## Planteamiento de la solución",
        "Classio ya cuenta con recomendaciones basadas en reglas, metadatos y señales de uso. La limitación es que dos recursos pueden estar relacionados pedagógicamente aunque sus etiquetas, títulos o temas no coincidan exactamente. Para abordar este problema, se propone una capa de aprendizaje no supervisado que descubra afinidad semántica entre recursos educativos.",
        "",
        "El sistema no sustituye el ranker actual. Primero descubre recursos semánticamente cercanos y después las reglas de negocio de Classio filtran por profesor, estudiante, asignatura, idioma, nivel, programa de aprendizaje, estado de archivo y tipo de recurso.",
        "",
        "Objetivos SMART:",
        "- Específico: construir un modelo no supervisado que agrupe recursos de Classio por similitud semántica educativa.",
        "- Medible: comparar K-Means, Agglomerative Clustering y DBSCAN con Silhouette Score, Calinski-Harabasz, Davies-Bouldin y tasa de contaminación entre asignaturas.",
        "- Alcanzable: usar los recursos ya almacenados en Classio como dataset inicial.",
        "- Realista: ejecutar el modelo en modo offline/experimental antes de impactar recomendaciones en producción.",
        "- Acotado en el tiempo: producir un reporte reproducible de Experimento 3 para revisión antes de integrar el mejor modelo.",
        "",
        "## Desarrollo del modelo",
        f"Dataset utilizado: {dataset.get('included_row_count')} recursos educativos extraídos de Classio a partir de worksheets, exams, videos, lesson plans y learning programs.",
        "Cada recurso se transformó en un perfil canónico de texto que combina título, asignatura, idioma, nivel, etapa, tema, subtipo y contenido pedagógico disponible. Esos perfiles se vectorizaron con TF-IDF y, cuando el tamaño del dataset lo permite, se redujeron con Truncated SVD y se normalizaron para usar similaridad coseno.",
        "",
        "Modelos evaluados:",
        "- K-Means",
        "- Agglomerative Clustering",
        "- DBSCAN",
        "",
        "Indicadores clave:",
        f"- Mejor modelo: {best.get('model_name')} {best.get('parameters_json')}",
        f"- Silhouette Score: {best.get('silhouette_score')}",
        f"- Calinski-Harabasz: {best.get('calinski_harabasz')}",
        f"- Davies-Bouldin: {best.get('davies_bouldin')}",
        f"- Número de clusters: {best.get('cluster_count')}",
        f"- Contaminación entre asignaturas: {best.get('cross_subject_contamination_rate')}",
        "",
        "## Conclusiones",
        f"El experimento generó un mapa de afinidad semántica para {dataset.get('included_row_count')} recursos. La utilidad productiva debe valorarse revisando los vecinos semánticos y la coherencia de los clusters antes de activar el modelo en producción.",
        "",
        "¿Tiene un índice de acierto aceptable? En aprendizaje no supervisado no existe una etiqueta de acierto directa. Por eso se usan métricas de coherencia de cluster, contaminación entre asignaturas/idiomas y revisión de vecinos semánticos como proxy de calidad.",
        "",
        "¿Podríamos llevarlo a producción? No directamente desde esta fase. El siguiente paso recomendado es usar el mejor modelo en modo sombra para mejorar el pool de candidatos en recomendaciones de profesor y en las alertas de recursos similares antes de generación.",
        "",
        "¿Necesitamos otros datos? Sí. Para validar mejor el modelo hacen falta más recursos, revisiones humanas de pares similares/no similares y eventos de uso posteriores que indiquen si los recursos semánticamente cercanos realmente son aceptados por profesores y estudiantes.",
    ]
    return "\n".join(lines) + "\n"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(_json_safe(payload), indent=2, sort_keys=True), encoding="utf-8")


def _write_frame(path: Path, frame: pd.DataFrame) -> None:
    frame.to_csv(path, index=False)


def generate_resource_affinity_unsupervised_evaluation(output_dir: Path | str = DEFAULT_OUTPUT_DIR, *, run_id: str | None = None) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    extraction_time = _utc_now()
    profile_df, dataset_summary = extract_resource_profiles(extraction_time)
    if profile_df.empty:
        comparison = pd.DataFrame(columns=MODEL_COMPARISON_COLUMNS)
        neighbors = pd.DataFrame(columns=NEIGHBOR_COLUMNS)
        cluster_assignments = pd.DataFrame(columns=CLUSTER_COLUMNS)
        embedding_manifest = {}
    else:
        vectors, embedding_manifest = _build_vectors(profile_df)
        comparison, labels_by_model = evaluate_unsupervised_models(profile_df, vectors)
        neighbors = _top_neighbors(profile_df, vectors, top_k=5)
        best = _best_model_row(comparison)
        best_labels = labels_by_model.get(str(best.get("model_key") or ""), np.array([], dtype=int))
        cluster_assignments = profile_df[["resource_key", "resource_type", "resource_id", "title", "subject", "language", "level", "topic"]].copy()
        cluster_assignments["cluster_id"] = best_labels if len(best_labels) == len(cluster_assignments) else -1

    best_model = _best_model_row(comparison)
    high_confidence_neighbors = int((neighbors.get("similarity_score", pd.Series(dtype=float)).astype(float) >= 0.72).sum()) if not neighbors.empty else 0
    evaluation = {
        "experiment_id": "resource_affinity_unsupervised_discovery",
        "run_id": run_id or uuid.uuid4().hex[:12],
        "primary_metric": "silhouette_score",
        "primary_metric_leader": best_model.get("model_name"),
        "winner": best_model.get("model_name"),
        "best_model": best_model,
        "maturity_verdict": "EXPLORATORY_ONLY" if int(dataset_summary.get("included_row_count") or 0) < 80 else "CANDIDATE_FOR_SHADOW_TESTING",
        "overall_evidence_strength": "EXPLORATORY_SEMANTIC_AFFINITY",
        "high_confidence_neighbor_edges": high_confidence_neighbors,
        "feature_names": ["profile_text", "subject", "language", "level", "resource_type"],
        "embedding_manifest": embedding_manifest,
        "limitations": [
            "No human-labeled semantic relevance labels are used in this unsupervised phase.",
            "Small or imbalanced resource catalogs can make clustering metrics unstable.",
            "Business rules must still filter by subject, language, teacher, student, level, and archive state.",
        ],
    }
    summary = {
        "generated_at": _iso(),
        "dataset": dataset_summary,
        "evaluation": evaluation,
        "review": {
            "label_reconciliation": {
                "summary": "Unsupervised experiment: no supervised label construction was used.",
                "limitations": evaluation["limitations"],
            }
        },
    }

    profile_audit = profile_df[
        ["resource_key", "resource_type", "resource_id", "profile_hash", "profile_token_count", "title", "subject", "language", "level", "topic"]
    ].copy() if not profile_df.empty else pd.DataFrame(columns=["resource_key", "resource_type", "resource_id", "profile_hash", "profile_token_count", "title", "subject", "language", "level", "topic"])
    feature_audit = pd.DataFrame(
        [
            {"feature": "profile_text", "retained": True, "role": "unsupervised_text_profile", "exclusion_reason": ""},
            {"feature": "subject", "retained": True, "role": "business_scope_quality_check", "exclusion_reason": ""},
            {"feature": "language", "retained": True, "role": "business_scope_quality_check", "exclusion_reason": ""},
            {"feature": "level", "retained": True, "role": "business_scope_quality_check", "exclusion_reason": ""},
            {"feature": "resource_type", "retained": True, "role": "business_scope_quality_check", "exclusion_reason": ""},
        ]
    )
    reconciliation = pd.DataFrame(
        [
            {
                "check": "supervised_labels_not_required",
                "status": "passed",
                "detail": "Experiment 3 uses unsupervised clustering and cosine-neighbor analysis.",
            }
        ]
    )

    _write_frame(output / FROZEN_DATASET_FILENAME, profile_df)
    _write_frame(output / PROFILE_AUDIT_FILENAME, profile_audit)
    _write_frame(output / FEATURE_AUDIT_FILENAME, feature_audit)
    _write_frame(output / MODEL_COMPARISON_FILENAME, comparison)
    _write_frame(output / CLUSTER_ASSIGNMENTS_FILENAME, cluster_assignments)
    _write_frame(output / NEIGHBORS_FILENAME, neighbors)
    _write_frame(output / RECONCILIATION_FILENAME, reconciliation)
    _write_json(output / "resource_affinity_embedding_manifest.json", embedding_manifest)
    _write_json(output / "resource_affinity_dataset_summary.json", dataset_summary)
    _write_json(output / RUN_SUMMARY_FILENAME, summary)
    (output / TECHNICAL_REPORT_FILENAME).write_text(_render_technical_report(summary), encoding="utf-8")
    (output / ACADEMIC_REPORT_FILENAME).write_text(_render_academic_report(summary), encoding="utf-8")
    (output / INTEGRITY_REVIEW_FILENAME).write_text(review_resource_affinity_unsupervised(output)["review_markdown"], encoding="utf-8")
    return {
        "dataset": dataset_summary,
        "evaluation": evaluation,
        "artifacts": {
            "run_summary": str(output / RUN_SUMMARY_FILENAME),
            "model_comparison": str(output / MODEL_COMPARISON_FILENAME),
            "neighbors": str(output / NEIGHBORS_FILENAME),
            "academic_report": str(output / ACADEMIC_REPORT_FILENAME),
        },
    }


def review_resource_affinity_unsupervised(output_dir: Path | str) -> dict[str, Any]:
    output = Path(output_dir)
    summary_path = output / RUN_SUMMARY_FILENAME
    comparison_path = output / MODEL_COMPARISON_FILENAME
    neighbors_path = output / NEIGHBORS_FILENAME
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    try:
        comparison = pd.read_csv(comparison_path) if comparison_path.exists() else pd.DataFrame(columns=MODEL_COMPARISON_COLUMNS)
    except Exception:
        comparison = pd.DataFrame(columns=MODEL_COMPARISON_COLUMNS)
    try:
        neighbors = pd.read_csv(neighbors_path) if neighbors_path.exists() else pd.DataFrame(columns=NEIGHBOR_COLUMNS)
    except Exception:
        neighbors = pd.DataFrame(columns=NEIGHBOR_COLUMNS)
    dataset = summary.get("dataset") or {}
    blocking: list[str] = []
    warnings: list[str] = []
    if int(dataset.get("included_row_count") or 0) < 6:
        blocking.append("Fewer than six resources are available for unsupervised comparison.")
    if comparison.empty or not (comparison.get("status", pd.Series(dtype=str)).astype(str) == "ok").any():
        blocking.append("No unsupervised model completed successfully.")
    if neighbors.empty:
        warnings.append("No semantic-neighbor artifact was generated.")
    verdict = "REQUIRES_RERUN" if blocking else "VALIDATED_EXPLORATORY_RUN"
    overall = "NO_ROBUST_WINNER" if blocking else "EXPLORATORY_SEMANTIC_AFFINITY"
    markdown = [
        "# Resource Affinity Unsupervised Integrity Review",
        "",
        f"Final verdict: {verdict}",
        f"Overall model conclusion: {overall}",
        "",
        "Checks:",
        f"- resources included: {dataset.get('included_row_count')}",
        f"- completed model rows: {int((comparison.get('status', pd.Series(dtype=str)).astype(str) == 'ok').sum()) if not comparison.empty else 0}",
        f"- neighbor rows: {len(neighbors)}",
    ]
    if blocking:
        markdown.append("")
        markdown.append("Blocking reasons:")
        markdown.extend(f"- {item}" for item in blocking)
    if warnings:
        markdown.append("")
        markdown.append("Warnings:")
        markdown.extend(f"- {item}" for item in warnings)
    review = {
        "final_verdict": verdict,
        "overall_model_conclusion": overall,
        "blocking_reasons": blocking,
        "warnings": warnings,
        "review_markdown": "\n".join(markdown) + "\n",
    }
    if output.exists():
        (output / INTEGRITY_REVIEW_FILENAME).write_text(review["review_markdown"], encoding="utf-8")
    return review
