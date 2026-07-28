from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import pickle
import platform
import re
import sys
from typing import Any
import unicodedata
import uuid

import numpy as np
import pandas as pd

from helpers.assigned_resource_open_7d_eval import _fetch_all_rows, _json_safe
from helpers.archive_utils import is_archived_status


FEATURE_SCHEMA_VERSION = "resource_affinity_unsupervised.v5"
DEFAULT_SEED = 20260726
DEFAULT_OUTPUT_DIR = Path("reports") / "ml_architecture" / "resource_affinity_unsupervised"
FROZEN_DATASET_FILENAME = "resource_affinity_dataset_frozen.csv"
PROFILE_AUDIT_FILENAME = "resource_affinity_profile_audit.csv"
EXCLUSION_AUDIT_FILENAME = "resource_affinity_exclusion_audit.csv"
CATEGORY_NORMALIZATION_AUDIT_FILENAME = "resource_affinity_category_normalization_audit.csv"
FEATURE_AUDIT_FILENAME = "resource_affinity_feature_audit.csv"
MODEL_COMPARISON_FILENAME = "resource_affinity_model_comparison.csv"
CLUSTER_ASSIGNMENTS_FILENAME = "resource_affinity_cluster_assignments.csv"
NEIGHBORS_FILENAME = "resource_affinity_pairwise_neighbors.csv"
ANCHOR_RESOURCE_CANDIDATES_FILENAME = "resource_affinity_program_topic_resource_candidates.csv"
HUMAN_REVIEW_SAMPLE_FILENAME = "resource_affinity_human_review_sample.csv"
EXPERIMENT_CONFIG_FILENAME = "resource_affinity_experiment_config.json"
REPRESENTATION_MANIFEST_FILENAME = "resource_affinity_representation_manifest.json"
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
        "id,user_id,title,subject,topic,learner_stage,level_or_band,lesson_purpose,source_type,planner_mode,author_name,subject_display,is_public,status,created_at,updated_at,plan_json",
    ),
    "program": (
        "learning_programs",
        "id,user_id,title,subject,custom_subject_name,learner_stage,level_or_band,program_overview,is_public,status,total_units,total_topics,sequence_order,created_at,updated_at,program_data",
    ),
    "program_topic": (
        "learning_program_topics",
        "id,program_id,unit_number,topic_number,title,subtopic,lesson_focus,lesson_purpose,learning_objectives,success_criteria,student_can_do,suggested_worksheet_types,suggested_exam_exercise_types,homework_idea,teacher_notes,student_summary,estimated_lessons,created_at,updated_at",
    ),
}
RESOURCE_TABLE_FALLBACK_SPECS = {
    "worksheet": (
        "worksheets",
        "id,user_id,title,subject,topic,learner_stage,level_or_band,worksheet_type,source_type,student_material_language,plan_language,author_name,subject_display,is_public,status,created_at",
        "retry_without_worksheet_json_after_fetch_error",
    ),
    "exam": (
        "quick_exams",
        "id,user_id,title,subject,topic,learner_stage,level,exam_length,exercise_types,is_public,status,created_at",
        "retry_without_exam_data_after_fetch_error",
    ),
}
RESOURCE_CONTENT_EXCERPT_TABLE = "resource_affinity_content_excerpts"
RESOURCE_CONTENT_EXCERPT_COLUMNS = "resource_type,resource_id,content_excerpt,content_excerpt_source,content_excerpt_char_count"

MATERIAL_KINDS = {"worksheet", "exam", "video", "lesson_plan", "program", "program_topic"}
PROFILE_COLUMNS = [
    "resource_key",
    "resource_type",
    "resource_role",
    "resource_id",
    "title",
    "subject",
    "language",
    "level",
    "learner_stage",
    "topic",
    "topics_extracted",
    "content_excerpt",
    "content_excerpt_source",
    "subtype",
    "is_public",
    "status",
    "created_at",
    "updated_at",
    "profile_text",
    "profile_hash",
    "profile_token_count",
    "subject_normalized",
    "language_normalized",
    "level_normalized",
    "resource_type_normalized",
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
    "min_cluster_size",
    "max_cluster_size",
    "mean_cluster_size",
    "median_cluster_size",
    "cluster_size_2_rate",
    "cluster_size_le_3_rate",
    "assigned_resource_coverage",
    "contaminated_subject_clusters",
    "evaluated_subject_clusters",
    "contaminated_language_clusters",
    "evaluated_language_clusters",
    "cross_subject_contamination_rate",
    "cross_language_contamination_rate",
    "selection_score",
    "train_duration_ms",
    "inference_duration_ms",
    "failure_reason",
]
NEIGHBOR_COLUMNS = [
    "source_resource_key",
    "source_resource_type",
    "source_resource_role",
    "source_title",
    "target_resource_key",
    "target_resource_type",
    "target_resource_role",
    "target_title",
    "similarity_score",
    "same_subject",
    "same_language",
    "same_level",
    "source_cluster_id",
    "target_cluster_id",
    "same_cluster",
    "reciprocal",
]
CLUSTER_COLUMNS = ["resource_key", "resource_type", "resource_role", "resource_id", "title", "subject", "language", "level", "topic", "cluster_id"]
REPRESENTATION_FILES = {
    "vectorizer": "resource_affinity_vectorizer.pkl",
    "svd": "resource_affinity_svd.pkl",
    "normalizer": "resource_affinity_normalizer.pkl",
    "vectors": "resource_affinity_vectors.npz",
    "resource_keys": "resource_affinity_ordered_resource_keys.json",
}
DEFAULT_NEIGHBOR_TOP_K = 5
DEFAULT_ANCHOR_CANDIDATE_TOP_K = 8
DEFAULT_CONFIDENCE_THRESHOLDS = (0.60, 0.70, 0.72, 0.80, 0.90)
CANONICAL_ALIASES = {
    "subject": {
        "espanol": "spanish",
        "español": "spanish",
        "spanish language": "spanish",
        "english language": "english",
        "math": "mathematics",
        "maths": "mathematics",
    },
    "language": {
        "english": "en",
        "eng": "en",
        "spanish": "es",
        "espanol": "es",
        "español": "es",
        "turkish": "tr",
        "turkce": "tr",
        "türkçe": "tr",
    },
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    return (value or _utc_now()).astimezone(timezone.utc).isoformat()


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _norm_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().casefold()).strip("_")


def _canonical_value(value: Any, field: str = "") -> str:
    text = unicodedata.normalize("NFKC", _clean_text(value)).replace("–", "-").replace("—", "-")
    text = re.sub(r"[/|]+", " ", text).casefold()
    text = re.sub(r"\s+", " ", text).strip()
    aliases = CANONICAL_ALIASES.get(field) or {}
    if text in aliases:
        return aliases[text]
    ascii_key = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return aliases.get(ascii_key, text)


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


CONTENT_EXCLUDE_KEY_TOKENS = (
    "answer",
    "answer_key",
    "correct",
    "solution",
    "explanation",
    "image",
    "image_url",
    "image_base64",
    "base64",
    "svg",
    "audio",
    "video",
    "file",
    "url",
)
CONTENT_INCLUDE_KEY_TOKENS = (
    "instruction",
    "prompt",
    "question",
    "stem",
    "option",
    "choice",
    "passage",
    "reading",
    "text",
    "sentence",
    "paragraph",
    "word",
    "vocabulary",
    "dialogue",
    "task",
    "activity",
)
CONTENT_FRAGMENT_CHAR_LIMIT = 160
CONTENT_MAX_FRAGMENTS = 12
CONTENT_TOTAL_CHAR_LIMIT = 1400


def _looks_like_large_media(text: str) -> bool:
    safe = _clean_text(text)
    return len(safe) > 600 and bool(re.search(r"(data:image|base64|<svg|iVBORw0KGgo|/9j/|https?://)", safe, re.IGNORECASE))


def _sanitize_content_excerpt(value: Any, *, max_fragments: int = CONTENT_MAX_FRAGMENTS, fragment_limit: int = CONTENT_FRAGMENT_CHAR_LIMIT, total_limit: int = CONTENT_TOTAL_CHAR_LIMIT) -> str:
    payload = _parse_jsonish(value)
    fragments: list[str] = []

    def should_skip_key(key: str) -> bool:
        normalized = _norm_key(key)
        return any(token in normalized for token in CONTENT_EXCLUDE_KEY_TOKENS)

    def should_prefer_key(key: str) -> bool:
        normalized = _norm_key(key)
        return any(token in normalized for token in CONTENT_INCLUDE_KEY_TOKENS)

    def add(text: Any) -> None:
        if len(fragments) >= max_fragments:
            return
        cleaned = _clean_text(text)
        if not cleaned or _looks_like_large_media(cleaned):
            return
        fragments.append(cleaned[:fragment_limit])

    def walk(item: Any, key_hint: str = "", depth: int = 0) -> None:
        if len(fragments) >= max_fragments or depth > 8:
            return
        if should_skip_key(key_hint):
            return
        if isinstance(item, dict):
            for key, child in item.items():
                key_text = _clean_text(key)
                if should_skip_key(key_text):
                    continue
                if should_prefer_key(key_text) and isinstance(child, (str, int, float)):
                    add(child)
                elif should_prefer_key(key_text) and isinstance(child, list):
                    for entry in child[:6]:
                        if isinstance(entry, (str, int, float)):
                            add(entry)
                walk(child, key_text, depth + 1)
        elif isinstance(item, list):
            for child in item[:30]:
                walk(child, key_hint, depth + 1)
        elif should_prefer_key(key_hint):
            add(item)

    walk(payload)
    deduped: list[str] = []
    seen: set[str] = set()
    total = 0
    for fragment in fragments:
        key = _canonical_value(fragment)
        if not key or key in seen:
            continue
        seen.add(key)
        if total + len(fragment) > total_limit:
            remaining = max(0, total_limit - total)
            if remaining >= 40:
                deduped.append(fragment[:remaining])
            break
        deduped.append(fragment)
        total += len(fragment)
    return " ".join(deduped)


