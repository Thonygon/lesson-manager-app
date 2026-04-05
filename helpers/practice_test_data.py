# CLASSIO — Smart Practice: Demo / Test Activities
# ============================================================
# Hardcoded sample exercises for local testing without Supabase.
# Used by the "Try Demo" button on the Smart Practice page.
# ============================================================

from core.i18n import t

# ── Multiple-choice demo (English) ─────────────────────────────
_MC_DEMO = {
    "title": "English Vocabulary Quiz",
    "instructions": "Choose the best answer for each question.",
    "source_type": "demo",
    "source_id": "demo_english_mc",
    "exercises": [
        {
            "type": "multiple_choice",
            "title": "Everyday Vocabulary",
            "instructions": "",
            "questions": [
                {
                    "stem": "What is the synonym of 'happy'?",
                    "options": ["Sad", "Joyful", "Angry", "Tired"],
                },
                {
                    "stem": "Which word means 'to start'?",
                    "options": ["End", "Begin", "Continue", "Stop"],
                },
                {
                    "stem": "Choose the correct meaning of 'enormous'.",
                    "options": ["Tiny", "Very large", "Medium", "Narrow"],
                },
                {
                    "stem": "What is the opposite of 'ancient'?",
                    "options": ["Old", "Modern", "Historic", "Classic"],
                },
                {
                    "stem": "'She is reading a novel.' What is a novel?",
                    "options": ["A newspaper", "A long fictional book", "A recipe", "A poem"],
                },
            ],
            "answers": ["Joyful", "Begin", "Very large", "Modern", "A long fictional book"],
        }
    ],
}


# ── True / False demo (Science) ─────────────────────────────────
_TF_DEMO = {
    "title": "Science True or False",
    "instructions": "Decide whether each statement is True or False.",
    "source_type": "demo",
    "source_id": "demo_science_tf",
    "exercises": [
        {
            "type": "true_false",
            "title": "General Science Facts",
            "instructions": "",
            "source_text": "",
            "questions": [
                {"text": "Water boils at 100 °C at sea level."},
                {"text": "The Moon is larger than the Earth."},
                {"text": "Sound travels faster in water than in air."},
                {"text": "Humans have four lungs."},
                {"text": "Diamonds are made of carbon."},
            ],
            "answers": ["True", "False", "True", "False", "True"],
        }
    ],
}


# ── Fill-in-the-blank demo (Mathematics — Matrices) ────────────
_MATH_DEMO = {
    "title": "Mathematics — Matrix Operations",
    "instructions": "Solve each matrix operation and type the answer.",
    "source_type": "demo",
    "source_id": "demo_math_fib",
    "exercises": [
        {
            "type": "fill_in_blank",
            "title": "Simple Matrix Operations",
            "instructions": "",
            "questions": [
                {"text": "If A = [[1, 2], [3, 4]] and B = [[5, 6], [7, 8]], what is the element in row 1, column 1 of A + B? Answer: ____"},
                {"text": "If A = [[2, 0], [0, 3]], what is the determinant of A? Answer: ____"},
                {"text": "If A = [[1, 0], [0, 1]], what is A called? (Answer: identity) ____"},
                {"text": "If A = [[4, 2], [1, 3]], what is the element in row 2, column 1? Answer: ____"},
                {"text": "A 3×2 matrix has how many elements in total? Answer: ____"},
            ],
            "answers": ["6", "6", "identity", "1", "6"],
        }
    ],
}


# Stable IDs for tracking demo completion
DEMO_IDS = ["demo_english_mc", "demo_science_tf", "demo_math_fib"]


# ── Public list used by the browse tab ──────────────────────────
def get_demo_activities():
    """Return demo activities with translated labels (must be called at render time)."""
    return [
        {
            "id": "demo_english_mc",
            "label": t("multiple_choice"),
            "emoji": "🇬🇧",
            "exercise_data": _MC_DEMO,
            "meta": {"subject": "english", "topic": "Vocabulary", "level": "A2"},
        },
        {
            "id": "demo_science_tf",
            "label": t("true_false"),
            "emoji": "🔬",
            "exercise_data": _TF_DEMO,
            "meta": {"subject": "science", "topic": "General Science", "level": "B1"},
        },
        {
            "id": "demo_math_fib",
            "label": t("fill_in_blank"),
            "emoji": "🔢",
            "exercise_data": _MATH_DEMO,
            "meta": {"subject": "mathematics", "topic": "Matrix Operations", "level": "B1"},
        },
    ]


# Keep backward-compatible alias
DEMO_ACTIVITIES = None  # use get_demo_activities() instead
