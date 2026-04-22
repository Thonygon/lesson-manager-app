# CLASSIO — Smart Practice: Demo / Test Activities
# ============================================================
# Localised sample exercises for testing without Supabase.
# Used by the "Try Demo" button on the Smart Practice page.
# ============================================================

import base64
import os
import streamlit as st
from core.i18n import t

_DEMO_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "demo")


@st.cache_data(show_spinner=False)
def _load_or_generate_demo_image(demo_id: str, prompt: str) -> str:
    """Return a data:image/… URL from disk cache only (no on-the-fly generation)."""
    for ext, mime in [("jpg", "image/jpeg"), ("png", "image/png")]:
        path = os.path.join(_DEMO_DIR, f"{demo_id}.{ext}")
        if os.path.isfile(path):
            with open(path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode("ascii")
            return f"data:{mime};base64,{encoded}"
    return ""


def generate_demo_images() -> None:
    """Pre-generate demo images to static/demo/. Run once via CLI."""
    from helpers.visual_support import _generate_ai_image_data_url, data_uri_to_bytes

    os.makedirs(_DEMO_DIR, exist_ok=True)
    for demo_id, prompt in [
        ("demo_english_mc", _MC_IMAGE_PROMPT),
        ("demo_english_tf", _TF_IMAGE_PROMPT),
        ("demo_math", _MATH_IMAGE_PROMPT),
    ]:
        path = os.path.join(_DEMO_DIR, f"{demo_id}.png")
        if os.path.isfile(path):
            print(f"  ✓ {demo_id} already cached")
            continue
        print(f"  ⏳ Generating {demo_id} …")
        try:
            data_url = _generate_ai_image_data_url(prompt)
            if data_url:
                image_bytes = data_uri_to_bytes(data_url)
                if image_bytes:
                    with open(path, "wb") as f:
                        f.write(image_bytes)
                    print(f"  ✓ {demo_id} saved")
                    continue
        except Exception as exc:
            print(f"  ✗ {demo_id} failed: {exc}")
        print(f"  ✗ {demo_id} — no image generated")


def _demo_visual_support(demo_id: str, prompt: str, caption: str) -> dict | None:
    """Build a visual_support dict with a disk-cached image."""
    data_url = _load_or_generate_demo_image(demo_id, prompt)
    if not data_url:
        return None
    return {
        "placement": "worksheet_intro",
        "generator": "classio_demo_visual_v1",
        "status": "ready",
        "purpose": "instructional_support",
        "visual_role": "demo_picture_support",
        "caption": caption,
        "alt_text": caption,
        "image_prompt": prompt,
        "image_data_url": data_url,
        "subject": "",
        "learner_stage": "lower_primary",
    }


# ── Image prompts (language-neutral, describe the visual concept) ──

_MC_IMAGE_PROMPT = (
    "Use case: illustration-story\n"
    "Asset type: worksheet vocabulary support image\n"
    "Primary request: Create a clean picture board showing 5 everyday objects: "
    "a red apple, an open book, a wooden chair, a round wall clock, and a colorful umbrella.\n"
    "Style/medium: simple, warm educational illustration with clean outlines\n"
    "Composition/framing: 5 separate picture tiles arranged in a neat row on a white background\n"
    "Lighting/mood: bright, friendly, inviting\n"
    "Text (verbatim): none\n"
    "Constraints: no words, no letters, no labels, each object must be clearly recognizable\n"
    "Avoid: abstract icons, decorative filler, watermark"
)

_TF_IMAGE_PROMPT = (
    "Use case: illustration-story\n"
    "Asset type: worksheet nature scene\n"
    "Primary request: Create an educational scene showing different weather elements: "
    "a bright sun in one part of the sky, rain clouds with raindrops, a rainbow, "
    "green trees, and a small pond reflecting the sky.\n"
    "Style/medium: clear, friendly educational illustration\n"
    "Composition/framing: one coherent outdoor landscape scene\n"
    "Lighting/mood: bright and cheerful with visible weather details\n"
    "Text (verbatim): none\n"
    "Constraints: no text, no labels, all weather elements must be clearly visible and identifiable\n"
    "Avoid: decorative filler, watermark"
)

_MATH_IMAGE_PROMPT = (
    "Use case: infographic-diagram\n"
    "Asset type: educational shapes diagram\n"
    "Primary request: Create a colorful educational diagram showing basic geometric shapes: "
    "3 red circles, 4 blue squares, 2 green triangles, and 5 yellow stars, "
    "each group clearly separated.\n"
    "Style/medium: clean, simple educational illustration with bold colors\n"
    "Composition/framing: groups of shapes arranged on a white background, easy to count\n"
    "Lighting/mood: bright, clear, print-friendly\n"
    "Text (verbatim): none\n"
    "Constraints: no labels, no numbers, shapes must be easy to count, uniform size within each group\n"
    "Avoid: overlapping shapes, decorative filler, watermark"
)


def _mc_demo() -> dict:
    vs = _demo_visual_support("demo_english_mc", _MC_IMAGE_PROMPT, t("demo_mc_section_title"))
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
                "visual_support": vs,
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
    vs = _demo_visual_support("demo_science_tf", _TF_IMAGE_PROMPT, t("demo_tf_section_title"))
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
                "visual_support": vs,
                "questions": [
                    {"text": t("demo_tf_q1")},
                    {"text": t("demo_tf_q2")},
                    {"text": t("demo_tf_q3")},
                    {"text": t("demo_tf_q4")},
                    {"text": t("demo_tf_q5")},
                ],
                "answers": ["True", "False", "True", "True", "False"],
            }
        ],
    }


def _math_demo() -> dict:
    vs = _demo_visual_support("demo_math_fib", _MATH_IMAGE_PROMPT, t("demo_math_section_title"))
    return {
        "title": t("demo_math_title"),
        "instructions": t("demo_math_instructions"),
        "source_type": "demo",
        "source_id": "demo_math_fib",
        "exercises": [
            {
                "type": "short_answer",
                "title": t("demo_math_section_title"),
                "instructions": "",
                "visual_support": vs,
                "questions": [
                    {"text": t("demo_math_q1")},
                    {"text": t("demo_math_q2")},
                    {"text": t("demo_math_q3")},
                    {"text": t("demo_math_q4")},
                    {"text": t("demo_math_q5")},
                ],
                "answers": ["3", "4", "2", "5", "14"],
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
            "meta": {"subject": "english", "topic": t("demo_topic_vocabulary"), "level": "A1"},
        },
        {
            "id": "demo_science_tf",
            "label": t("true_false"),
            "emoji": "🌤️",
            "exercise_data": _tf_demo(),
            "meta": {"subject": "science", "topic": t("demo_topic_nature"), "level": "A1"},
        },
        {
            "id": "demo_math_fib",
            "label": t("short_answer"),
            "emoji": "🔢",
            "exercise_data": _math_demo(),
            "meta": {"subject": "mathematics", "topic": t("demo_topic_shapes"), "level": "A1"},
        },
    ]


DEMO_ACTIVITIES = None