def _extract_lesson_plan_topics(value: Any, fallback_topic: str = "") -> list[str]:
    payload = _parse_jsonish(value)
    candidates: list[str] = []
    if fallback_topic:
        candidates.append(fallback_topic)

    def add(value: Any) -> None:
        text = _clean_text(value)
        if text and len(text) <= 160:
            candidates.append(text)

    def walk(item: Any, key_hint: str = "") -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                key_text = _clean_text(key).casefold()
                if any(token in key_text for token in ("topic", "title", "objective", "focus", "vocabulary", "success", "assessment")):
                    if isinstance(child, (str, int, float)):
                        add(child)
                    elif isinstance(child, list):
                        for entry in child[:8]:
                            if isinstance(entry, (str, int, float)):
                                add(entry)
                walk(child, key_text)
        elif isinstance(item, list):
            for child in item[:40]:
                walk(child, key_hint)

    walk(payload)
    deduped: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        key = _canonical_value(item)
        if key and key not in seen:
            seen.add(key)
            deduped.append(_clean_text(item))
    return deduped[:12]


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
    resource_role = "curricular_anchor" if resource_type == "program_topic" else "candidate_resource"
    subject = _field(row, "subject", "subject_key", "custom_subject_name")
    level = _field(row, "level_or_band", "level")
    stage = _field(row, "learner_stage")
    topic = _field(row, "topic")
    title = _field(row, "title")
    subtype = _field(row, "worksheet_type", "exam_length", "lesson_purpose", "planner_mode", "source_type")
    if resource_type == "program_topic":
        subtype = _clean_text("program_topic " + subtype).strip()
    language = _resource_language(row)
    lesson_topics = _extract_lesson_plan_topics(row.get("plan_json"), topic) if resource_type == "lesson_plan" else []
    content_excerpt = _clean_text(row.get("content_excerpt"))
    content_excerpt_source = _clean_text(row.get("content_excerpt_source"))
    if not content_excerpt and resource_type == "worksheet" and row.get("worksheet_json") not in (None, ""):
        content_excerpt = _sanitize_content_excerpt(row.get("worksheet_json"))
        content_excerpt_source = "local_sanitized_worksheet_json"
    if not content_excerpt and resource_type == "exam" and row.get("exam_data") not in (None, ""):
        content_excerpt = _sanitize_content_excerpt(row.get("exam_data"))
        content_excerpt_source = "local_sanitized_exam_data"
    detail_fields = [
        "description",
        "program_overview",
        "plan_json",
        "program_data",
        "lesson_plan_json",
        "content_json",
        "exercise_types",
        "learning_objectives",
        "success_criteria",
        "student_can_do",
        "suggested_worksheet_types",
        "suggested_exam_exercise_types",
        "homework_idea",
        "teacher_notes",
        "student_summary",
    ]
    detail_text = " ".join(_flatten_json_text(row.get(name)) for name in detail_fields if row.get(name) not in (None, ""))
    extracted_topic_text = "; ".join(lesson_topics)
    profile_text = _clean_text(
        " ".join(
            [
                f"Resource type: {resource_type}",
                f"Profile role: {resource_role}",
                f"Title: {title}",
                f"Subject: {subject}",
                f"Language: {language}",
                f"Level: {level}",
                f"Learner stage: {stage}",
                f"Topic: {topic}",
                f"Extracted topics: {extracted_topic_text}",
                f"Subtype: {subtype}",
                f"Content excerpt: {content_excerpt}",
                detail_text,
            ]
        )
    )
    return {
        "resource_key": f"{resource_type}:{rid}",
        "resource_type": resource_type,
        "resource_role": resource_role,
        "resource_id": rid,
        "title": title,
        "subject": subject,
        "language": language,
        "level": level,
        "learner_stage": stage,
        "topic": topic,
        "topics_extracted": extracted_topic_text,
        "content_excerpt": content_excerpt,
        "content_excerpt_source": content_excerpt_source,
        "subtype": subtype,
        "is_public": bool(row.get("is_public")),
        "status": _clean_text(row.get("status")),
        "created_at": _clean_text(row.get("created_at")),
        "updated_at": _clean_text(row.get("updated_at")),
        "profile_text": profile_text,
        "profile_hash": _hash_text(profile_text),
        "profile_token_count": len(re.findall(r"\w+", profile_text)),
        "subject_normalized": _canonical_value(subject, "subject"),
        "language_normalized": _canonical_value(language, "language"),
        "level_normalized": _canonical_value(level, "level"),
        "resource_type_normalized": _canonical_value(resource_type, "resource_type"),
    }


def _exclusion_row(row: dict[str, Any], resource_type: str, table_name: str, reason: str, extraction_time: datetime | None) -> dict[str, Any]:
    try:
        profile = build_resource_profile(row, resource_type)
    except Exception:
        profile = {}
    return {
        "resource_type": resource_type,
        "source_table": table_name,
        "resource_id": _clean_text(row.get("id")),
        "title": _field(row, "title"),
        "status": _clean_text(row.get("status")),
        "resource_key": _clean_text(profile.get("resource_key")),
        "profile_hash": _clean_text(profile.get("profile_hash")),
        "profile_token_count": _safe_int(profile.get("profile_token_count")),
        "exclusion_reason": reason,
        "extraction_timestamp": _iso(extraction_time),
    }


