from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import streamlit as st

from core.database import get_sb, json_safe
from core.state import get_current_user_id


REPORT_CONTEXT_TABLE = "experiment_report_contexts"
REPORT_CONTEXT_ROOT = Path("reports") / "ml_architecture" / "eic_reports"
SUPPORTED_LANGUAGES = {"en", "es", "tr"}

PURPOSE_OPTIONS = (
    "infrastructure_validation",
    "engagement_prediction",
    "recommendation_optimization",
    "learning_outcome_prediction",
    "churn_or_disengagement_detection",
    "operational_efficiency",
    "other",
)

DECISION_OPTIONS = (
    "maintain_current_heuristic",
    "continue_collecting_data",
    "run_another_evaluation",
    "move_to_shadow_testing",
    "start_controlled_pilot",
    "reject_current_approach",
    "archive_experiment",
    "other",
)

AUDIENCE_OPTIONS = (
    "leadership_meeting",
    "product_review",
    "data_science_review",
    "technical_review",
    "school_administration",
    "mixed_audience",
)

LOCAL_ONLY_CONTEXT_FIELDS = (
    "main_limitation",
    "evidence_non_proof",
    "recommended_next_action",
)

REQUIRED_CONTEXT_FIELDS = (
    "purpose_key",
    "decision_under_consideration_key",
    "audience_key",
    "business_problem",
    "decision_supported",
    "expected_value",
    "product_impact",
    "success_definition",
    "minimum_evidence_required",
    "risks",
    "main_limitation",
    "evidence_non_proof",
    "recommended_next_action",
    "next_review_trigger",
    "next_review_date",
    "responsible_person_or_team",
    "meeting_notes",
)


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _lang(language: str | None) -> str:
    safe = _clean_text(language).lower()
    return safe if safe in SUPPORTED_LANGUAGES else "en"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _report_dir(run_id: str, language: str) -> Path:
    return REPORT_CONTEXT_ROOT / _clean_text(run_id) / _lang(language)


def _context_cache_path(run_id: str, language: str) -> Path:
    safe_run_id = _clean_text(run_id)
    safe_lang = _lang(language)
    return REPORT_CONTEXT_ROOT / safe_run_id / f"report_context_{safe_lang}.json"


