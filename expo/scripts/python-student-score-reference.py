"""Evaluate Streamlit's live resource score over an isolated frozen profile."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "streamlit"))
from helpers import student_recommendations as recommendations  # noqa: E402

payload = json.load(sys.stdin)
profile = {
    "primary_subjects": [], "subject_need": {}, "topic_need": {}, "exercise_need": {},
    "subject_attempts": {}, "subject_level": {}, "subject_stage": {}, "default_stage": "",
    "overall_accuracy": {},
    "program_signals": {
        "subjects": set(), "subject_levels": {}, "subject_stages": {},
        "active_topic_ids": set(), "next_topic_ids": set(), "pending_topic_ids": set(), "review_topic_ids": set(),
        "topic_tokens": set(), "next_topic_tokens": set(), "pending_topic_tokens": set(), "review_topic_tokens": set(),
        "next_topics": [], "worksheet_types": set(), "exam_types": set(),
    },
    "assignment_behavior": {},
    "assignment_signals": {
        "resource_assignments": {}, "active_assigned_topic_tokens": set(), "unseen_video_topic_tokens": set(),
    },
}
for key, value in payload.get("program_signals", {}).items():
    if key.endswith("_ids") or key.endswith("_tokens") or key in {"subjects", "worksheet_types", "exam_types"}:
        profile["program_signals"][key] = set(value)
    else:
        profile["program_signals"][key] = value
profile.update(payload.get("profile_overrides", {}))
assignment_signals = payload.get("assignment_signals", {})
if assignment_signals:
    profile["assignment_signals"] = {
        "resource_assignments": {
            (item["kind"], str(item["id"])): {"is_completed": item["is_completed"], "is_unseen": item["is_unseen"]}
            for item in assignment_signals.get("resource_assignments", [])
        },
        "active_assigned_topic_tokens": set(assignment_signals.get("active_assigned_topic_tokens", [])),
        "unseen_video_topic_tokens": set(assignment_signals.get("unseen_video_topic_tokens", [])),
    }
behavior = payload.get("assignment_behavior", {})
if behavior:
    profile["assignment_behavior"] = {**behavior, "recent_teacher_topics": set(behavior.get("recent_teacher_topics", []))}
recommendations.get_current_user_id = lambda: ""
recommendations.topic_resource_alignment_features = lambda *_args, **_kwargs: {
    "explicit_topic_match": 0.0, "explicit_topic_support": 0.0, "direct_topic_link": 0.0,
    "topic_kind_prior": 0.0, "topic_match_ambiguity": 0.0,
}
scores = []
for candidate in payload["candidates"]:
    recommendations.score_student_resource_candidate = lambda *_args, **_kwargs: candidate["ml_score"]
    score, _reasons, _meta = recommendations._resource_feature_score(candidate["row"], candidate["kind"], profile)
    scores.append(score)
json.dump(scores, sys.stdout)
