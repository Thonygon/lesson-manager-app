from __future__ import annotations

from dataclasses import dataclass

import streamlit as st


@dataclass(frozen=True)
class GenerationSurfaceCapabilities:
    name: str
    page_key: str
    user_face: str
    allow_program_context: bool = True
    allow_student_personalization: bool = True
    allow_generation_recommendations: bool = True
    allow_previous_program_chain: bool = True
    allow_library_reuse_checks: bool = True
    allow_direct_library_save: bool = True
    allow_signup_staging: bool = False
    allow_template_mode: bool = True
    enforce_platform_usage_limits: bool = True
    anonymous_ai_limit: int | None = None


SMART_TOOLS_CAPABILITIES = GenerationSurfaceCapabilities(
    name="smart_tools",
    page_key="smart_tools",
    user_face="teacher",
)


EXPLORER_CAPABILITIES = GenerationSurfaceCapabilities(
    name="explorer",
    page_key="explore",
    user_face="anonymous",
    allow_program_context=False,
    allow_student_personalization=False,
    allow_generation_recommendations=False,
    allow_previous_program_chain=False,
    allow_library_reuse_checks=False,
    allow_direct_library_save=False,
    allow_signup_staging=True,
    allow_template_mode=False,
    enforce_platform_usage_limits=False,
    anonymous_ai_limit=1,
)


def resolve_effective_subject(subject: str, custom_subject_name: str = "") -> str:
    return str(custom_subject_name or "").strip() if str(subject or "").strip() == "other" else str(subject or "").strip()


def anonymous_ai_remaining(counter_key: str, *, limit: int | None) -> int | None:
    if limit is None:
        return None
    used = int(st.session_state.get(counter_key, 0) or 0)
    return max(0, int(limit) - used)


def anonymous_ai_limit_reached(counter_key: str, *, limit: int | None) -> bool:
    remaining = anonymous_ai_remaining(counter_key, limit=limit)
    return remaining is not None and remaining <= 0


def mark_anonymous_ai_generation(counter_key: str) -> int:
    updated = int(st.session_state.get(counter_key, 0) or 0) + 1
    st.session_state[counter_key] = updated
    return updated
