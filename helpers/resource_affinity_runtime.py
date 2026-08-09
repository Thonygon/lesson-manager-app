from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
import pickle
import re
from typing import Any

import numpy as np
import pandas as pd

from core.database import get_sb
from helpers.resource_gallery import extract_resource_language_value


RUNS_ROOT = Path("reports") / "ml_architecture" / "resource_affinity_unsupervised" / "runs"
MIN_QUERY_ANCHOR_SIMILARITY = 0.38
REPRESENTATION_MANIFEST_FILENAME = "resource_affinity_representation_manifest.json"
MIN_FEATURE_SCHEMA_VERSION = "resource_affinity_unsupervised.v5"
PREFERRED_RUNTIME_MODEL_FAMILY = "kmeans"
ALLOW_NON_KMEANS_RUNTIME_FALLBACK = False
RUN_TABLE = "ml_experiment_runs"
RESOURCE_AFFINITY_EXPERIMENT_ID = "resource_affinity_unsupervised_discovery"


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return re.sub(r"\s+", " ", str(value).strip())


def _norm_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().casefold()).strip("_")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        value = float(value)
        if pd.isna(value):
            return default
        return value
    except Exception:
        return default


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _kind_to_resource_type(kind: Any) -> str:
    safe = _norm_key(kind)
    return {
        "plan": "lesson_plan",
        "lesson_plan": "lesson_plan",
        "lesson": "lesson_plan",
        "worksheet": "worksheet",
        "exam": "exam",
        "quick_exam": "exam",
        "video": "video",
        "program": "program",
        "learning_program": "program",
        "program_topic": "program_topic",
        "learning_program_topic": "program_topic",
    }.get(safe, safe)


def resource_key_for(kind: Any, resource_id: Any) -> str:
    resource_type = _kind_to_resource_type(kind)
    safe_id = _clean_text(resource_id)
    if not resource_type or not safe_id or safe_id.lower() in {"none", "nan", "0"}:
        return ""
    return f"{resource_type}:{safe_id}"


def _resource_id_from_row(row: dict[str, Any]) -> str:
    for key in ("id", "resource_id", "record_id"):
        value = _clean_text(row.get(key))
        if value and value.lower() not in {"none", "nan", "0"}:
            return value
    return ""


def _profile_text_for_candidate(row: dict[str, Any], kind: Any) -> str:
    resource_type = _kind_to_resource_type(kind)
    subject = _clean_text(row.get("subject") or row.get("subject_display"))
    language = _clean_text(extract_resource_language_value(row, resource_type=resource_type))
    level = _clean_text(row.get("level_or_band") or row.get("level"))
    parts = [
        f"Resource type: {resource_type}",
        f"Title: {_clean_text(row.get('title'))}",
        f"Subject: {subject}",
        f"Language: {language}",
        f"Level: {level}",
        f"Learner stage: {_clean_text(row.get('learner_stage'))}",
        f"Topic: {_clean_text(row.get('topic'))}",
        f"Subtype: {_clean_text(row.get('worksheet_type') or row.get('lesson_purpose') or row.get('exam_length'))}",
        f"Description: {_clean_text(row.get('description') or row.get('program_overview'))}",
    ]
    exercise_types = row.get("exercise_types") or []
    if isinstance(exercise_types, list) and exercise_types:
        parts.append("Exercise types: " + ", ".join(_clean_text(item) for item in exercise_types if _clean_text(item)))
    return " ".join(part for part in parts if not part.endswith(": "))


