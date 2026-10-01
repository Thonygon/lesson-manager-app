# CLASSIO — Font Manager
# ============================================================
"""
Centralised font registry for PDF and DOCX exports.

Two categories of fonts:

1. **Embedded** — TTF/OTF files shipped in static/fonts/.
   Used for both PDF (ReportLab) and DOCX generation.
   Currently: DejaVu Sans, Open Sans, Yavuz Bağıd Dik Temel.

2. **Named** — no local font file bundled.
   For DOCX the font-family name is set directly (Word resolves it).
   For PDF the engine falls back to DejaVu Sans automatically.
   Currently: Arial, Calibri, Times New Roman, Comic Sans MS.

All 7 options are always visible in the UI.
"""
import os

_FONT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, "static", "fonts")
)

# ── Font registry ────────────────────────────────────────────────────
#
#   embedded : True  → TTF/OTF files live in static/fonts/
#   embedded : False → named-only; PDF falls back to DejaVu Sans
#   regular / bold   → filenames inside _FONT_DIR (embedded) or None
#   docx_name        → font-family string written into .docx XML
#

FONT_REGISTRY: dict[str, dict] = {
    # ── Embedded fonts (local files) ──────────────────────────
    "dejavu": {
        "label_key": "font_label_dejavu",
        "embedded": True,
        "regular": "DejaVuSans.ttf",
        "bold": "DejaVuSans-Bold.ttf",
        "docx_name": "DejaVu Sans",
    },
    "open_sans": {
        "label_key": "font_label_open_sans",
        "embedded": True,
        "regular": "OpenSans-Regular.ttf",
        "bold": "OpenSans-Bold.ttf",
        "docx_name": "Open Sans",
    },
    "yavuz": {
        "label_key": "font_label_yavuz",
        "embedded": True,
        "regular": "Yavuz-Bagis-dik-temel-harfler.otf",
        "bold": "Yavuz-Bagis-dik-temel-harfler.otf",   # no bold variant
        "docx_name": "Yavuz Bagis Dik Temel",
    },
    # ── Named-only fonts (DOCX name only, PDF → DejaVu) ──────
    "arial": {
        "label_key": "font_label_arial",
        "embedded": False,
        "regular": None,
        "bold": None,
        "docx_name": "Arial",
    },
    "calibri": {
        "label_key": "font_label_calibri",
        "embedded": False,
        "regular": None,
        "bold": None,
        "docx_name": "Calibri",
    },
    "times": {
        "label_key": "font_label_times",
        "embedded": False,
        "regular": None,
        "bold": None,
        "docx_name": "Times New Roman",
    },
    "comic_sans": {
        "label_key": "font_label_comic_sans",
        "embedded": False,
        "regular": None,
        "bold": None,
        "docx_name": "Comic Sans MS",
    },
}

DEFAULT_FONT_KEY = "dejavu"
DEFAULT_SIZE_KEY = "standard"

# ── Size presets ─────────────────────────────────────────────────────
# Each preset returns title / section / body sizes used by pdf_styles.py

SIZE_PRESETS: dict[str, dict] = {
    "compact": {
        "label_key": "font_size_compact",
        "title": 14,
        "section": 12,
        "body": 10,
        "leading_ratio": 1.15,
    },
    "standard": {
        "label_key": "font_size_standard",
        "title": 14,
        "section": 14,
        "body": 12,
        "leading_ratio": 1.15,
    },
    "large": {
        "label_key": "font_size_large",
        "title": 18,
        "section": 16,
        "body": 13,
        "leading_ratio": 1.35,
    },
    "exam_style": {
        "label_key": "font_size_exam_style",
        "title": 14,
        "section": 12,
        "body": 11,
        "leading_ratio": 1.45,
    },
}

# ── Registry kept for already-registered fonts ────────────────────
_registered_fonts: set[str] = set()


def _resolve_path(filename: str | None) -> str | None:
    """Return full path if file exists in _FONT_DIR, else None."""
    if not filename:
        return None
    full = os.path.join(_FONT_DIR, filename)
    return full if os.path.isfile(full) else None


