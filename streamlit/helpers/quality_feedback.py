"""Explicit teacher labels for recommendations; never infer a label from opens."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import UUID

import streamlit as st

from core.database import _create_supabase_client, get_sb
from core.state import get_current_user_id
from core.i18n import t


def _feedback_db():
    """Use a server-only credential for the RLS-protected feedback tables."""
    key = st.secrets.get("SUPABASE_SERVICE_ROLE_KEY", None) or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    url = st.secrets.get("SUPABASE_URL", None) or os.getenv("SUPABASE_URL")
    if key and url:
        return _create_supabase_client(url, key)
    return get_sb()


def bind_generated_resource(kind: str, resource_id: int | str, operation_id: str) -> bool:
    """Bind a successful AI call to the unedited library row it produced."""
    table = {"plan": "lesson_plans", "worksheet": "worksheets", "exam": "quick_exams"}.get(kind)
    actor = str(get_current_user_id() or "")
    try:
        operation_id = str(UUID(operation_id))
    except (ValueError, TypeError, AttributeError):
        return False
    if not table or not actor or not str(resource_id).isdigit():
        return False
    sb = _feedback_db()
    operations = (sb.table("classio_ai_operations").select("operation_id,started_at")
                  .eq("operation_id", operation_id).eq("actor_user_id", actor)
                  .eq("source", "streamlit").eq("modality", "text").eq("status", "success")
                  .limit(1).execute().data or [])
    resources = (sb.table(table).select("id,created_at").eq("id", resource_id)
                 .eq("user_id", actor).limit(1).execute().data or [])
    if not operations or not resources:
        return False
    start = datetime.fromisoformat(str(operations[0]["started_at"]).replace("Z", "+00:00"))
    created = datetime.fromisoformat(str(resources[0]["created_at"]).replace("Z", "+00:00"))
    if not -60 <= (created - start).total_seconds() <= 3600:
        return False
    result = sb.table("classio_generation_resources").upsert({
        "generation_id": operation_id, "actor_user_id": actor,
        "resource_type": kind, "resource_id": str(resource_id),
    }, on_conflict="generation_id").execute()
    return bool(result.data)


def render_generation_intent_question(kind: str, resource_id: int | str | None, *, surface: str, key_prefix: str) -> None:
    """Only ask about an AI generation while its saved content remains unedited."""
    if surface not in {"generation_preview", "resource_page"} or kind not in {"plan", "worksheet", "exam"} or not resource_id:
        return
    actor = str(get_current_user_id() or "")
    if not actor:
        return
    try:
        sb = _feedback_db()
        links = (sb.table("classio_generation_resources").select("generation_id,edited_at")
                 .eq("actor_user_id", actor).eq("resource_type", kind)
                 .eq("resource_id", str(resource_id)).limit(1).execute().data or [])
        if not links or links[0].get("edited_at"):
            return
        generation_id = str(links[0]["generation_id"])
        answers = (sb.table("classio_generation_intent_feedback").select("satisfied,reason")
                   .eq("generation_id", generation_id).eq("actor_user_id", actor)
                   .limit(1).execute().data or [])
        operation = (sb.table("classio_ai_operations").select("feature_name")
                     .eq("operation_id", generation_id).eq("actor_user_id", actor)
                     .limit(1).execute().data or [])
        attempts = (sb.table("classio_provider_attempts").select("model_reported,model_requested")
                    .eq("operation_id", generation_id).eq("status", "success")
                    .order("attempt_no", desc=True).limit(1).execute().data or [])
    except Exception:
        return
    if not operation:
        return

    def answer(satisfied: bool, reason: str | None = None) -> None:
        try:
            now = datetime.now(timezone.utc).isoformat()
            model = attempts[0] if attempts else {}
            payload = {
                "generation_id": generation_id, "operation_id": generation_id,
                "actor_user_id": actor, "source": "streamlit",
                "feature_name": str(operation[0].get("feature_name") or "unknown")[:80],
                "generation_mode": "ai", "prompt_version": "streamlit-beta-v1",
                "model_name": str(model.get("model_reported") or model.get("model_requested") or "")[:160],
                "resource_type": kind, "resource_id": str(resource_id),
                "feedback_surface": surface, "satisfied": satisfied,
                "reason": None if satisfied else reason, "answered_at": now, "updated_at": now,
            }
            sb.table("classio_generation_intent_feedback").upsert(payload, on_conflict="generation_id").execute()
            sb.table("classio_generation_intent_feedback_events").insert({
                "generation_id": generation_id, "actor_user_id": actor,
                "feedback_surface": surface, "satisfied": satisfied,
                "reason": None if satisfied else reason,
            }).execute()
            st.rerun()
        except Exception:
            st.error(t("generation_intent_failed"))

    selected = answers[0].get("satisfied") if answers else None
    st.markdown(f"**{t('generation_intent_question')}**")
    yes_col, no_col = st.columns(2)
    with yes_col:
        if st.button(t("generation_intent_yes"), key=f"{key_prefix}_{resource_id}_intent_yes", type="primary" if selected is True else "secondary"):
            answer(True)
    with no_col:
        if st.button(t("generation_intent_no"), key=f"{key_prefix}_{resource_id}_intent_no", type="primary" if selected is False else "secondary"):
            answer(False)
    if selected is False:
        st.caption(t("generation_intent_reason"))
        for reason, key in (("content", "generation_intent_content"), ("level", "generation_intent_level"), ("format", "generation_intent_format"), ("other", "generation_intent_other")):
            if st.button(t(key), key=f"{key_prefix}_{resource_id}_intent_{reason}"):
                answer(False, reason)


def _context_key(student_id: str, topic_id: int, recommendation_id: str, kind: str, resource_id: str) -> str:
    return ":".join((student_id, f"topic:{topic_id}" if topic_id else f"need:{recommendation_id}", kind, resource_id))


def hidden_recommendation_keys(student_id: str) -> set[str]:
    teacher_id = str(get_current_user_id() or "").strip()
    if not teacher_id or not student_id:
        return set()
    rows = (_feedback_db().table("classio_teacher_relevance_feedback")
            .select("context_key").eq("teacher_id", teacher_id)
            .eq("student_id", student_id).eq("active", True)
            .limit(2000).execute().data or [])
    return {str(row.get("context_key") or "") for row in rows}


def recommendation_resource_key(item: dict, resource: dict) -> str:
    row = resource.get("row") or {}
    return _context_key(
        str(item.get("student_id") or "").strip(),
        int(item.get("learning_program_topic_id") or 0),
        str(item.get("id") or "").strip(),
        str(resource.get("kind") or "").strip(),
        str(row.get("id") or "").strip(),
    )


def set_recommendation_relevance(exposure_id: str, *, reason: str | None) -> str:
    """Persist a contextual rejection or undo after verifying the exposure owner."""
    if reason is not None and reason not in {"wrong_topic", "student_unfit"}:
        raise ValueError("Invalid relevance reason")
    teacher_id = str(get_current_user_id() or "").strip()
    if not teacher_id or not exposure_id:
        raise ValueError("Recommendation feedback is unavailable")
    sb = _feedback_db()
    exposures = (sb.table("resource_exposures").select("exposure_id,student_id,resource_id,resource_type,learning_program_topic_id,context_json")
                 .eq("exposure_id", exposure_id).eq("teacher_id", teacher_id)
                 .eq("viewer_user_id", teacher_id).eq("exposure_type", "teacher_resource_recommendation")
                 .limit(1).execute().data or [])
    if not exposures:
        raise ValueError("Recommendation exposure is unavailable")
    exposure = exposures[0]
    kind = str(exposure.get("resource_type") or "")
    table = {"plan": "lesson_plans", "worksheet": "worksheets", "exam": "quick_exams", "video": "videos"}.get(kind)
    if not table:
        raise ValueError("Invalid resource kind")
    resource_id = str(exposure.get("resource_id") or "")
    rows = sb.table(table).select("id,user_id,is_public,status,updated_at").eq("id", resource_id).limit(1).execute().data or []
    if not rows or str(rows[0].get("status") or "active") == "archived" or (not rows[0].get("is_public") and str(rows[0].get("user_id") or "") != teacher_id):
        raise ValueError("Resource is unavailable")
    context = exposure.get("context_json") or {}
    student_id = str(exposure.get("student_id") or "")
    topic_id = int(exposure.get("learning_program_topic_id") or 0)
    recommendation_id = str(context.get("recommendation_id") or "")
    context_key = _context_key(student_id, topic_id, recommendation_id, kind, resource_id)
    existing = (sb.table("classio_teacher_relevance_feedback").select("id,created_at")
                .eq("teacher_id", teacher_id).eq("context_key", context_key).limit(1).execute().data or [])
    if reason is None and not existing:
        return context_key
    payload = {
        "teacher_id": teacher_id, "student_id": student_id, "context_key": context_key,
        "exposure_id": exposure_id, "resource_type": kind, "resource_id": resource_id,
        "resource_is_public": bool(rows[0].get("is_public")),
        "resource_updated_at": rows[0].get("updated_at"), "topic_id": topic_id or None,
        "recommendation_id": recommendation_id, "reason": reason,
        "active": reason is not None,
    }
    if existing:
        payload["created_at"] = existing[0]["created_at"]
    result = sb.table("classio_teacher_relevance_feedback").upsert(payload, on_conflict="teacher_id,context_key").execute()
    feedback_rows = result.data or []
    if not feedback_rows:
        raise RuntimeError("Relevance feedback was not confirmed")
    sb.table("classio_teacher_relevance_feedback_events").insert({
        "feedback_id": feedback_rows[0]["id"], "exposure_id": exposure_id,
        "teacher_id": teacher_id, "action": "rejected" if reason else "undone", "reason": reason,
    }).execute()
    return context_key