def _profile_text_for_context(context: dict[str, Any], *, kind: Any = "") -> str:
    resource_type = _kind_to_resource_type(kind or context.get("kind") or context.get("resource_kind") or "")
    parts = [
        f"Resource type: {resource_type}",
        f"Title: {_clean_text(context.get('title'))}",
        f"Subject: {_clean_text(context.get('subject') or context.get('subject_key'))}",
        f"Language: {_clean_text(extract_resource_language_value(context, resource_type=resource_type))}",
        f"Level: {_clean_text(context.get('level_or_band') or context.get('level'))}",
        f"Learner stage: {_clean_text(context.get('learner_stage'))}",
        f"Topic: {_clean_text(context.get('topic'))}",
        f"Objective: {_clean_text(context.get('objective'))}",
        f"Focus: {_clean_text(context.get('focus_kind') or context.get('recommendation_bucket') or context.get('lesson_focus'))}",
        f"Subtype: {_clean_text(context.get('worksheet_type') or context.get('lesson_purpose') or context.get('exam_length'))}",
    ]
    for list_key in ("exercise_types", "next_topics", "weak_topics"):
        values = context.get(list_key) or []
        if isinstance(values, list) and values:
            parts.append(f"{list_key.replace('_', ' ').title()}: " + ", ".join(_clean_text(item) for item in values if _clean_text(item)))
    return " ".join(part for part in parts if not part.endswith(": "))


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _current_validated_run_row() -> dict[str, Any]:
    try:
        rows = (
            get_sb()
            .table(RUN_TABLE)
            .select("run_id,run_status,overall_model_selection,human_review_recommended_model_name,is_current_validated_run,operational_use,human_reviewed_at,created_at")
            .eq("experiment_id", RESOURCE_AFFINITY_EXPERIMENT_ID)
            .order("human_reviewed_at", desc=True, nullsfirst=False)
            .order("created_at", desc=True)
            .limit(100)
            .execute()
        ).data or []
        if not rows:
            return {}
        runtime_rows = [
            row
            for row in rows
            if _clean_text(row.get("operational_use")) == "PRODUCTION_RUNTIME"
            and _clean_text(row.get("run_status")) in {"VALIDATED_EXPLORATORY_RUN", "VALIDATED_NO_ROBUST_WINNER", "SUPERSEDED"}
        ]
        if runtime_rows:
            return dict(runtime_rows[0])
        current_rows = [row for row in rows if bool(row.get("is_current_validated_run"))]
        if current_rows:
            return dict(current_rows[0])
        return {}
    except Exception:
        return {}


def _load_pickle(path: Path) -> Any:
    with path.open("rb") as handle:
        return pickle.load(handle)


def _model_family(value: Any) -> str:
    return _norm_key(value).split("_", 1)[0]


def _run_winner(summary: dict[str, Any], comparison: pd.DataFrame | None = None) -> str:
    evaluation = summary.get("evaluation") or {}
    winner = _clean_text(
        evaluation.get("winner")
        or evaluation.get("selected_candidate_for_human_review")
        or evaluation.get("balanced_candidate")
        or evaluation.get("primary_metric_leader")
        or ((evaluation.get("best_model") or {}).get("model_name") if isinstance(evaluation.get("best_model"), dict) else "")
    )
    if winner:
        return winner
    if comparison is not None and not comparison.empty and "model_name" in comparison.columns:
        return _clean_text(comparison.iloc[0].get("model_name"))
    return ""


def _artifact_candidate_score(summary_path: Path, summary: dict[str, Any], winner: str) -> tuple[int, float, float]:
    evaluation = summary.get("evaluation") or {}
    dataset = summary.get("dataset") or {}
    preferred = 1 if _model_family(winner) == PREFERRED_RUNTIME_MODEL_FAMILY else 0
    included_rows = _safe_float(dataset.get("included_row_count"), 0.0)
    freshness = float(summary_path.stat().st_mtime)
    selection_score = _safe_float((evaluation.get("best_model") or {}).get("selection_score"), -1.0) if isinstance(evaluation.get("best_model"), dict) else -1.0
    return (preferred, selection_score + included_rows / 1_000_000.0, freshness)


