"""Build finite subject-template snapshots from the Streamlit source."""

import json
from pathlib import Path

import streamlit as st
from helpers import lesson_planner as planner


TOPIC = "zztopicmarker"
SUBJECTS = ("english", "spanish", "mathematics", "science", "music", "study_skills")
LANGUAGES = ("en", "es", "tr")
STAGES = tuple(planner.LEARNER_STAGES)
PURPOSES = tuple(planner.LESSON_PURPOSES)
BANK_TOPICS = ("travel", "food")


def output(subject: str, stage: str, level: str, purpose: str, topic: str) -> dict:
    return planner.normalize_planner_output(planner.build_quick_lesson_plan(subject, stage, level, purpose, topic))


def main() -> None:
    original_bank = planner._get_language_bank_entry
    snapshots = {}
    fixtures = []
    try:
        for subject in SUBJECTS:
            snapshots[subject] = {}
            levels = planner.LANGUAGE_LEVELS if subject in ("english", "spanish") else planner.ACADEMIC_BANDS
            for language in LANGUAGES:
                st.session_state["ui_lang"] = language
                snapshots[subject][language] = {}
                for stage in STAGES:
                    snapshots[subject][language][stage] = {}
                    for level in levels:
                        snapshots[subject][language][stage][level] = {}
                        for purpose in PURPOSES:
                            variants = {"default": output(subject, stage, level, purpose, TOPIC)}
                            if subject in ("english", "spanish"):
                                for bank_topic in BANK_TOPICS:
                                    planner._get_language_bank_entry = lambda topic, level, material_lang, bank_topic=bank_topic: original_bank(bank_topic, level, material_lang)
                                    variants[bank_topic] = output(subject, stage, level, purpose, TOPIC)
                                    planner._get_language_bank_entry = original_bank
                            snapshots[subject][language][stage][level][purpose] = variants
        for subject, language, stage, level, purpose, topic in (
            ("spanish", "en", "adult_stage", "A2", "introduce_concept", "Travel"),
            ("english", "tr", "lower_secondary", "B1", "practice_skill", "food"),
            ("mathematics", "es", "upper_primary", "beginner_band", "review_topic", "Fractions"),
            ("science", "tr", "lower_secondary", "intermediate_band", "diagnose_difficulty", "Photosynthesis"),
            ("music", "en", "adult_stage", "advanced_band", "discussion_exploration", "Rhythm"),
            ("study_skills", "es", "early_primary", "beginner_band", "practice_skill", "Time management"),
        ):
            st.session_state["ui_lang"] = language
            fixtures.append({"input": {"subject": subject, "planLanguage": language, "stage": stage, "level": level, "purpose": purpose, "topic": topic}, "expected": output(subject, stage, level, purpose, topic)})
    finally:
        planner._get_language_bank_entry = original_bank
    unique = []
    identities = {}
    index = {}
    for subject, languages in snapshots.items():
        index[subject] = {}
        for language, stages in languages.items():
            index[subject][language] = {}
            for stage, levels in stages.items():
                index[subject][language][stage] = {}
                for level, purposes in levels.items():
                    index[subject][language][stage][level] = {}
                    for purpose, variants in purposes.items():
                        index[subject][language][stage][level][purpose] = {}
                        for variant, document in variants.items():
                            identity = json.dumps(document, ensure_ascii=False, separators=(",", ":"))
                            if identity not in identities:
                                identities[identity] = len(unique)
                                unique.append(document)
                            index[subject][language][stage][level][purpose][variant] = identities[identity]
    root = Path(__file__).resolve().parents[1]
    (root / "src/server/source-subject-plan-templates.json").write_text(json.dumps({"index": index, "templates": unique}, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    (root / "scripts/fixtures/subject-plan-expected.json").write_text(json.dumps(fixtures, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print("Wrote subject plan snapshots and fixtures")


if __name__ == "__main__":
    main()
