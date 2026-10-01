"""Snapshot the read-only Streamlit general lesson-plan engine for Expo."""

import json
from pathlib import Path

from helpers import lesson_planner as planner


TOPIC = "zztopicmarker"
LEVEL = "zzlevelmarker"
PURPOSES = planner.LESSON_PURPOSES
LANGUAGES = ("en", "es", "tr")


def main() -> None:
    original_language = planner.get_plan_language
    try:
        snapshots = {}
        for language in LANGUAGES:
            planner.get_plan_language = lambda language=language: language
            snapshots[language] = {
                purpose: planner.normalize_planner_output(
                    planner.build_quick_lesson_plan(
                        subject="other",
                        learner_stage="adult_stage",
                        level_or_band=LEVEL,
                        lesson_purpose=purpose,
                        topic=TOPIC,
                    )
                )
                for purpose in PURPOSES
            }
    finally:
        planner.get_plan_language = original_language
    target = Path(__file__).resolve().parents[1] / "src" / "server" / "source-general-plan-templates.json"
    target.write_text(json.dumps(snapshots, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    cases = [
        ("en", "introduce_concept", "Creative writing", "beginner_band"),
        ("es", "review_topic", "Arte / cultura", "intermediate_band"),
        ("tr", "diagnose_difficulty", "study habits", "advanced_band"),
    ]
    fixtures = []
    for language, purpose, topic, level in cases:
        planner.get_plan_language = lambda language=language: language
        expected = planner.normalize_planner_output(planner.build_quick_lesson_plan("other", "adult_stage", level, purpose, topic))
        fixtures.append({"input": {"topic": topic, "level": level, "purpose": purpose, "planLanguage": language}, "expected": expected})
    fixture_target = Path(__file__).resolve().parent / "fixtures" / "general-plan-expected.json"
    fixture_target.parent.mkdir(parents=True, exist_ok=True)
    fixture_target.write_text(json.dumps(fixtures, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Wrote {target}")


if __name__ == "__main__":
    main()