def _write_local_context(payload: dict[str, Any]) -> None:
    cache_path = _context_cache_path(str(payload.get("run_id") or ""), str(payload.get("language") or "en"))
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(json_safe(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def _read_local_context(run_id: str, language: str) -> dict[str, Any] | None:
    cache_path = _context_cache_path(run_id, language)
    if not cache_path.exists():
        return None
    try:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_any_language_context(run_id: str) -> dict[str, Any] | None:
    safe_run_id = _clean_text(run_id)
    if not safe_run_id:
        return None
    try:
        response = (
            get_sb()
            .table(REPORT_CONTEXT_TABLE)
            .select("*")
            .eq("run_id", safe_run_id)
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = getattr(response, "data", None) or []
        if rows:
            row = dict(rows[0])
            _write_local_context(row)
            return row
    except Exception:
        pass
    root = REPORT_CONTEXT_ROOT / safe_run_id
    if not root.exists():
        return None
    latest_path: Path | None = None
    latest_mtime = -1.0
    for path in root.glob("report_context_*.json"):
        try:
            mtime = path.stat().st_mtime
        except Exception:
            continue
        if mtime > latest_mtime:
            latest_mtime = mtime
            latest_path = path
    if latest_path is None:
        return None
    try:
        return json.loads(latest_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _clear_cached_reports(run_id: str, language: str) -> None:
    report_dir = _report_dir(run_id, language)
    if not report_dir.exists():
        return
    for path in report_dir.glob("*.docx"):
        try:
            path.unlink()
        except Exception:
            pass


def _default_context(run_id: str, experiment_id: str, language: str) -> dict[str, Any]:
    return {
        "run_id": _clean_text(run_id),
        "experiment_id": _clean_text(experiment_id),
        "language": _lang(language),
        "purpose_key": "",
        "decision_under_consideration_key": "",
        "audience_key": "",
        "business_problem": "",
        "decision_supported": "",
        "expected_value": "",
        "product_impact": "",
        "success_definition": "",
        "minimum_evidence_required": "",
        "risks": "",
        "main_limitation": "",
        "evidence_non_proof": "",
        "recommended_next_action": "",
        "next_review_trigger": "",
        "next_review_date": "",
        "responsible_person_or_team": "",
        "meeting_notes": "",
        "created_by": "",
        "created_at": "",
        "updated_at": "",
    }


def get_report_context(run_id: str, experiment_id: str, language: str) -> dict[str, Any]:
    safe_run_id = _clean_text(run_id)
    safe_experiment_id = _clean_text(experiment_id)
    safe_lang = _lang(language)
    if not safe_run_id:
        return _default_context(safe_run_id, safe_experiment_id, safe_lang)
    try:
        response = (
            get_sb()
            .table(REPORT_CONTEXT_TABLE)
            .select("*")
            .eq("run_id", safe_run_id)
            .eq("language", safe_lang)
            .limit(1)
            .execute()
        )
        rows = getattr(response, "data", None) or []
        if rows:
            row = dict(rows[0])
            row.setdefault("experiment_id", safe_experiment_id)
            row.setdefault("language", safe_lang)
            local_row = _read_local_context(safe_run_id, safe_lang) or {}
            merged = {**_default_context(safe_run_id, safe_experiment_id, safe_lang), **row, **dict(local_row)}
            _write_local_context(merged)
            return merged
    except Exception:
        pass
    local_row = _read_local_context(safe_run_id, safe_lang)
    if local_row:
        local_row = dict(local_row)
        local_row["language"] = safe_lang
        local_row.setdefault("experiment_id", safe_experiment_id)
        return {**_default_context(safe_run_id, safe_experiment_id, safe_lang), **local_row}
    cross_language = _load_any_language_context(safe_run_id)
    if cross_language:
        fallback_row = dict(cross_language)
        fallback_row["language"] = safe_lang
        fallback_row.setdefault("experiment_id", safe_experiment_id)
        return {**_default_context(safe_run_id, safe_experiment_id, safe_lang), **fallback_row}
    return _default_context(safe_run_id, safe_experiment_id, safe_lang)


def save_report_context(payload: dict[str, Any]) -> dict[str, Any]:
    safe_run_id = _clean_text(payload.get("run_id"))
    safe_experiment_id = _clean_text(payload.get("experiment_id"))
    safe_lang = _lang(payload.get("language"))
    now_text = _now_iso()
    current_user_id = _clean_text(get_current_user_id())
    base = {
        "run_id": safe_run_id,
        "experiment_id": safe_experiment_id,
        "language": safe_lang,
        "purpose_key": _clean_text(payload.get("purpose_key")),
        "decision_under_consideration_key": _clean_text(payload.get("decision_under_consideration_key")),
        "audience_key": _clean_text(payload.get("audience_key")),
        "business_problem": _clean_text(payload.get("business_problem")),
        "decision_supported": _clean_text(payload.get("decision_supported")),
        "expected_value": _clean_text(payload.get("expected_value")),
        "product_impact": _clean_text(payload.get("product_impact")),
        "success_definition": _clean_text(payload.get("success_definition")),
        "minimum_evidence_required": _clean_text(payload.get("minimum_evidence_required")),
        "risks": _clean_text(payload.get("risks")),
        "next_review_trigger": _clean_text(payload.get("next_review_trigger")),
        "next_review_date": _clean_text(payload.get("next_review_date")),
        "responsible_person_or_team": _clean_text(payload.get("responsible_person_or_team")),
        "meeting_notes": _clean_text(payload.get("meeting_notes")),
        "updated_at": now_text,
    }
    local_only = {field: _clean_text(payload.get(field)) for field in LOCAL_ONLY_CONTEXT_FIELDS}
    try:
        response = (
            get_sb()
            .table(REPORT_CONTEXT_TABLE)
            .select("*")
            .eq("run_id", safe_run_id)
            .eq("language", safe_lang)
            .limit(1)
            .execute()
        )
        rows = getattr(response, "data", None) or []
        if rows:
            record_id = rows[0].get("id")
            result = (
                get_sb()
                .table(REPORT_CONTEXT_TABLE)
                .update(json_safe(base))
                .eq("id", record_id)
                .execute()
            )
            saved = (getattr(result, "data", None) or [base])[0]
        else:
            create_payload = {
                **base,
                "created_by": current_user_id or None,
                "created_at": now_text,
            }
            result = get_sb().table(REPORT_CONTEXT_TABLE).insert(json_safe(create_payload)).execute()
            saved = (getattr(result, "data", None) or [create_payload])[0]
        saved_payload = {**_default_context(safe_run_id, safe_experiment_id, safe_lang), **dict(saved), **local_only, "_storage_status": "supabase"}
        _write_local_context(saved_payload)
        _clear_cached_reports(safe_run_id, safe_lang)
        return saved_payload
    except Exception:
        fallback = {
            **_default_context(safe_run_id, safe_experiment_id, safe_lang),
            **base,
            "created_by": current_user_id,
            "created_at": now_text,
            "updated_at": now_text,
            **local_only,
            "_storage_status": "local_cache",
        }
        _write_local_context(fallback)
        _clear_cached_reports(safe_run_id, safe_lang)
        return fallback


def report_context_options() -> dict[str, tuple[str, ...]]:
    return {
        "purpose_key": PURPOSE_OPTIONS,
        "decision_under_consideration_key": DECISION_OPTIONS,
        "audience_key": AUDIENCE_OPTIONS,
    }


def report_context_completion(context: dict[str, Any]) -> dict[str, Any]:
    completed = sum(1 for field in REQUIRED_CONTEXT_FIELDS if _clean_text(context.get(field)))
    missing_fields = [field for field in REQUIRED_CONTEXT_FIELDS if not _clean_text(context.get(field))]
    return {
        "completed_fields": completed,
        "total_fields": len(REQUIRED_CONTEXT_FIELDS),
        "complete": completed == len(REQUIRED_CONTEXT_FIELDS),
        "missing_fields": missing_fields,
    }