def _best_run_dir() -> Path | None:
    candidates: list[tuple[tuple[int, float, float], Path]] = []
    if not RUNS_ROOT.exists():
        return None
    for run_dir in RUNS_ROOT.iterdir():
        if not run_dir.is_dir():
            continue
        summary_path = run_dir / "resource_affinity_run_summary.json"
        comparison_path = run_dir / "resource_affinity_model_comparison.csv"
        frozen_path = run_dir / "resource_affinity_dataset_frozen.csv"
        cluster_path = run_dir / "resource_affinity_cluster_assignments.csv"
        representation_path = run_dir / REPRESENTATION_MANIFEST_FILENAME
        if not (summary_path.exists() and comparison_path.exists() and frozen_path.exists() and cluster_path.exists() and representation_path.exists()):
            continue
        summary = _read_json(summary_path)
        dataset = summary.get("dataset") or {}
        if _clean_text(dataset.get("feature_schema_version")) < MIN_FEATURE_SCHEMA_VERSION:
            continue
        try:
            comparison = pd.read_csv(comparison_path).fillna("")
        except Exception:
            comparison = pd.DataFrame()
        winner = _run_winner(summary, comparison)
        if _model_family(winner) != PREFERRED_RUNTIME_MODEL_FAMILY and not ALLOW_NON_KMEANS_RUNTIME_FALLBACK:
            continue
        candidates.append((_artifact_candidate_score(summary_path, summary, winner), run_dir))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


@lru_cache(maxsize=1)
def load_resource_affinity_index() -> dict[str, Any]:
    pinned_row = _current_validated_run_row()
    run_dir = RUNS_ROOT / _clean_text(pinned_row.get("run_id")) if _clean_text(pinned_row.get("run_id")) else None
    if run_dir and (not run_dir.exists() or not run_dir.is_dir()):
        run_dir = None
    if run_dir is None:
        run_dir = _best_run_dir()
    if not run_dir:
        return {"available": False, "reason": "no_validated_artifacts"}
    try:
        frozen = pd.read_csv(run_dir / "resource_affinity_dataset_frozen.csv").fillna("")
        clusters = pd.read_csv(run_dir / "resource_affinity_cluster_assignments.csv").fillna("")
        comparison = pd.read_csv(run_dir / "resource_affinity_model_comparison.csv").fillna("")
        representation = _read_json(run_dir / REPRESENTATION_MANIFEST_FILENAME)
    except Exception as exc:
        return {"available": False, "reason": f"artifact_read_failed:{exc}"}
    if frozen.empty or clusters.empty or "resource_key" not in frozen.columns:
        return {"available": False, "reason": "empty_index"}

    merged = frozen.merge(clusters[["resource_key", "cluster_id"]], on="resource_key", how="left")
    files = representation.get("files") or {}
    try:
        vectorizer = _load_pickle(Path(str(files.get("vectorizer") or "")))
        normalizer = _load_pickle(Path(str(files.get("normalizer") or "")))
        svd_path = _clean_text(files.get("svd"))
        svd = _load_pickle(Path(svd_path)) if svd_path else None
        with np.load(Path(str(files.get("vectors") or ""))) as vectors_payload:
            matrix = np.asarray(vectors_payload["vectors"], dtype=float).copy()
        ordered_keys = json.loads(Path(str(files.get("resource_keys") or "")).read_text(encoding="utf-8"))
    except Exception as exc:
        return {"available": False, "reason": f"fitted_representation_load_failed:{exc}"}
    merged_keys = merged["resource_key"].astype(str).tolist()
    if list(ordered_keys) != merged_keys:
        return {"available": False, "reason": "resource_order_mismatch"}
    if matrix.shape[0] != len(merged_keys):
        return {"available": False, "reason": "vector_row_count_mismatch"}
    summary = _read_json(run_dir / "resource_affinity_run_summary.json")
    best_row = {}
    pinned_model_name = _clean_text(pinned_row.get("human_review_recommended_model_name")) if pinned_row else ""
    if not comparison.empty:
        winner_name = pinned_model_name or _run_winner(summary, comparison)
        matches = comparison[comparison.get("model_name", pd.Series(dtype=str)).astype(str) == winner_name] if winner_name else pd.DataFrame()
        if not matches.empty:
            best_row = matches.iloc[0].to_dict()
        else:
            best_row = comparison.iloc[0].to_dict()
    return {
        "available": True,
        "run_id": run_dir.name,
        "run_dir": str(run_dir),
        "winner": _clean_text(best_row.get("model_name")),
        "model_family": _model_family(best_row.get("model_name")),
        "selection_source": "human_review_runtime_pin" if pinned_model_name else "artifact_winner_scan",
        "runtime_model_policy": f"preferred_family={PREFERRED_RUNTIME_MODEL_FAMILY}; fallback={'allowed' if ALLOW_NON_KMEANS_RUNTIME_FALLBACK else 'disabled'}",
        "silhouette_score": _safe_float(best_row.get("silhouette_score")),
        "selection_score": _safe_float(best_row.get("selection_score")),
        "cross_subject_contamination_rate": _safe_float(best_row.get("cross_subject_contamination_rate")),
        "cross_language_contamination_rate": _safe_float(best_row.get("cross_language_contamination_rate")),
        "resources": merged.to_dict("records"),
        "resource_key_to_index": {str(key): idx for idx, key in enumerate(merged["resource_key"].astype(str).tolist())},
        "vectorizer": vectorizer,
        "svd": svd,
        "normalizer": normalizer,
        "matrix": matrix,
        "representation_manifest": representation,
    }