def _category_normalization_audit(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for field in ("subject", "language", "level", "resource_type", "resource_role"):
        norm_col = f"{field}_normalized" if field != "resource_role" else "resource_role"
        if field not in df.columns or norm_col not in df.columns:
            continue
        if field == norm_col:
            counts = df.groupby(field, dropna=False).size().reset_index(name="occurrence_count")
            counts[norm_col] = counts[field]
        else:
            counts = df.groupby([field, norm_col], dropna=False).size().reset_index(name="occurrence_count")
        for _, row in counts.iterrows():
            rows.append(
                {
                    "field": field,
                    "original_value": _clean_text(row.get(field)),
                    "normalized_value": _clean_text(row.get(norm_col)),
                    "occurrence_count": int(row.get("occurrence_count") or 0),
                }
            )
    return pd.DataFrame(rows, columns=["field", "original_value", "normalized_value", "occurrence_count"])


def _completeness_summary(df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    fields = {
        "resource_id": "resource_id",
        "title": "title",
        "resource_role": "resource_role",
        "subject": "subject",
        "language": "language",
        "level": "level",
        "learner_stage": "learner_stage",
        "topic": "topic",
        "lesson_plan_extracted_topics": "topics_extracted",
        "content_excerpt": "content_excerpt",
        "subtype": "subtype",
        "profile_text": "profile_text",
    }
    total = int(len(df))
    summary: dict[str, dict[str, Any]] = {}
    for label, column in fields.items():
        known = int(df[column].replace("", pd.NA).dropna().shape[0]) if column in df.columns and total else 0
        summary[label] = {
            "known_count": known,
            "missing_count": max(0, total - known),
            "known_pct": round(known / max(1, total), 4),
        }
    return summary


def _fetch_content_excerpt_map(warnings: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    try:
        rows = _fetch_all_rows(RESOURCE_CONTENT_EXCERPT_TABLE, RESOURCE_CONTENT_EXCERPT_COLUMNS, page_size=250)
    except Exception as exc:
        warnings.append(
            {
                "resource_type": "worksheet_exam",
                "table_name": RESOURCE_CONTENT_EXCERPT_TABLE,
                "warning": "content_excerpt_view_unavailable_metadata_only",
                "primary_error": str(exc),
            }
        )
        return {}
    excerpt_map: dict[str, dict[str, Any]] = {}
    for row in rows:
        resource_type = _clean_text(row.get("resource_type"))
        resource_id = _clean_text(row.get("resource_id"))
        excerpt = _clean_text(row.get("content_excerpt"))
        if resource_type and resource_id and excerpt:
            excerpt_map[f"{resource_type}:{resource_id}"] = {
                "content_excerpt": excerpt[:CONTENT_TOTAL_CHAR_LIMIT],
                "content_excerpt_source": _clean_text(row.get("content_excerpt_source")) or RESOURCE_CONTENT_EXCERPT_TABLE,
            }
    warnings.append(
        {
            "resource_type": "worksheet_exam",
            "table_name": RESOURCE_CONTENT_EXCERPT_TABLE,
            "warning": "content_excerpt_view_loaded",
            "primary_error": "",
        }
    )
    return excerpt_map


def extract_resource_profiles(extraction_time: datetime | None = None) -> tuple[pd.DataFrame, dict[str, Any], pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    exclusions: list[dict[str, Any]] = []
    raw_counts: dict[str, int] = {}
    program_meta_by_id: dict[str, dict[str, Any]] = {}
    content_excerpt_map = _fetch_content_excerpt_map(warnings)
    for resource_type, (table_name, columns) in RESOURCE_TABLE_SPECS.items():
        try:
            table_rows = _fetch_all_rows(table_name, columns, page_size=500)
        except Exception as exc:
            fallback = RESOURCE_TABLE_FALLBACK_SPECS.get(resource_type)
            if fallback:
                fallback_table, fallback_columns, fallback_reason = fallback
                try:
                    table_rows = _fetch_all_rows(fallback_table, fallback_columns, page_size=200)
                    warnings.append(
                        {
                            "resource_type": resource_type,
                            "table_name": table_name,
                            "warning": fallback_reason,
                            "primary_error": str(exc),
                        }
                    )
                except Exception as fallback_exc:
                    errors.append({"resource_type": resource_type, "table_name": table_name, "error": str(exc), "fallback_error": str(fallback_exc)})
                    table_rows = []
            else:
                errors.append({"resource_type": resource_type, "table_name": table_name, "error": str(exc)})
                table_rows = []
        raw_counts[resource_type] = len(table_rows)
        for row in table_rows:
            if is_archived_status(row.get("status")):
                exclusions.append(_exclusion_row(row, resource_type, table_name, "archived_status", extraction_time))
                continue
            if resource_type == "program":
                program_meta_by_id[_clean_text(row.get("id"))] = {
                    "subject": _field(row, "subject", "custom_subject_name"),
                    "learner_stage": _field(row, "learner_stage"),
                    "level_or_band": _field(row, "level_or_band", "level"),
                    "language": _resource_language(row),
                    "program_title": _field(row, "title"),
                }
            elif resource_type == "program_topic":
                parent = program_meta_by_id.get(_clean_text(row.get("program_id"))) or {}
                row = {
                    **parent,
                    **row,
                    "topic": _field(row, "title", "subtopic", "lesson_focus"),
                    "title": _field(row, "title", "lesson_focus", "subtopic"),
                }
            if resource_type in {"worksheet", "exam"}:
                row = {**row, **(content_excerpt_map.get(f"{resource_type}:{_clean_text(row.get('id'))}") or {})}
            try:
                profile = build_resource_profile(row, resource_type)
            except Exception as exc:
                exclusions.append(_exclusion_row(row, resource_type, table_name, f"extraction_error:{exc}", extraction_time))
                continue
            if not profile["resource_id"]:
                exclusions.append(_exclusion_row(row, resource_type, table_name, "missing_or_invalid_resource_id", extraction_time))
                continue
            if profile["profile_token_count"] < 3:
                exclusions.append(_exclusion_row(row, resource_type, table_name, "profile_below_minimum_token_count", extraction_time))
                continue
            rows.append(profile)
    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=PROFILE_COLUMNS)
    if not df.empty:
        duplicate_mask = df.duplicated(subset=["resource_key", "profile_hash"], keep="first")
        for _, duplicate in df[duplicate_mask].iterrows():
            exclusions.append(
                {
                    "resource_type": _clean_text(duplicate.get("resource_type")),
                    "source_table": RESOURCE_TABLE_SPECS.get(_clean_text(duplicate.get("resource_type")), ("", ""))[0],
                    "resource_id": _clean_text(duplicate.get("resource_id")),
                    "title": _clean_text(duplicate.get("title")),
                    "status": _clean_text(duplicate.get("status")),
                    "resource_key": _clean_text(duplicate.get("resource_key")),
                    "profile_hash": _clean_text(duplicate.get("profile_hash")),
                    "profile_token_count": _safe_int(duplicate.get("profile_token_count")),
                    "exclusion_reason": "duplicate_resource_key_profile_hash",
                    "extraction_timestamp": _iso(extraction_time),
                }
            )
        df = df[~duplicate_mask].reset_index(drop=True)
    exclusion_df = pd.DataFrame(
        exclusions,
        columns=[
            "resource_type",
            "source_table",
            "resource_id",
            "title",
            "status",
            "resource_key",
            "profile_hash",
            "profile_token_count",
            "exclusion_reason",
            "extraction_timestamp",
        ],
    )
    normalization_audit = _category_normalization_audit(df)
    excluded_count = int(len(exclusion_df))
    source_count = int(sum(raw_counts.values()))
    included_count = int(len(df))
    if source_count != included_count + excluded_count:
        errors.append(
            {
                "resource_type": "all",
                "table_name": "resource_catalog",
                "error": f"accounting_mismatch source={source_count} included={included_count} excluded={excluded_count}",
            }
        )
    diagnostics = {
        "extracted_at": _iso(extraction_time),
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "experiment_target": "learning_program_topic_to_candidate_resource_alignment",
        "program_topic_role": "curricular_anchor",
        "candidate_resource_types": ["worksheet", "exam", "video", "lesson_plan", "program"],
        "source_row_count": source_count,
        "included_row_count": included_count,
        "excluded_row_count": excluded_count,
        "resource_count": int(df[df["resource_role"] == "candidate_resource"]["resource_key"].nunique()) if not df.empty else 0,
        "curricular_anchor_count": int((df["resource_role"] == "curricular_anchor").sum()) if not df.empty else 0,
        "candidate_resource_count": int((df["resource_role"] == "candidate_resource").sum()) if not df.empty else 0,
        "raw_counts_by_type": raw_counts,
        "included_counts_by_type": df["resource_type"].value_counts().to_dict() if not df.empty else {},
        "included_counts_by_role": df["resource_role"].value_counts().to_dict() if not df.empty else {},
        "excluded_counts_by_reason": exclusion_df["exclusion_reason"].value_counts().to_dict() if not exclusion_df.empty else {},
        "excluded_counts_by_type": exclusion_df["resource_type"].value_counts().to_dict() if not exclusion_df.empty else {},
        "subject_count": int(df["subject_normalized"].replace("", pd.NA).nunique()) if not df.empty else 0,
        "language_count": int(df["language_normalized"].replace("", pd.NA).nunique()) if not df.empty else 0,
        "level_count": int(df["level_normalized"].replace("", pd.NA).nunique()) if not df.empty else 0,
        "raw_subject_count": int(df["subject"].replace("", pd.NA).nunique()) if not df.empty else 0,
        "raw_language_count": int(df["language"].replace("", pd.NA).nunique()) if not df.empty else 0,
        "raw_level_count": int(df["level"].replace("", pd.NA).nunique()) if not df.empty else 0,
        "completeness": _completeness_summary(df),
        "errors": errors,
        "warnings": warnings,
        "data_fingerprint": _hash_text("|".join(sorted(df["profile_hash"].tolist())) if not df.empty else "empty", 24),
    }
    return df, diagnostics, exclusion_df, normalization_audit


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


def _experiment_config(n_rows: int) -> dict[str, Any]:
    k_values = sorted({2, 3, 4, 5, 8, 12, max(2, min(16, int(round(math.sqrt(max(1, n_rows)))))), max(2, min(24, int(round(n_rows / 12))))})
    k_values = [k for k in k_values if 1 < k < n_rows]
    return {
        "configuration_schema_version": "resource_affinity_config.v1",
        "random_seed": DEFAULT_SEED,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "analysis_unit": {
            "target": "learning_program_topic",
            "curricular_anchor_resource_type": "program_topic",
            "candidate_resource_types": ["worksheet", "exam", "video", "lesson_plan", "program"],
            "objective": "Measure whether candidate resources align semantically with learning-program topic anchors before existing Classio heuristics filter final recommendations.",
        },
        "profile_schema": PROFILE_COLUMNS,
        "text_processing": {
            "lowercase": True,
            "strip_accents": "unicode",
            "ngram_range": [1, 2],
            "min_df": 1,
            "max_df": 0.92,
            "max_features": 1600,
        },
        "svd": {"enabled_when_min_tfidf_shape_gt": 3, "max_components": 64},
        "normalization": {"vector_l2_normalization": True, "category_unicode_nfkc_casefold": True},
        "clustering_grid": {
            "kmeans_k": k_values,
            "agglomerative_k": k_values,
            "dbscan_eps": [0.28, 0.32, 0.36, 0.40, 0.42, 0.46, 0.52, 0.58, 0.62],
            "dbscan_min_samples": [2, 3, 4],
            "distance_metric": "cosine",
            "agglomerative_linkage": "average",
        },
        "model_selection": {
            "metric_leader": "highest silhouette among successful rows",
            "balanced_candidate": "highest balanced selection score after fragmentation, noise, and contamination penalties",
            "not_exhaustive": True,
        },
        "neighbors": {"top_k": DEFAULT_NEIGHBOR_TOP_K, "thresholds": list(DEFAULT_CONFIDENCE_THRESHOLDS), "directed": True},
        "anchor_resource_alignment": {
            "top_k": DEFAULT_ANCHOR_CANDIDATE_TOP_K,
            "source_role": "curricular_anchor",
            "target_role": "candidate_resource",
            "human_review_basis": True,
        },
        "minimum_dataset_checks": {"minimum_resources": 6},
        "report_schema_version": "resource_affinity_report.v2",
    }


def _config_hash(config: dict[str, Any]) -> str:
    return _hash_text(json.dumps(config, sort_keys=True), 24)


def _build_vectors(profile_df: pd.DataFrame) -> tuple[np.ndarray, dict[str, Any], dict[str, Any]]:
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
        normalizer = sk["Normalizer"](copy=False)
        vectors = normalizer.fit_transform(vectors)
        explained = float(np.sum(getattr(svd, "explained_variance_ratio_", np.array([]))))
        method = "tfidf_truncated_svd"
    else:
        svd = None
        vectors = tfidf.toarray()
        normalizer = sk["Normalizer"](copy=False)
        vectors = normalizer.fit_transform(vectors)
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
    artifacts = {"vectorizer": vectorizer, "svd": svd, "normalizer": normalizer}
    return np.asarray(vectors, dtype=float), manifest, artifacts


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
        "min_cluster_size": 0,
        "max_cluster_size": 0,
        "mean_cluster_size": 0.0,
        "median_cluster_size": 0.0,
        "cluster_size_2_rate": 0.0,
        "cluster_size_le_3_rate": 0.0,
        "assigned_resource_coverage": round(float(np.sum(labels >= 0)) / max(1, len(labels)), 4),
        "contaminated_subject_clusters": 0,
        "evaluated_subject_clusters": 0,
        "contaminated_language_clusters": 0,
        "evaluated_language_clusters": 0,
        "cross_subject_contamination_rate": None,
        "cross_language_contamination_rate": None,
        "silhouette_score": None,
        "calinski_harabasz": None,
        "davies_bouldin": None,
    }
    if cluster_count >= 1:
        counts = pd.Series(labels[labels >= 0]).value_counts()
        metrics["singleton_cluster_count"] = int((counts == 1).sum())
        metrics["min_cluster_size"] = int(counts.min())
        metrics["max_cluster_size"] = int(counts.max())
        metrics["mean_cluster_size"] = round(float(counts.mean()), 4)
        metrics["median_cluster_size"] = round(float(counts.median()), 4)
        metrics["cluster_size_2_rate"] = round(float((counts == 2).sum()) / max(1, len(counts)), 4)
        metrics["cluster_size_le_3_rate"] = round(float((counts <= 3).sum()) / max(1, len(counts)), 4)
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
        known_subjects = group["subject_normalized"].replace("", pd.NA).dropna()
        known_languages = group["language_normalized"].replace("", pd.NA).dropna()
        if not known_subjects.empty:
            contamination_subject.append(1.0 if known_subjects.nunique() > 1 else 0.0)
        if not known_languages.empty:
            contamination_language.append(1.0 if known_languages.nunique() > 1 else 0.0)
    if contamination_subject:
        metrics["contaminated_subject_clusters"] = int(sum(contamination_subject))
        metrics["evaluated_subject_clusters"] = int(len(contamination_subject))
        metrics["cross_subject_contamination_rate"] = round(sum(contamination_subject) / len(contamination_subject), 4)
    if contamination_language:
        metrics["contaminated_language_clusters"] = int(sum(contamination_language))
        metrics["evaluated_language_clusters"] = int(len(contamination_language))
        metrics["cross_language_contamination_rate"] = round(sum(contamination_language) / len(contamination_language), 4)
    return metrics


def _candidate_models(n_rows: int) -> list[tuple[str, dict[str, Any]]]:
    if n_rows < 3:
        return []
    config = _experiment_config(n_rows)
    grid = config["clustering_grid"]
    candidates: list[tuple[str, dict[str, Any]]] = []
    for k in grid["kmeans_k"]:
        candidates.append(("KMeans", {"n_clusters": k}))
    for k in grid["agglomerative_k"]:
        candidates.append(("AgglomerativeClustering", {"n_clusters": k}))
    for eps in grid["dbscan_eps"]:
        for min_samples in grid["dbscan_min_samples"]:
            candidates.append(("DBSCAN", {"eps": eps, "min_samples": min_samples, "metric": "cosine"}))
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
                "min_cluster_size": quality.get("min_cluster_size"),
                "max_cluster_size": quality.get("max_cluster_size"),
                "mean_cluster_size": quality.get("mean_cluster_size"),
                "median_cluster_size": quality.get("median_cluster_size"),
                "cluster_size_2_rate": quality.get("cluster_size_2_rate"),
                "cluster_size_le_3_rate": quality.get("cluster_size_le_3_rate"),
                "assigned_resource_coverage": quality.get("assigned_resource_coverage"),
                "contaminated_subject_clusters": quality.get("contaminated_subject_clusters"),
                "evaluated_subject_clusters": quality.get("evaluated_subject_clusters"),
                "contaminated_language_clusters": quality.get("contaminated_language_clusters"),
                "evaluated_language_clusters": quality.get("evaluated_language_clusters"),
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
        comparison["_selection_score"] = (
            comparison["silhouette_score"].fillna(-1)
            - comparison["cross_subject_contamination_rate"].fillna(1) * 0.35
            - comparison["noise_ratio"].fillna(1) * 0.20
            - comparison["cluster_size_2_rate"].fillna(1) * 0.12
            - comparison["cluster_size_le_3_rate"].fillna(1) * 0.08
        )
        comparison["selection_score"] = comparison["_selection_score"].round(6)
        comparison = comparison.sort_values(["_selection_score", "_rank_silhouette", "_rank_contamination"], ascending=[False, False, True])
        comparison = comparison.drop(columns=["_selection_score", "_rank_silhouette", "_rank_contamination"])
    return comparison.reset_index(drop=True), labels_by_model


def _top_neighbors(profile_df: pd.DataFrame, vectors: np.ndarray, labels: np.ndarray | None = None, *, top_k: int = DEFAULT_NEIGHBOR_TOP_K) -> pd.DataFrame:
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
            source_cluster = int(labels[i]) if labels is not None and len(labels) > i else None
            target_cluster = int(labels[int(j)]) if labels is not None and len(labels) > int(j) else None
            rows.append(
                {
                    "source_resource_key": source["resource_key"],
                    "source_resource_type": source["resource_type"],
                    "source_resource_role": source.get("resource_role", ""),
                    "source_title": source["title"],
                    "target_resource_key": target["resource_key"],
                    "target_resource_type": target["resource_type"],
                    "target_resource_role": target.get("resource_role", ""),
                    "target_title": target["title"],
                    "similarity_score": round(score, 6),
                    "same_subject": _clean_text(source.get("subject_normalized")) == _clean_text(target.get("subject_normalized")),
                    "same_language": _clean_text(source.get("language_normalized")) == _clean_text(target.get("language_normalized")) if source.get("language_normalized") and target.get("language_normalized") else None,
                    "same_level": _clean_text(source.get("level_normalized")) == _clean_text(target.get("level_normalized")) if source.get("level_normalized") and target.get("level_normalized") else None,
                    "source_cluster_id": source_cluster,
                    "target_cluster_id": target_cluster,
                    "same_cluster": source_cluster is not None and target_cluster is not None and source_cluster == target_cluster and source_cluster >= 0,
                    "reciprocal": False,
                }
            )
            emitted += 1
            if emitted >= top_k:
                break
    frame = pd.DataFrame(rows)
    if not frame.empty:
        edges = set(zip(frame["source_resource_key"], frame["target_resource_key"]))
        frame["reciprocal"] = [(target, source) in edges for source, target in zip(frame["source_resource_key"], frame["target_resource_key"])]
    return frame


def _anchor_resource_candidates(profile_df: pd.DataFrame, vectors: np.ndarray, labels: np.ndarray | None = None, *, top_k: int = DEFAULT_ANCHOR_CANDIDATE_TOP_K) -> pd.DataFrame:
    if profile_df.empty or len(profile_df) < 2:
        return pd.DataFrame(columns=NEIGHBOR_COLUMNS)
    sk = _sklearn_imports()
    sim = sk["cosine_similarity"](vectors)
    records = profile_df.to_dict("records")
    anchor_indexes = [idx for idx, row in enumerate(records) if row.get("resource_role") == "curricular_anchor"]
    candidate_indexes = [idx for idx, row in enumerate(records) if row.get("resource_role") == "candidate_resource"]
    rows: list[dict[str, Any]] = []
    for i in anchor_indexes:
        source = records[i]
        ordered_candidates = sorted(candidate_indexes, key=lambda j: float(sim[i, j]), reverse=True)
        for j in ordered_candidates[:top_k]:
            target = records[j]
            source_cluster = int(labels[i]) if labels is not None and len(labels) > i else None
            target_cluster = int(labels[j]) if labels is not None and len(labels) > j else None
            rows.append(
                {
                    "source_resource_key": source["resource_key"],
                    "source_resource_type": source["resource_type"],
                    "source_resource_role": source.get("resource_role", ""),
                    "source_title": source["title"],
                    "target_resource_key": target["resource_key"],
                    "target_resource_type": target["resource_type"],
                    "target_resource_role": target.get("resource_role", ""),
                    "target_title": target["title"],
                    "similarity_score": round(float(sim[i, j]), 6),
                    "same_subject": _clean_text(source.get("subject_normalized")) == _clean_text(target.get("subject_normalized")),
                    "same_language": _clean_text(source.get("language_normalized")) == _clean_text(target.get("language_normalized")) if source.get("language_normalized") and target.get("language_normalized") else None,
                    "same_level": _clean_text(source.get("level_normalized")) == _clean_text(target.get("level_normalized")) if source.get("level_normalized") and target.get("level_normalized") else None,
                    "source_cluster_id": source_cluster,
                    "target_cluster_id": target_cluster,
                    "same_cluster": source_cluster is not None and target_cluster is not None and source_cluster == target_cluster and source_cluster >= 0,
                    "reciprocal": False,
                }
            )
    frame = pd.DataFrame(rows, columns=NEIGHBOR_COLUMNS)
    if not frame.empty:
        edges = set(zip(frame["source_resource_key"], frame["target_resource_key"]))
        frame["reciprocal"] = [(target, source) in edges for source, target in zip(frame["source_resource_key"], frame["target_resource_key"])]
    return frame


def _neighbor_summary(neighbors: pd.DataFrame, *, top_k: int = DEFAULT_NEIGHBOR_TOP_K) -> dict[str, Any]:
    if neighbors.empty:
        return {"top_k": top_k, "directed_edge_count": 0, "thresholds": {}}
    directed = int(len(neighbors))
    pairs = {tuple(sorted((str(row.source_resource_key), str(row.target_resource_key)))) for row in neighbors.itertuples()}
    reciprocal = int(neighbors["reciprocal"].fillna(False).astype(bool).sum())
    sims = neighbors["similarity_score"].astype(float)
    thresholds = {
        str(threshold): int((sims >= threshold).sum())
        for threshold in DEFAULT_CONFIDENCE_THRESHOLDS
    }
    known_language = neighbors["same_language"].dropna()
    known_level = neighbors["same_level"].dropna()
    return {
        "top_k": top_k,
        "directed_edge_count": directed,
        "unique_undirected_pair_count": int(len(pairs)),
        "reciprocal_edge_count": reciprocal,
        "reciprocal_edge_rate": round(reciprocal / max(1, directed), 4),
        "mean_similarity": round(float(sims.mean()), 6),
        "median_similarity": round(float(sims.median()), 6),
        "min_similarity": round(float(sims.min()), 6),
        "max_similarity": round(float(sims.max()), 6),
        "same_subject_rate": round(float(neighbors["same_subject"].fillna(False).astype(bool).mean()), 4),
        "same_language_rate_known": round(float(known_language.astype(bool).mean()), 4) if not known_language.empty else None,
        "same_level_rate_known": round(float(known_level.astype(bool).mean()), 4) if not known_level.empty else None,
        "noise_source_edges": int((neighbors["source_cluster_id"].astype(str) == "-1").sum()) if "source_cluster_id" in neighbors else 0,
        "noise_target_edges": int((neighbors["target_cluster_id"].astype(str) == "-1").sum()) if "target_cluster_id" in neighbors else 0,
        "thresholds": thresholds,
    }


def _normalization_methodology() -> dict[str, Any]:
    return {
        "text_cleaning": [
            "All text fields are converted to strings, collapsed to single spaces, and stripped of leading/trailing whitespace.",
            "Unicode text is normalized with NFKC for category comparison.",
            "Dash variants are normalized before category comparison.",
        ],
        "category_normalization": [
            "subject, language, level, resource_type, and resource_role are audited.",
            "Category values are case-folded.",
            "Slash and pipe separators are converted to spaces.",
            "Known aliases are mapped before metrics are calculated.",
            "Accent-insensitive fallback keys are used when an alias exists without diacritics.",
            "Empty metadata values are excluded from contamination denominators.",
        ],
        "known_aliases": CANONICAL_ALIASES,
        "vector_normalization": [
            "Canonical profile text is vectorized with TF-IDF using unigrams and bigrams.",
            "When TF-IDF shape allows it, Truncated SVD reduces the sparse matrix to dense latent dimensions.",
            "All vectors are L2-normalized before cosine similarity, clustering quality calculations, and runtime scoring.",
        ],
        "audit_artifacts": [
            CATEGORY_NORMALIZATION_AUDIT_FILENAME,
            PROFILE_AUDIT_FILENAME,
            FEATURE_AUDIT_FILENAME,
            REPRESENTATION_MANIFEST_FILENAME,
        ],
    }


def _selection_scoring_methodology() -> dict[str, Any]:
    return {
        "formula": "selection_score = silhouette_score - 0.35 * cross_subject_contamination_rate - 0.20 * noise_ratio - 0.12 * cluster_size_2_rate - 0.08 * cluster_size_le_3_rate",
        "sort_order": [
            "highest selection_score",
            "highest silhouette_score as tie-breaker",
            "lowest cross_subject_contamination_rate as tie-breaker",
        ],
        "component_definitions": {
            "silhouette_score": "Primary unsupervised cohesion/separation metric calculated with cosine distance on non-noise observations.",
            "cross_subject_contamination_rate": "Share of evaluated clusters containing more than one normalized subject among rows with known subject metadata.",
            "noise_ratio": "Share of rows assigned to DBSCAN noise label -1.",
            "cluster_size_2_rate": "Share of clusters with exactly two rows, used as a fragmentation warning.",
            "cluster_size_le_3_rate": "Share of clusters with three or fewer rows, used as a broader fragmentation warning.",
        },
        "weight_rationale": [
            "Silhouette remains the positive base because the experiment is unsupervised and has no human relevance labels yet.",
            "Cross-subject contamination receives the largest penalty because Classio's recommendation rules treat subject boundaries as business-critical.",
            "Noise receives a moderate penalty because a model that leaves many rows unassigned is less useful for candidate generation.",
            "Tiny-cluster penalties discourage models that look clean only because they fragment the catalog into very small groups.",
            "The weights are heuristic and transparent; they are intended for exploratory model triage, not as proof of recommendation impact.",
        ],
        "why_not_silhouette_only": "The highest Silhouette model can over-reward small, isolated, or noisy clusters. The balanced score prefers a model that is coherent enough while still preserving coverage and useful cluster structure for downstream heuristics.",
    }


def _python_model_development_methodology() -> dict[str, Any]:
    return {
        "language": "Python",
        "core_libraries": ["pandas", "numpy", "scikit-learn"],
        "data_sources": {
            "worksheets": "worksheets table: title, subject, topic, learner stage, level/band, worksheet type, language fields, status, visibility, and creation timestamp. Full worksheet_json is not fetched by the experiment.",
            "exams": "quick_exams table: title, subject, topic, learner stage, level, exam length, exercise types, status, visibility, and creation timestamp. Full exam_data is not fetched by the experiment.",
            "videos": "videos table: title, subject/custom subject, topic, description, learner stage, level/band, status, visibility, creation/update timestamps.",
            "lesson_plans": "lesson_plans table: title, subject, topic, learner stage, level/band, lesson purpose, source/planner metadata, language fields, status, visibility, creation/update timestamps, and plan_json content.",
            "learning_programs": "learning_programs table: title, subject/custom subject, learner stage, level/band, overview, status, visibility, unit/topic counts, sequence order, timestamps, and program_data content.",
            "learning_program_topics": "learning_program_topics table: program_id, unit/topic order, title, subtopic, lesson focus, lesson purpose, objectives, success criteria, can-do statements, suggested worksheet/exam types, homework idea, teacher notes, student summary, estimated lessons, and timestamps.",
            "bounded_content_excerpts": "Optional resource_affinity_content_excerpts view: resource_type, resource_id, content_excerpt, source, and character count. This view must return sanitized bounded text only; the experiment does not fetch full worksheet_json or exam_data as its primary path.",
        },
        "inclusion_rules": [
            "Archived rows are excluded before model development.",
            "Rows without a stable resource id are excluded.",
            "Rows with fewer than three profile tokens are excluded.",
            "Duplicate rows with the same resource key and profile hash are excluded after the first occurrence.",
            "The primary extractor does not select worksheet_json or exam_data. Content is included only through bounded sanitized excerpts when the lightweight excerpt view exists.",
            "If the excerpt view is unavailable, worksheets and exams remain included through metadata-only profiles and the run records a warning.",
        ],
        "profile_construction": [
            "Each included row becomes one canonical text profile.",
            "content_excerpt is included only when a bounded sanitized excerpt is available; images, media, URLs, answer keys, correct answers, and solutions are excluded.",
            "program_topic rows are assigned resource_role=curricular_anchor.",
            "worksheet, exam, video, lesson_plan, and program rows are assigned resource_role=candidate_resource.",
            "Lesson-plan topics are extracted from plan_json keys related to topic, title, objective, focus, vocabulary, success, and assessment, plus the fallback topic field.",
            "Program topics inherit parent learning-program metadata when the parent program is available, so topic anchors carry subject, level, and stage context.",
        ],
        "model_pipeline": [
            "Build a pandas DataFrame of frozen resource profiles.",
            "Vectorize profile_text with scikit-learn TfidfVectorizer using unigrams and bigrams.",
            "When matrix shape permits, reduce TF-IDF features with TruncatedSVD.",
            "Normalize vectors with scikit-learn Normalizer using L2 normalization.",
            "Train candidate KMeans, AgglomerativeClustering, and DBSCAN configurations.",
            "Evaluate each successful configuration with Silhouette, Calinski-Harabasz, Davies-Bouldin, noise ratio, cluster-size diagnostics, and cross-subject/cross-language contamination.",
            "Select the winner by the transparent balanced selection_score formula.",
            "Generate pairwise semantic neighbors with cosine similarity.",
            "Generate the human-review sample from program_topic anchors to candidate resources.",
            "Persist the fitted vectorizer, SVD, normalizer, vector matrix, ordered resource keys, frozen dataset, model comparison, cluster assignments, and audit files.",
        ],
        "reproducibility_controls": [
            f"Random seed is fixed at {DEFAULT_SEED}.",
            "The run stores a dataset fingerprint built from profile hashes.",
            "The run stores a configuration hash for the model grid and preprocessing settings.",
            "The fitted representation is serialized so runtime scoring does not refit TF-IDF from live data.",
        ],
    }


def _human_review_sample(profile_df: pd.DataFrame, neighbors: pd.DataFrame, *, max_rows: int = 80) -> pd.DataFrame:
    columns = [
        "source_resource_key",
        "target_resource_key",
        "source_title",
        "target_title",
        "source_resource_type",
        "target_resource_type",
        "source_resource_role",
        "target_resource_role",
        "source_subject",
        "target_subject",
        "source_language",
        "target_language",
        "source_level",
        "target_level",
        "similarity_score",
        "source_cluster_id",
        "target_cluster_id",
        "same_cluster",
        "reciprocal",
        "review_category",
        "relevance_score_0_3",
        "reviewer_comment",
    ]
    if neighbors.empty:
        return pd.DataFrame(columns=columns)
    resources = {str(row.get("resource_key")): row for row in profile_df.to_dict("records")}

    def category(row: pd.Series) -> str:
        score = _safe_float(row.get("similarity_score"), 0.0) or 0.0
        if bool(row.get("same_cluster")) and bool(row.get("reciprocal")):
            return "same_cluster_reciprocal_pair"
        if str(row.get("source_cluster_id")) == "-1" or str(row.get("target_cluster_id")) == "-1":
            return "noise_resource_pair"
        if score >= 0.72 and bool(row.get("same_subject")):
            return "high_similarity_same_subject"
        if score >= 0.72 and not bool(row.get("same_subject")):
            return "high_similarity_cross_subject"
        if score >= 0.52:
            return "medium_similarity_pair"
        return "lower_similarity_control_pair"

    sample = neighbors.copy()
    sample["review_category"] = sample.apply(category, axis=1)
    parts = []
    per_category = max(4, max_rows // max(1, sample["review_category"].nunique()))
    for _, group in sample.sort_values("similarity_score", ascending=False).groupby("review_category"):
        parts.append(group.head(per_category))
    selected = pd.concat(parts, ignore_index=True).head(max_rows) if parts else sample.head(max_rows)
    rows: list[dict[str, Any]] = []
    for _, row in selected.iterrows():
        source = resources.get(str(row.get("source_resource_key"))) or {}
        target = resources.get(str(row.get("target_resource_key"))) or {}
        rows.append(
            {
                "source_resource_key": row.get("source_resource_key"),
                "target_resource_key": row.get("target_resource_key"),
                "source_title": row.get("source_title"),
                "target_title": row.get("target_title"),
                "source_resource_type": row.get("source_resource_type"),
                "target_resource_type": row.get("target_resource_type"),
                "source_resource_role": row.get("source_resource_role"),
                "target_resource_role": row.get("target_resource_role"),
                "source_subject": source.get("subject"),
                "target_subject": target.get("subject"),
                "source_language": source.get("language"),
                "target_language": target.get("language"),
                "source_level": source.get("level"),
                "target_level": target.get("level"),
                "similarity_score": row.get("similarity_score"),
                "source_cluster_id": row.get("source_cluster_id"),
                "target_cluster_id": row.get("target_cluster_id"),
                "same_cluster": row.get("same_cluster"),
                "reciprocal": row.get("reciprocal"),
                "review_category": row.get("review_category"),
                "relevance_score_0_3": "",
                "reviewer_comment": "",
            }
        )
    return pd.DataFrame(rows, columns=columns)


def _best_model_row(comparison: pd.DataFrame) -> dict[str, Any]:
    if comparison.empty:
        return {}
    ok = comparison[comparison["status"] == "ok"].copy()
    if ok.empty:
        return comparison.iloc[0].to_dict()
    return ok.iloc[0].to_dict()


def _metric_leader_row(comparison: pd.DataFrame) -> dict[str, Any]:
    if comparison.empty:
        return {}
    ok = comparison[comparison["status"] == "ok"].copy()
    if ok.empty:
        return {}
    ok = ok.sort_values("silhouette_score", ascending=False, na_position="last")
    return ok.iloc[0].to_dict()


def _persist_representation(output: Path, vectors: np.ndarray, profile_df: pd.DataFrame, fitted: dict[str, Any], manifest: dict[str, Any], run_id: str, config: dict[str, Any]) -> dict[str, Any]:
    vectorizer_path = output / REPRESENTATION_FILES["vectorizer"]
    svd_path = output / REPRESENTATION_FILES["svd"]
    normalizer_path = output / REPRESENTATION_FILES["normalizer"]
    vectors_path = output / REPRESENTATION_FILES["vectors"]
    resource_keys_path = output / REPRESENTATION_FILES["resource_keys"]
    with vectorizer_path.open("wb") as handle:
        pickle.dump(fitted.get("vectorizer"), handle)
    if fitted.get("svd") is not None:
        with svd_path.open("wb") as handle:
            pickle.dump(fitted.get("svd"), handle)
    with normalizer_path.open("wb") as handle:
        pickle.dump(fitted.get("normalizer"), handle)
    np.savez_compressed(vectors_path, vectors=vectors)
    resource_keys = profile_df["resource_key"].astype(str).tolist() if "resource_key" in profile_df.columns else []
    resource_keys_path.write_text(json.dumps(resource_keys, indent=2), encoding="utf-8")
    files = {
        "vectorizer": str(vectorizer_path),
        "svd": str(svd_path) if svd_path.exists() else "",
        "normalizer": str(normalizer_path),
        "vectors": str(vectors_path),
        "resource_keys": str(resource_keys_path),
    }
    return {
        **manifest,
        "run_id": run_id,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "dataset_fingerprint": _hash_text("|".join(sorted(profile_df["profile_hash"].tolist())) if not profile_df.empty else "empty", 24),
        "configuration_hash": _config_hash(config),
        "resource_count": int(len(resource_keys)),
        "ordered_resource_key_count": int(len(resource_keys)),
        "files": files,
        "file_checksums": {name: _hash_file(Path(path)) for name, path in files.items() if path},
    }


def _render_technical_report(summary: dict[str, Any]) -> str:
    dataset = summary.get("dataset") or {}
    evaluation = summary.get("evaluation") or {}
    best = evaluation.get("best_model") or {}
    normalization = evaluation.get("normalization_methodology") or {}
    scoring = evaluation.get("selection_scoring_methodology") or {}
    python_methodology = evaluation.get("python_model_development_methodology") or {}
    winner_explanation = evaluation.get("winner_explanation") or {}
    lines = [
        "# Resource Affinity Unsupervised Discovery Technical Report",
        "",
        "Business question: Can Classio align worksheets, exams, videos, lesson plans, and learning programs to learning-program topic anchors without manual labels, so teacher recommendations and pre-generation similar-resource warnings start from the intended curriculum topic before heuristic rules are applied?",
        "",
        "Method:",
        "- Program topics are treated as curricular anchors, not complete resources.",
        "- Candidate resource profiles were built from worksheets, exams, videos, lesson plans, and learning programs.",
        "- Text profiles were vectorized with TF-IDF and reduced/normalized into dense semantic vectors when possible.",
        "- K-Means, Agglomerative Clustering, and DBSCAN were compared as unsupervised models.",
        "- Cosine similarity was used to produce both pairwise neighbors and explicit program-topic to candidate-resource alignment candidates.",
        "",
        "Python model development methodology:",
        f"- language: {python_methodology.get('language')}",
        f"- core libraries: {python_methodology.get('core_libraries')}",
        f"- data sources: {python_methodology.get('data_sources')}",
        f"- inclusion rules: {python_methodology.get('inclusion_rules')}",
        f"- profile construction: {python_methodology.get('profile_construction')}",
        f"- model pipeline: {python_methodology.get('model_pipeline')}",
        f"- reproducibility controls: {python_methodology.get('reproducibility_controls')}",
        "",
        "Dataset summary:",
        f"- extraction timestamp: {dataset.get('extracted_at')}",
        f"- source rows inspected: {dataset.get('source_row_count')}",
        f"- included resources: {dataset.get('included_row_count')}",
        f"- curricular anchors: {dataset.get('curricular_anchor_count')}",
        f"- candidate resources: {dataset.get('candidate_resource_count')}",
        f"- excluded resources: {dataset.get('excluded_row_count')}",
        f"- exclusions by reason: {dataset.get('excluded_counts_by_reason')}",
        f"- resource types: {dataset.get('included_counts_by_type')}",
        f"- resource roles: {dataset.get('included_counts_by_role')}",
        f"- subjects represented: {dataset.get('subject_count')}",
        f"- completeness: {dataset.get('completeness')}",
        "",
        "Model comparison:",
        f"- best candidate: {best.get('model_name')} {best.get('parameters_json')}",
        f"- Silhouette Score: {best.get('silhouette_score')}",
        f"- Calinski-Harabasz: {best.get('calinski_harabasz')}",
        f"- Davies-Bouldin: {best.get('davies_bouldin')}",
        f"- cluster count: {best.get('cluster_count')}",
        f"- cluster size <= 3 rate: {best.get('cluster_size_le_3_rate')}",
        f"- cross-subject contamination: {best.get('cross_subject_contamination_rate')} ({best.get('contaminated_subject_clusters')}/{best.get('evaluated_subject_clusters')})",
        f"- cross-language contamination: {best.get('cross_language_contamination_rate')} ({best.get('contaminated_language_clusters')}/{best.get('evaluated_language_clusters')})",
        "",
        "Metric notes:",
        "- Silhouette, Calinski-Harabasz, and Davies-Bouldin are calculated only on non-noise observations.",
        "- Silhouette uses cosine distance.",
        "- Contamination rates use normalized category values and ignore empty metadata values in denominators.",
        "- The selected model is the highest balanced selection score, not necessarily the highest Silhouette model.",
        f"- Anchor-resource alignment summary: {evaluation.get('anchor_resource_alignment_summary')}",
        "",
        "Normalization methodology:",
        f"- text cleaning: {normalization.get('text_cleaning')}",
        f"- category normalization: {normalization.get('category_normalization')}",
        f"- known aliases: {normalization.get('known_aliases')}",
        f"- vector normalization: {normalization.get('vector_normalization')}",
        f"- audit artifacts: {normalization.get('audit_artifacts')}",
        "",
        "Winner scoring formula:",
        f"- formula: {scoring.get('formula')}",
        f"- sort order: {scoring.get('sort_order')}",
        f"- component definitions: {scoring.get('component_definitions')}",
        f"- weight rationale: {scoring.get('weight_rationale')}",
        f"- why not Silhouette only: {scoring.get('why_not_silhouette_only')}",
        "",
        "Winner explanation:",
        f"- winner: {winner_explanation.get('winner')}",
        f"- metric leader: {winner_explanation.get('metric_leader')}",
        f"- winner selection score: {winner_explanation.get('winner_selection_score')}",
        f"- metric leader selection score: {winner_explanation.get('metric_leader_selection_score')}",
        f"- reason: {winner_explanation.get('reason')}",
        "",
        "Production note:",
        "This run is an offline unsupervised experiment. It does not deploy a model automatically. The semantic affinity outputs are suitable for review and shadow comparison before production use.",
    ]
    return "\n".join(lines) + "\n"


def _render_academic_report(summary: dict[str, Any]) -> str:
    dataset = summary.get("dataset") or {}
    evaluation = summary.get("evaluation") or {}
    best = evaluation.get("best_model") or {}
    normalization = evaluation.get("normalization_methodology") or {}
    scoring = evaluation.get("selection_scoring_methodology") or {}
    python_methodology = evaluation.get("python_model_development_methodology") or {}
    winner_explanation = evaluation.get("winner_explanation") or {}
    lines = [
        "# Experimento 3 - Descubrimiento no supervisado de afinidad entre recursos",
        "",
        "## Planteamiento de la solución",
        "Classio ya cuenta con recomendaciones basadas en reglas, metadatos y señales de uso. La limitación es que un recurso puede apoyar un tema del learning program aunque sus etiquetas, títulos o temas no coincidan exactamente. Para abordar este problema, se propone una capa de aprendizaje no supervisado que alinee recursos candidatos con temas curriculares del learning program.",
        "",
        "El sistema no sustituye el ranker actual. Primero descubre candidatos semánticamente cercanos al tema del learning program y después las reglas de negocio de Classio filtran por profesor, estudiante, asignatura, idioma, nivel, programa de aprendizaje, estado de archivo y tipo de recurso.",
        "",
        "Objetivos SMART:",
        "- Específico: construir un modelo no supervisado que agrupe recursos de Classio y mida su alineación con temas del learning program.",
        "- Medible: comparar K-Means, Agglomerative Clustering y DBSCAN con Silhouette Score, Calinski-Harabasz, Davies-Bouldin y tasa de contaminación entre asignaturas.",
        "- Alcanzable: usar los recursos ya almacenados en Classio como dataset inicial.",
        "- Realista: ejecutar el modelo en modo offline/experimental antes de impactar recomendaciones en producción.",
        "- Acotado en el tiempo: producir un reporte reproducible de Experimento 3 para revisión antes de integrar el mejor modelo.",
        "",
        "## Desarrollo del modelo",
        f"Dataset utilizado: {dataset.get('included_row_count')} filas incluidas: {dataset.get('curricular_anchor_count')} temas del learning program como anclas curriculares y {dataset.get('candidate_resource_count')} recursos candidatos.",
        "",
        "Datos utilizados:",
        "- worksheets: título, asignatura, tema, etapa, nivel/banda, tipo de worksheet, idioma, estado, visibilidad y fecha de creación. El experimento no trae worksheet_json completo.",
        "- quick_exams: título, asignatura, tema, etapa, nivel, duración/tamaño, tipos de ejercicios, estado, visibilidad y fecha de creación. El experimento no trae exam_data completo.",
        "- videos: título, asignatura, tema, descripción, etapa, nivel/banda, estado, visibilidad y timestamps.",
        "- lesson_plans: título, asignatura, tema, etapa, nivel/banda, propósito, metadatos de planificación, idioma, estado, visibilidad, timestamps y plan_json.",
        "- learning_programs: título, asignatura, etapa, nivel/banda, overview, estado, visibilidad, conteos de unidades/temas, orden, timestamps y program_data.",
        "- learning_program_topics: unidad, número de tema, título, subtopic, lesson focus, propósito, objetivos, criterios de éxito, can-do statements, sugerencias de worksheet/exam, homework, notas docentes y resumen para estudiantes.",
        "- resource_affinity_content_excerpts: vista opcional para extractos sanitizados y acotados de worksheets/exams. Si no existe, worksheets y exams entran por metadata-only y se registra warning.",
        "",
        "Reglas de inclusión y exclusión:",
        "- Se excluyen registros archivados antes de entrenar o comparar modelos.",
        "- Se excluyen registros sin identificador estable.",
        "- Se excluyen perfiles con menos de tres tokens.",
        "- Se eliminan duplicados con la misma resource_key y el mismo profile_hash.",
        f"- Reglas registradas en la corrida: {python_methodology.get('inclusion_rules')}",
        "",
        "Cómo se desarrolló el modelo en Python:",
        f"- Lenguaje y librerías principales: {python_methodology.get('language')}; {python_methodology.get('core_libraries')}.",
        "- Se construyó un DataFrame congelado con perfiles canónicos de recursos.",
        "- Cada fila se transformó en profile_text combinando rol, tipo, título, asignatura, idioma, nivel, etapa, tema, subtipo y contenido pedagógico disponible.",
        "- El contenido de worksheets/exams solo se incorpora como content_excerpt sanitizado: sin imágenes, media, URLs, answer keys, correct answers ni soluciones.",
        "- Los lesson plans aportan temas extraídos desde plan_json mediante claves asociadas a topic, title, objective, focus, vocabulary, success y assessment.",
        "- Los program_topic heredan metadata del learning program padre cuando está disponible, para que el ancla curricular conserve materia, nivel y etapa.",
        "- profile_text se vectorizó con TfidfVectorizer de scikit-learn usando unigramas y bigramas.",
        "- Si la matriz tenía tamaño suficiente, se aplicó TruncatedSVD para reducir dimensionalidad.",
        "- Se aplicó normalización L2 con Normalizer antes de calcular similaridad coseno y métricas de clustering.",
        "- Se entrenaron configuraciones de KMeans, AgglomerativeClustering y DBSCAN.",
        "- Cada configuración exitosa se evaluó con Silhouette, Calinski-Harabasz, Davies-Bouldin, ruido, tamaño de clústeres y contaminación entre materias/idiomas.",
        "- El ganador se seleccionó con la fórmula balanceada documentada en este informe.",
        "- La auditoría humana se construyó desde anclas program_topic hacia recursos candidatos, no desde pares tema-tema.",
        f"- Controles de reproducibilidad: {python_methodology.get('reproducibility_controls')}",
        "",
        "Cada fila se transformó en un perfil canónico de texto que combina rol, tipo, título, asignatura, idioma, nivel, etapa, tema, subtipo y contenido pedagógico disponible. Los lesson plans aportan temas extraídos desde plan_json cuando existen. Esos perfiles se vectorizaron con TF-IDF y, cuando el tamaño del dataset lo permite, se redujeron con Truncated SVD y se normalizaron para usar similaridad coseno.",
        "",
        "Normalización de datos:",
        "- Limpieza textual: todos los campos se convierten a texto, los espacios múltiples se reducen a un solo espacio y se eliminan espacios al inicio/final.",
        "- Normalización Unicode: las categorías se normalizan con NFKC antes de compararlas.",
        "- Materia, idioma, nivel, tipo de recurso y rol del recurso se auditan con valor original, valor normalizado y conteo.",
        "- Las categorías se comparan con casefold, separadores como / y | se convierten a espacios y se aplican alias conocidos.",
        f"- Alias usados: {normalization.get('known_aliases')}",
        "- Los valores vacíos no se usan como denominador en contaminación de materia o idioma, para no castigar al modelo por metadata ausente.",
        "- Vectorización: los perfiles se convierten con TF-IDF usando unigramas y bigramas; luego se aplica SVD si el tamaño lo permite y normalización L2 para similaridad coseno.",
        f"- Artefactos de auditoría: {normalization.get('audit_artifacts')}",
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
        f"- Selection score del ganador: {best.get('selection_score')}",
        f"- Resumen de alineación tema-recurso: {evaluation.get('anchor_resource_alignment_summary')}",
        "",
        "Fórmula de selección del ganador:",
        f"- {scoring.get('formula')}",
        "- El Silhouette Score es la base positiva porque en esta fase no existen etiquetas humanas de relevancia.",
        "- La contaminación entre asignaturas recibe la penalización más fuerte porque las reglas de recomendación de Classio dependen de respetar límites de materia.",
        "- La proporción de ruido penaliza modelos que dejan muchos registros sin asignar, lo cual reduce utilidad para generar candidatos.",
        "- Las penalizaciones por clústeres pequeños reducen el riesgo de elegir modelos que parecen coherentes solo porque fragmentan demasiado el catálogo.",
        f"- Orden de desempate: {scoring.get('sort_order')}",
        f"- Por qué no basta Silhouette: {scoring.get('why_not_silhouette_only')}",
        "",
        "Por qué se considera ganador:",
        f"- Ganador por score balanceado: {winner_explanation.get('winner')} con selection score {winner_explanation.get('winner_selection_score')}.",
        f"- Líder métrico por Silhouette: {winner_explanation.get('metric_leader')} con selection score {winner_explanation.get('metric_leader_selection_score')}.",
        f"- Justificación: {winner_explanation.get('reason')}",
        "",
        "## Conclusiones",
        f"El experimento generó un mapa de afinidad semántica para {dataset.get('included_row_count')} filas y una muestra de revisión humana basada en anclas curriculares hacia recursos candidatos. La utilidad productiva debe valorarse revisando esas alineaciones y la coherencia de los clusters antes de activar el modelo en producción.",
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


def _hash_file(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate_resource_affinity_unsupervised_evaluation(output_dir: Path | str = DEFAULT_OUTPUT_DIR, *, run_id: str | None = None) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    safe_run_id = run_id or uuid.uuid4().hex[:12]
    extraction_time = _utc_now()
    profile_df, dataset_summary, exclusion_audit, normalization_audit = extract_resource_profiles(extraction_time)
    experiment_config = _experiment_config(len(profile_df))
    experiment_config["configuration_hash"] = _config_hash(experiment_config)
    experiment_config["runtime"] = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "numpy": getattr(np, "__version__", ""),
        "pandas": getattr(pd, "__version__", ""),
    }
    if profile_df.empty:
        comparison = pd.DataFrame(columns=MODEL_COMPARISON_COLUMNS)
        neighbors = pd.DataFrame(columns=NEIGHBOR_COLUMNS)
        anchor_resource_candidates = pd.DataFrame(columns=NEIGHBOR_COLUMNS)
        cluster_assignments = pd.DataFrame(columns=CLUSTER_COLUMNS)
        embedding_manifest = {}
        representation_manifest = {}
        human_review_sample = pd.DataFrame()
    else:
        vectors, embedding_manifest, fitted = _build_vectors(profile_df)
        comparison, labels_by_model = evaluate_unsupervised_models(profile_df, vectors)
        best = _best_model_row(comparison)
        best_labels = labels_by_model.get(str(best.get("model_key") or ""), np.array([], dtype=int))
        neighbors = _top_neighbors(profile_df, vectors, best_labels, top_k=DEFAULT_NEIGHBOR_TOP_K)
        anchor_resource_candidates = _anchor_resource_candidates(profile_df, vectors, best_labels, top_k=DEFAULT_ANCHOR_CANDIDATE_TOP_K)
        cluster_assignments = profile_df[["resource_key", "resource_type", "resource_role", "resource_id", "title", "subject", "language", "level", "topic"]].copy()
        cluster_assignments["cluster_id"] = best_labels if len(best_labels) == len(cluster_assignments) else -1
        representation_manifest = _persist_representation(output, vectors, profile_df, fitted, embedding_manifest, safe_run_id, experiment_config)
        human_review_sample = _human_review_sample(profile_df, anchor_resource_candidates)

    best_model = _best_model_row(comparison)
    metric_leader = _metric_leader_row(comparison)
    normalization_methodology = _normalization_methodology()
    selection_scoring_methodology = _selection_scoring_methodology()
    python_model_development = _python_model_development_methodology()
    neighbor_summary = _neighbor_summary(neighbors, top_k=DEFAULT_NEIGHBOR_TOP_K)
    anchor_neighbor_summary = _neighbor_summary(anchor_resource_candidates, top_k=DEFAULT_ANCHOR_CANDIDATE_TOP_K)
    high_confidence_neighbors = int((neighbors.get("similarity_score", pd.Series(dtype=float)).astype(float) >= 0.72).sum()) if not neighbors.empty else 0
    high_confidence_anchor_candidates = int((anchor_resource_candidates.get("similarity_score", pd.Series(dtype=float)).astype(float) >= 0.72).sum()) if not anchor_resource_candidates.empty else 0
    missing_language = (dataset_summary.get("completeness") or {}).get("language", {}).get("missing_count", 0)
    evaluation = {
        "experiment_id": "resource_affinity_unsupervised_discovery",
        "run_id": safe_run_id,
        "target_definition": "Learning-program topics are curricular anchors. Worksheets, exams, videos, lesson plans, and learning programs are candidate resources tested for semantic alignment with those anchors.",
        "primary_metric": "balanced_selection_score",
        "metric_leader": metric_leader.get("model_name"),
        "primary_metric_leader": best_model.get("model_name"),
        "balanced_candidate": best_model.get("model_name"),
        "selected_candidate_for_human_review": best_model.get("model_name"),
        "winner": best_model.get("model_name"),
        "best_model": best_model,
        "maturity_verdict": "EXPLORATORY_ONLY" if int(dataset_summary.get("included_row_count") or 0) < 80 else "CANDIDATE_FOR_SHADOW_TESTING",
        "overall_evidence_strength": "EXPLORATORY_SEMANTIC_AFFINITY",
        "high_confidence_neighbor_edges": high_confidence_neighbors,
        "high_confidence_anchor_candidate_edges": high_confidence_anchor_candidates,
        "neighbor_summary": neighbor_summary,
        "anchor_resource_alignment_summary": anchor_neighbor_summary,
        "feature_names": ["profile_text", "subject_normalized", "language_normalized", "level_normalized", "resource_type_normalized"],
        "embedding_manifest": embedding_manifest,
        "representation_manifest": representation_manifest,
        "normalization_methodology": normalization_methodology,
        "selection_scoring_methodology": selection_scoring_methodology,
        "python_model_development_methodology": python_model_development,
        "experiment_config": {
            "configuration_hash": experiment_config["configuration_hash"],
            "candidate_count": len(_candidate_models(len(profile_df))),
            "not_exhaustive": True,
        },
        "winner_explanation": {
            "winner": best_model.get("model_name"),
            "metric_leader": metric_leader.get("model_name"),
            "winner_selection_score": best_model.get("selection_score"),
            "metric_leader_selection_score": metric_leader.get("selection_score"),
            "reason": "The winner is the top balanced selection-score candidate. The metric leader is reported separately because a higher Silhouette score alone can over-reward fragmented, noisy, or business-contaminated cluster structures.",
        },
        "metric_notes": {
            "cluster_metrics_noise_handling": "Silhouette, Calinski-Harabasz, and Davies-Bouldin are calculated only on non-noise observations.",
            "silhouette_distance": "cosine",
            "contamination_denominators": "Empty metadata values are excluded from unique-category counts.",
        },
        "limitations": [
            "No human-labeled semantic relevance labels are used in this unsupervised phase.",
            "Small or imbalanced resource catalogs can make clustering metrics unstable.",
            "Program topics are curricular anchors, not standalone resources; candidate-resource alignment must be reviewed separately from topic-to-topic similarity.",
            "Business rules must still filter by subject, language, teacher, student, level, and archive state.",
            "Cross-language contamination is calculated only from non-empty known language values. Missing language metadata limits interpretation." if int(missing_language or 0) else "",
        ],
    }
    evaluation["limitations"] = [item for item in evaluation["limitations"] if item]
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
        [
            "resource_key",
            "resource_type",
            "resource_role",
            "resource_id",
            "profile_hash",
            "profile_token_count",
            "title",
            "subject",
            "subject_normalized",
            "language",
            "language_normalized",
            "level",
            "level_normalized",
            "topic",
            "topics_extracted",
            "content_excerpt",
            "content_excerpt_source",
        ]
    ].copy() if not profile_df.empty else pd.DataFrame(columns=["resource_key", "resource_type", "resource_role", "resource_id", "profile_hash", "profile_token_count", "title", "subject", "subject_normalized", "language", "language_normalized", "level", "level_normalized", "topic", "topics_extracted", "content_excerpt", "content_excerpt_source"])
    feature_audit = pd.DataFrame(
        [
            {"feature": "profile_text", "retained": True, "role": "unsupervised_text_profile", "exclusion_reason": ""},
            {"feature": "resource_role", "retained": True, "role": "analysis_unit_split_curricular_anchor_vs_candidate_resource", "exclusion_reason": ""},
            {"feature": "topics_extracted", "retained": True, "role": "lesson_plan_topic_signal", "exclusion_reason": ""},
            {"feature": "content_excerpt", "retained": True, "role": "bounded_sanitized_content_signal_when_available", "exclusion_reason": ""},
            {"feature": "subject_normalized", "retained": True, "role": "business_scope_quality_check", "exclusion_reason": ""},
            {"feature": "language_normalized", "retained": True, "role": "business_scope_quality_check", "exclusion_reason": ""},
            {"feature": "level_normalized", "retained": True, "role": "business_scope_quality_check", "exclusion_reason": ""},
            {"feature": "resource_type_normalized", "retained": True, "role": "business_scope_quality_check", "exclusion_reason": ""},
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
    _write_frame(output / EXCLUSION_AUDIT_FILENAME, exclusion_audit)
    _write_frame(output / CATEGORY_NORMALIZATION_AUDIT_FILENAME, normalization_audit)
    _write_frame(output / FEATURE_AUDIT_FILENAME, feature_audit)
    _write_frame(output / MODEL_COMPARISON_FILENAME, comparison)
    _write_frame(output / CLUSTER_ASSIGNMENTS_FILENAME, cluster_assignments)
    _write_frame(output / NEIGHBORS_FILENAME, neighbors)
    _write_frame(output / ANCHOR_RESOURCE_CANDIDATES_FILENAME, anchor_resource_candidates)
    _write_frame(output / HUMAN_REVIEW_SAMPLE_FILENAME, human_review_sample)
    _write_frame(output / RECONCILIATION_FILENAME, reconciliation)
    _write_json(output / EXPERIMENT_CONFIG_FILENAME, experiment_config)
    _write_json(output / "resource_affinity_embedding_manifest.json", embedding_manifest)
    _write_json(output / REPRESENTATION_MANIFEST_FILENAME, representation_manifest)
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
            "anchor_resource_candidates": str(output / ANCHOR_RESOURCE_CANDIDATES_FILENAME),
            "human_review_sample": str(output / HUMAN_REVIEW_SAMPLE_FILENAME),
            "academic_report": str(output / ACADEMIC_REPORT_FILENAME),
        },
    }


def review_resource_affinity_unsupervised(output_dir: Path | str) -> dict[str, Any]:
    output = Path(output_dir)
    summary_path = output / RUN_SUMMARY_FILENAME
    comparison_path = output / MODEL_COMPARISON_FILENAME
    neighbors_path = output / NEIGHBORS_FILENAME
    anchor_candidates_path = output / ANCHOR_RESOURCE_CANDIDATES_FILENAME
    frozen_path = output / FROZEN_DATASET_FILENAME
    cluster_path = output / CLUSTER_ASSIGNMENTS_FILENAME
    exclusion_path = output / EXCLUSION_AUDIT_FILENAME
    representation_path = output / REPRESENTATION_MANIFEST_FILENAME
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    try:
        comparison = pd.read_csv(comparison_path) if comparison_path.exists() else pd.DataFrame(columns=MODEL_COMPARISON_COLUMNS)
    except Exception:
        comparison = pd.DataFrame(columns=MODEL_COMPARISON_COLUMNS)
    try:
        neighbors = pd.read_csv(neighbors_path) if neighbors_path.exists() else pd.DataFrame(columns=NEIGHBOR_COLUMNS)
    except Exception:
        neighbors = pd.DataFrame(columns=NEIGHBOR_COLUMNS)
    try:
        anchor_candidates = pd.read_csv(anchor_candidates_path) if anchor_candidates_path.exists() else pd.DataFrame(columns=NEIGHBOR_COLUMNS)
    except Exception:
        anchor_candidates = pd.DataFrame(columns=NEIGHBOR_COLUMNS)
    try:
        frozen = pd.read_csv(frozen_path) if frozen_path.exists() else pd.DataFrame(columns=PROFILE_COLUMNS)
    except Exception:
        frozen = pd.DataFrame(columns=PROFILE_COLUMNS)
    try:
        clusters = pd.read_csv(cluster_path) if cluster_path.exists() else pd.DataFrame(columns=CLUSTER_COLUMNS)
    except Exception:
        clusters = pd.DataFrame(columns=CLUSTER_COLUMNS)
    try:
        exclusions = pd.read_csv(exclusion_path) if exclusion_path.exists() else pd.DataFrame()
    except Exception:
        exclusions = pd.DataFrame()
    representation = json.loads(representation_path.read_text(encoding="utf-8")) if representation_path.exists() else {}
    dataset = summary.get("dataset") or {}
    blocking: list[str] = []
    warnings: list[str] = []
    if int(dataset.get("included_row_count") or 0) < 6:
        blocking.append("Fewer than six resources are available for unsupervised comparison.")
    if comparison.empty or not (comparison.get("status", pd.Series(dtype=str)).astype(str) == "ok").any():
        blocking.append("No unsupervised model completed successfully.")
    if neighbors.empty:
        warnings.append("No semantic-neighbor artifact was generated.")
    anchor_count = int(dataset.get("curricular_anchor_count") or 0)
    candidate_count = int(dataset.get("candidate_resource_count") or 0)
    if anchor_count and candidate_count and anchor_candidates.empty:
        blocking.append("No program-topic to candidate-resource alignment artifact was generated.")
    source_rows = int(dataset.get("source_row_count") or 0)
    included_rows = int(dataset.get("included_row_count") or 0)
    excluded_rows = int(dataset.get("excluded_row_count") or 0)
    if source_rows != included_rows + excluded_rows:
        blocking.append("Source row accounting does not reconcile to included plus excluded rows.")
    if len(frozen) != included_rows:
        blocking.append("Frozen dataset row count does not match included row count.")
    if "resource_key" in frozen.columns and frozen["resource_key"].astype(str).duplicated().any():
        blocking.append("Frozen dataset contains duplicate resource keys.")
    frozen_keys = set(frozen.get("resource_key", pd.Series(dtype=str)).astype(str))
    cluster_keys = set(clusters.get("resource_key", pd.Series(dtype=str)).astype(str))
    if frozen_keys and cluster_keys and cluster_keys != frozen_keys:
        blocking.append("Cluster assignment keys do not match the frozen dataset.")
    if not neighbors.empty:
        if (neighbors.get("source_resource_key", pd.Series(dtype=str)).astype(str) == neighbors.get("target_resource_key", pd.Series(dtype=str)).astype(str)).any():
            blocking.append("Neighbor artifact contains self-neighbors.")
        neighbor_keys = set(neighbors.get("source_resource_key", pd.Series(dtype=str)).astype(str)) | set(neighbors.get("target_resource_key", pd.Series(dtype=str)).astype(str))
        if frozen_keys and not neighbor_keys.issubset(frozen_keys):
            blocking.append("Neighbor artifact references resources outside the frozen dataset.")
        top_k = int(((summary.get("evaluation") or {}).get("neighbor_summary") or {}).get("top_k") or DEFAULT_NEIGHBOR_TOP_K)
        counts = neighbors.get("source_resource_key", pd.Series(dtype=str)).astype(str).value_counts()
        if included_rows > 1 and not counts.empty and int(counts.min()) != min(top_k, included_rows - 1):
            warnings.append("At least one source does not have the expected number of directed neighbors.")
    if not anchor_candidates.empty:
        if not (anchor_candidates.get("source_resource_role", pd.Series(dtype=str)).astype(str) == "curricular_anchor").all():
            blocking.append("Anchor-resource artifact contains a non-anchor source.")
        if not (anchor_candidates.get("target_resource_role", pd.Series(dtype=str)).astype(str) == "candidate_resource").all():
            blocking.append("Anchor-resource artifact contains a non-candidate target.")
        anchor_neighbor_keys = set(anchor_candidates.get("source_resource_key", pd.Series(dtype=str)).astype(str)) | set(anchor_candidates.get("target_resource_key", pd.Series(dtype=str)).astype(str))
        if frozen_keys and not anchor_neighbor_keys.issubset(frozen_keys):
            blocking.append("Anchor-resource artifact references rows outside the frozen dataset.")
    if representation:
        files = representation.get("files") or {}
        for name in ("vectorizer", "normalizer", "vectors", "resource_keys"):
            path = Path(str(files.get(name) or ""))
            if not path.exists():
                blocking.append(f"Missing fitted representation artifact: {name}.")
        if int(representation.get("ordered_resource_key_count") or 0) != included_rows:
            blocking.append("Fitted representation resource ordering does not match included row count.")
    else:
        blocking.append("Fitted representation manifest is missing.")
    if excluded_rows and exclusions.empty:
        blocking.append("Excluded rows were counted but no exclusion audit was generated.")
    verdict = "REQUIRES_RERUN" if blocking else "VALIDATED_EXPLORATORY_RUN"
    overall = "NO_ROBUST_WINNER" if blocking else "EXPLORATORY_SEMANTIC_AFFINITY"
    markdown = [
        "# Resource Affinity Unsupervised Integrity Review",
        "",
        f"Final verdict: {verdict}",
        f"Overall model conclusion: {overall}",
        "",
        "Checks:",
        f"- source rows: {dataset.get('source_row_count')}",
        f"- resources included: {dataset.get('included_row_count')}",
        f"- curricular anchors: {dataset.get('curricular_anchor_count')}",
        f"- candidate resources: {dataset.get('candidate_resource_count')}",
        f"- resources excluded: {dataset.get('excluded_row_count')}",
        f"- completed model rows: {int((comparison.get('status', pd.Series(dtype=str)).astype(str) == 'ok').sum()) if not comparison.empty else 0}",
        f"- neighbor rows: {len(neighbors)}",
        f"- anchor-resource candidate rows: {len(anchor_candidates)}",
        f"- fitted representation: {'present' if representation else 'missing'}",
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
