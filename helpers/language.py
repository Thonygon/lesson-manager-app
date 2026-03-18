import streamlit as st
import pycountry
from core.i18n import t
from core.database import load_table, register_cache
from typing import List, Optional, Tuple

# 07.3) LANGUAGE HELPERS
# =========================
LANG_EN = "English"
LANG_ES = "Spanish"
LANG_BOTH = "English,Spanish"
ALLOWED_LANGS = {LANG_EN, LANG_ES, LANG_BOTH}
ALLOWED_LESSON_LANGS = {LANG_EN, LANG_ES, LANG_BOTH}
DEFAULT_PACKAGE_LANGS = [LANG_ES]


def pack_languages(selected: List[str]) -> str:
    s = [x for x in selected if x in (LANG_EN, LANG_ES)]
    s = sorted(set(s), key=lambda z: 0 if z == LANG_EN else 1)
    if len(s) == 2:
        return LANG_BOTH
    if len(s) == 1:
        return s[0]
    return LANG_ES


def unpack_languages(value: str) -> List[str]:
    v = str(value or "").strip()
    if v == LANG_BOTH:
        return [LANG_EN, LANG_ES]
    if v in (LANG_EN, LANG_ES):
        return [v]
    return [LANG_ES]


def allowed_lesson_language_from_package(languages_value: str) -> Tuple[List[str], Optional[str]]:
    langs = unpack_languages(languages_value)
    if len(langs) == 1:
        return [langs[0]], langs[0]
    return [LANG_EN, LANG_ES], None


def translate_status(val: str) -> str:
    if not val:
        return ""
    key_map = {
        "dropout": "dropout",
        "finished": "finished",
        "mismatch": "mismatch",
        "almost_finished": "almost_finished",
        "active": "active",
    }
    return t(key_map.get(str(val).strip().casefold(), str(val)))


def translate_modality_value(x: str) -> str:
    v = str(x or "").strip().casefold()
    if v == "online":
        return t("online")
    if v == "offline":
        return t("offline")
    return str(x or "").strip()


def translate_language_value(x: str) -> str:
    v = str(x or "").strip()
    if v == LANG_EN:
        return t("english")
    if v == LANG_ES:
        return t("spanish")
    if v == LANG_BOTH:
        return t("both")
    if v.casefold() in ("unknown", ""):
        return t("unknown")
    return v

# =========================
