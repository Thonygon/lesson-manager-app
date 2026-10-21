"""Only approved educational signals may leave Classio for an AI provider."""

from __future__ import annotations

import hashlib
from typing import Any


def minimize_student_profile_for_ai(profile: dict[str, Any] | None) -> dict[str, Any]:
    source = profile or {}
    if not source:
        return {}
    result: dict[str, Any] = {}
    internal_id = str(source.get("student_user_id") or "").strip()
    if internal_id:
        # A numeric, non-reversible per-student reference. The provider never
        # receives the UUID or the name; no local lookup table is exported.
        result["learner_id"] = int.from_bytes(
            hashlib.sha256(internal_id.encode("utf-8")).digest()[:8], "big"
        )
    for key in ("learner_stage", "level_or_band", "native_language", "subject_focus"):
        value = source.get(key)
        if isinstance(value, str) and value.isascii() and value.replace("_", "").replace("-", "").isalnum() and len(value) <= 40:
            result[key] = value
    for key in ("completed_assignments", "recent_average_score_pct"):
        value = source.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 10000:
            result[key] = value
    return result