def resource_affinity_score(row: dict[str, Any], kind: Any, context: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    index = load_resource_affinity_index()
    if not index.get("available"):
        return 0.0, {"available": False, "reason": index.get("reason") or "unavailable"}
    resource_key = resource_key_for(kind, _resource_id_from_row(row))
    row_idx = (index.get("resource_key_to_index") or {}).get(resource_key)
    if row_idx is None:
        return 0.0, {"available": True, "matched": False, "resource_key": resource_key, "run_id": index.get("run_id")}

    query_text = _profile_text_for_context(context, kind=kind)
    if not query_text.strip():
        query_text = _profile_text_for_candidate(row, kind)
    try:
        query_vec = index["vectorizer"].transform([query_text])
        if index.get("svd") is not None:
            query_vec = index["svd"].transform(query_vec)
        else:
            query_vec = query_vec.toarray()
        query_vec = index["normalizer"].transform(query_vec)
        matrix = np.asarray(index["matrix"], dtype=float)
        sims = np.dot(query_vec, matrix.T)[0]
    except Exception as exc:
        return 0.0, {"available": False, "reason": f"score_failed:{exc}", "resource_key": resource_key}

    candidate_similarity = _safe_float(sims[int(row_idx)])
    resources = index.get("resources") or []
    candidate = resources[int(row_idx)] if 0 <= int(row_idx) < len(resources) else {}
    candidate_cluster = _clean_text(candidate.get("cluster_id"))
    anchor_idx = int(sims.argmax()) if len(sims) else -1
    anchor_similarity = _safe_float(sims[anchor_idx]) if anchor_idx >= 0 else 0.0
    anchor = resources[anchor_idx] if 0 <= anchor_idx < len(resources) else {}
    anchor_cluster = _clean_text(anchor.get("cluster_id"))
    same_cluster = bool(
        candidate_cluster
        and anchor_cluster
        and candidate_cluster == anchor_cluster
        and candidate_cluster != "-1"
        and anchor_similarity >= MIN_QUERY_ANCHOR_SIMILARITY
    )
    noise_penalty = 0.12 if candidate_cluster == "-1" else 0.0
    cluster_bonus = 0.22 if same_cluster else 0.0
    score = _clamp((0.78 * candidate_similarity) + cluster_bonus - noise_penalty)
    diagnostics = {
        "available": True,
        "matched": True,
        "run_id": index.get("run_id"),
        "winner": index.get("winner"),
        "model_family": index.get("model_family"),
        "runtime_model_policy": index.get("runtime_model_policy"),
        "resource_key": resource_key,
        "candidate_similarity": round(candidate_similarity, 6),
        "candidate_cluster": candidate_cluster,
        "query_anchor_resource_key": _clean_text(anchor.get("resource_key")),
        "query_anchor_similarity": round(anchor_similarity, 6),
        "query_anchor_cluster": anchor_cluster,
        "same_cluster_as_query_anchor": same_cluster,
        "score": round(score, 6),
    }
    return score, diagnostics


def clear_resource_affinity_runtime_cache() -> None:
    load_resource_affinity_index.cache_clear()
