"""Train Streamlit's live student resource model over a frozen workspace."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "streamlit"))
from helpers import recommendation_models as models  # noqa: E402

payload = json.load(sys.stdin)
signals = payload["program_signals"]
for key in ("subjects", "topic_tokens", "active_topic_ids"):
    signals[key] = set(signals.get(key, []))
models._load_student_history_rows = lambda _student_id: {
    "practice_sessions": payload["sessions"],
    "teacher_assignments": payload["assignments"],
    "recommendation_activity": payload["feedback"],
}
models.topic_resource_alignment_features = lambda *_args, **_kwargs: {
    "explicit_topic_match": 0.0, "explicit_topic_support": 0.0, "direct_topic_link": 0.0,
    "topic_kind_prior": 0.0, "topic_match_ambiguity": 0.0,
}
model = models.build_student_recommendation_model({"program_signals": signals}, student_id="fixture")
json.dump(model["weights"], sys.stdout)