def _fallback_paths() -> tuple[str, str]:
    """Return (regular, bold) paths for the DejaVu fallback."""
    fb = FONT_REGISTRY[DEFAULT_FONT_KEY]
    return os.path.join(_FONT_DIR, fb["regular"]), os.path.join(_FONT_DIR, fb["bold"])


def get_font_paths(font_key: str) -> tuple[str, str]:
    """Return (regular_path, bold_path) for a font key.
    Falls back to DejaVu Sans if the files are missing or the font is named-only."""
    entry = FONT_REGISTRY.get(font_key, FONT_REGISTRY[DEFAULT_FONT_KEY])

    if not entry.get("embedded"):
        return _fallback_paths()

    regular = _resolve_path(entry["regular"])
    bold = _resolve_path(entry["bold"])

    if not regular or not bold:
        return _fallback_paths()

    return regular, bold


def register_font_for_pdf(font_key: str) -> tuple[str, str]:
    """
    Register a font with ReportLab and return (body_name, bold_name).
    Safe to call multiple times — idempotent.

    For embedded fonts, registers the local TTF/OTF.
    For named-only fonts (or missing files), falls back to DejaVu Sans.
    """
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    regular_path, bold_path = get_font_paths(font_key)

    # Determine the registration key: use the actual font if embedded,
    # otherwise this will be "dejavu" (the fallback paths).
    entry = FONT_REGISTRY.get(font_key, FONT_REGISTRY[DEFAULT_FONT_KEY])
    is_embedded = entry.get("embedded") and _resolve_path(entry["regular"])
    reg_key = font_key if is_embedded else DEFAULT_FONT_KEY

    body_name = f"Classio_{reg_key}"
    bold_name = f"Classio_{reg_key}_Bold"

    if body_name not in _registered_fonts:
        try:
            pdfmetrics.registerFont(TTFont(body_name, regular_path))
            pdfmetrics.registerFont(TTFont(bold_name, bold_path))
            from reportlab.pdfbase.pdfmetrics import registerFontFamily
            registerFontFamily(
                body_name,
                normal=body_name,
                bold=bold_name,
                italic=body_name,
                boldItalic=bold_name,
            )
            _registered_fonts.add(body_name)
        except Exception:
            # Last-resort fallback to the legacy registration
            from styles.pdf_styles import ensure_pdf_fonts_registered
            return ensure_pdf_fonts_registered()

    return body_name, bold_name


def get_font_sizes(size_key: str) -> dict:
    """Return a size preset dict with title/section/body/leading_ratio."""
    return SIZE_PRESETS.get(size_key, SIZE_PRESETS[DEFAULT_SIZE_KEY]).copy()


def get_docx_font_name(font_key: str) -> str:
    """Return the font-family name to write into DOCX XML.
    Always returns the configured docx_name — Word resolves the font
    on the user's machine even if we don't bundle the file."""
    entry = FONT_REGISTRY.get(font_key, FONT_REGISTRY[DEFAULT_FONT_KEY])
    return entry["docx_name"]


def get_font_options() -> list[tuple[str, str]]:
    """Return list of (font_key, display_label) for UI selectors.
    All 7 curated fonts are always shown."""
    from core.i18n import t
    return [(key, t(entry["label_key"])) for key, entry in FONT_REGISTRY.items()]


def is_font_available(font_key: str) -> bool:
    """Check whether local TTF/OTF files exist for this font key.
    Named-only fonts return False (they work in DOCX but not PDF)."""
    entry = FONT_REGISTRY.get(font_key)
    if not entry or not entry.get("embedded"):
        return False
    return bool(_resolve_path(entry["regular"]) and _resolve_path(entry["bold"]))


def get_size_options() -> list[tuple[str, str]]:
    """Return list of (size_key, label_translation_key) for UI selectors."""
    result = []
    for key, entry in SIZE_PRESETS.items():
        result.append((key, entry["label_key"]))
    return result
