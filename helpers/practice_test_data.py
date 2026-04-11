# CLASSIO — Smart Practice: Demo / Test Activities
# ============================================================
# Localised sample exercises for testing without Supabase.
# Used by the "Try Demo" button on the Smart Practice page.
# ============================================================

from core.i18n import t


def _mc_demo() -> dict:
    return {
        "title": t("demo_mc_title"),
        "instructions": t("demo_mc_instructions"),
        "source_type": "demo",
        "source_id": "demo_english_mc",
        "exercises": [
            {
                "type": "multiple_choice",
                "title": t("demo_mc_section_title"),
                "instructions": "",
                "questions": [
                    {
                        "stem": t("demo_mc_q1_stem"),
                        "options": [
                            t("demo_mc_q1_opt_1"),
                            t("demo_mc_q1_opt_2"),
                            t("demo_mc_q1_opt_3"),
                            t("demo_mc_q1_opt_4"),
                        ],
                    },
                    {
                        "stem": t("demo_mc_q2_stem"),
                        "options": [
                            t("demo_mc_q2_opt_1"),
                            t("demo_mc_q2_opt_2"),
                            t("demo_mc_q2_opt_3"),
                            t("demo_mc_q2_opt_4"),
                        ],
                    },
                    {
                        "stem": t("demo_mc_q3_stem"),
                        "options": [
                            t("demo_mc_q3_opt_1"),
                            t("demo_mc_q3_opt_2"),
                            t("demo_mc_q3_opt_3"),
                            t("demo_mc_q3_opt_4"),
                        ],
                    },
                    {
                        "stem": t("demo_mc_q4_stem"),
                        "options": [
                            t("demo_mc_q4_opt_1"),
                            t("demo_mc_q4_opt_2"),
                            t("demo_mc_q4_opt_3"),
                            t("demo_mc_q4_opt_4"),
                        ],
                    },
                    {
                        "stem": t("demo_mc_q5_stem"),
                        "options": [
                            t("demo_mc_q5_opt_1"),
                            t("demo_mc_q5_opt_2"),
                            t("demo_mc_q5_opt_3"),
                            t("demo_mc_q5_opt_4"),
                        ],
                    },
                ],
                "answers": [
                    t("demo_mc_q1_answer"),
                    t("demo_mc_q2_answer"),
                    t("demo_mc_q3_answer"),
                    t("demo_mc_q4_answer"),
                    t("demo_mc_q5_answer"),
                ],
            }
        ],
    }


def _tf_demo() -> dict:
    return {
        "title": t("demo_tf_title"),
        "instructions": t("demo_tf_instructions"),
        "source_type": "demo",
        "source_id": "demo_science_tf",
        "exercises": [
            {
                "type": "true_false",
                "title": t("demo_tf_section_title"),
                "instructions": "",
                "source_text": "",
                "questions": [
                    {"text": t("demo_tf_q1")},
                    {"text": t("demo_tf_q2")},
                    {"text": t("demo_tf_q3")},
                    {"text": t("demo_tf_q4")},
                    {"text": t("demo_tf_q5")},
                ],
                "answers": ["True", "False", "True", "False", "True"],
            }
        ],
    }


def _math_demo() -> dict:
    return {
        "title": t("demo_math_title"),
        "instructions": t("demo_math_instructions"),
        "source_type": "demo",
        "source_id": "demo_math_fib",
        "exercises": [
            {
                "type": "fill_in_blank",
                "title": t("demo_math_section_title"),
                "instructions": "",
                "questions": [
                    {"text": t("demo_math_q1")},
                    {"text": t("demo_math_q2")},
                    {"text": t("demo_math_q3")},
                    {"text": t("demo_math_q4")},
                    {"text": t("demo_math_q5")},
                ],
                "answers": ["6", "6", t("demo_math_q3_answer"), "1", "6"],
            }
        ],
    }


# Stable IDs for tracking demo completion
DEMO_IDS = ["demo_english_mc", "demo_science_tf", "demo_math_fib"]


def get_demo_activities():
    """Return demo activities with localised content (must be called at render time)."""
    return [
        {
            "id": "demo_english_mc",
            "label": t("multiple_choice"),
            "emoji": "🇬🇧",
            "exercise_data": _mc_demo(),
            "meta": {"subject": "english", "topic": t("demo_topic_vocabulary"), "level": "A2"},
        },
        {
            "id": "demo_science_tf",
            "label": t("true_false"),
            "emoji": "🔬",
            "exercise_data": _tf_demo(),
            "meta": {"subject": "science", "topic": t("demo_topic_general_science"), "level": "B1"},
        },
        {
            "id": "demo_math_fib",
            "label": t("fill_in_blank"),
            "emoji": "🔢",
            "exercise_data": _math_demo(),
            "meta": {"subject": "mathematics", "topic": t("demo_topic_matrix_operations"), "level": "B1"},
        },
    ]


DEMO_ACTIVITIES = None
