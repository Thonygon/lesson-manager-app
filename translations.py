# ============================================================
# CLASS MANAGER - I18N / TRANSLATIONS
# ------------------------------------------------------------
# Language payloads live in separate modules to keep this public
# import point small while preserving `from translations import I18N`.

from typing import Dict

from translations_en import EN
from translations_es import ES
from translations_tr import TR

I18N: Dict[str, Dict[str, str]] = {
    "en": EN,
    "es": ES,
    "tr": TR,
}

__all__ = ["I18N"]
