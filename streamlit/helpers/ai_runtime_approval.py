"""Fail-closed human release gate for provider/model/prompt combinations."""

from __future__ import annotations

import os
import streamlit as st
from core.database import _create_supabase_client

TEXT_PROMPT_VERSION = "streamlit-generation-v1"
IMAGE_PROMPT_VERSION = "streamlit-image-v1"


def require_ai_runtime_approval(surface: str, provider: str, model: str, prompt_version: str) -> None:
    try:
        url = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
        key = (st.secrets.get("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
               or st.secrets.get("SUPABASE_KEY") or os.getenv("SUPABASE_KEY"))
    except Exception:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("AI release approval could not be verified")
    try:
        approved = (_create_supabase_client(url, key)
                    .rpc("classio_is_ai_runtime_approved", {
                        "p_surface": surface, "p_provider": provider,
                        "p_model": model, "p_prompt_version": prompt_version,
                    }).execute().data)
    except Exception as exc:
        raise RuntimeError("AI release approval could not be verified") from exc
    if approved is not True:
        raise RuntimeError("AI generation is awaiting release approval")


def record_streamlit_fallback(feature_name: str, reason: str) -> None:
    """Best-effort metadata event; a telemetry outage must not hide a template."""
    try:
        url = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
        key = st.secrets.get("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if url and key:
            (_create_supabase_client(url, key).table("classio_ai_fallback_events")
             .insert({"source": "streamlit", "feature_name": feature_name,
                      "requested_mode": "ai", "effective_mode": "template", "reason": reason})
             .execute())
    except Exception:
        pass
