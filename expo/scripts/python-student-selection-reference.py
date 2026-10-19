"""Frozen-input comparison against Streamlit's actual student selection helpers."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "streamlit"))
from helpers import student_recommendations as recommendations  # noqa: E402

payload = json.load(sys.stdin)
program_signals = {"program_scopes": payload["program_scopes"]}
ranked = []
for candidate in payload["candidates"]:
    row = candidate["row"]
    kind = candidate["kind"]
    score = candidate["score"]
    scopes = recommendations._program_scopes_for_resource(row, program_signals, None)
    for scope in scopes or [{}]:
        ranked.append(recommendations._normalize_recommendation_row(
            row, kind, recommendations._scope_adjusted_resource_score(row, kind, score, scope), [], None, None, scope
        ))

ranked.sort(key=lambda item: (-item["score"], item["topic"].casefold(), item["title"].casefold()))
seen = set()
deduped = []
for item in ranked:
    key = (
        recommendations._recommendation_scope_key(item), recommendations.normalize_subject(item["subject"]),
        item["resource_type"], item["topic"].casefold(), item["exercise_type"].casefold(),
    )
    if key not in seen:
        seen.add(key)
        deduped.append(item)
selected = recommendations._select_subject_balanced_recommendations(
    deduped, set(payload["active_scope_keys"]), limit=payload["limit"]
)
json.dump([
    [str(item["id"]), item["learning_program_assignment_id"], item["learning_program_topic_id"], item["score"]]
    for item in selected
], sys.stdout)
