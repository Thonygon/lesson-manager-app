from __future__ import annotations

from typing import Any

import pycountry


def _language_display_name(language) -> str:
    return str(
        getattr(language, "common_name", "")
        or getattr(language, "name", "")
        or getattr(language, "alpha_3", "")
    ).strip()


def _language_code(language) -> str:
    return str(getattr(language, "alpha_3", "") or getattr(language, "alpha_2", "")).strip().lower()


def _build_language_library() -> tuple[list[str], dict[str, str], dict[str, str], dict[str, str]]:
    labels: dict[str, str] = {}
    alpha2_by_code: dict[str, str] = {}
    aliases: dict[str, str] = {"": "", "none": "", "not_set": ""}
    for language in pycountry.languages:
        code = _language_code(language)
        name = _language_display_name(language)
        if not code or not name:
            continue
        labels.setdefault(code, name)
        alpha2 = str(getattr(language, "alpha_2", "") or "").strip().lower()
        if alpha2:
            alpha2_by_code.setdefault(code, alpha2)
        alias_values = {
            code,
            str(getattr(language, "alpha_2", "") or "").strip().lower(),
            str(getattr(language, "alpha_3", "") or "").strip().lower(),
            str(getattr(language, "bibliographic", "") or "").strip().lower(),
            name.casefold(),
            name.casefold().replace(" ", "_"),
            str(getattr(language, "common_name", "") or "").strip().casefold(),
            str(getattr(language, "common_name", "") or "").strip().casefold().replace(" ", "_"),
        }
        for alias in alias_values:
            if alias:
                aliases[alias] = code

    options = [""] + sorted(labels.keys(), key=lambda item: labels[item].casefold())
    if "other" not in labels:
        labels["other"] = "Other"
        aliases["other"] = "other"
        options.append("other")
    return options, labels, aliases, alpha2_by_code


NATIVE_LANGUAGE_OPTIONS, _LANGUAGE_LABELS, _NATIVE_LANGUAGE_ALIASES, _LANGUAGE_ALPHA2 = _build_language_library()

_LANGUAGE_FLAG_COUNTRIES = {
    "eng": "gb",
    "spa": "es",
    "tur": "tr",
    "ara": "sa",
    "zho": "cn",
    "cmn": "cn",
    "yue": "hk",
    "jpn": "jp",
    "kor": "kr",
    "hin": "in",
    "ben": "bd",
    "por": "pt",
    "rus": "ru",
    "deu": "de",
    "fra": "fr",
    "ita": "it",
    "ell": "gr",
    "ces": "cz",
    "ukr": "ua",
    "heb": "il",
    "vie": "vn",
    "swe": "se",
    "dan": "dk",
    "nld": "nl",
    "fin": "fi",
    "pol": "pl",
    "ron": "ro",
    "hun": "hu",
    "ind": "id",
    "msa": "my",
    "tha": "th",
}

_NATIVE_LANGUAGE_ALIASES.update(
    {
        "inglés": "eng",
        "ingilizce": "eng",
        "español": "spa",
        "ispanyolca": "spa",
        "turco": "tur",
        "türkçe": "tur",
        "árabe": "ara",
        "arapça": "ara",
        "francés": "fra",
        "fransızca": "fra",
        "alemán": "deu",
        "almanca": "deu",
        "italyanca": "ita",
        "portugués": "por",
        "portekizce": "por",
        "ruso": "rus",
        "rusça": "rus",
    }
)


def normalize_native_language(raw: Any) -> str:
    key = str(raw or "").strip().casefold().replace(" ", "_")
    return _NATIVE_LANGUAGE_ALIASES.get(key, key if key in NATIVE_LANGUAGE_OPTIONS else "")


def is_language_subject(subject: str, custom_subject_name: str = "") -> bool:
    subject_key = normalize_native_language(subject)
    custom_key = normalize_native_language(custom_subject_name)
    raw_subject = str(subject or "").strip().casefold()
    raw_custom = str(custom_subject_name or "").strip().casefold()
    language_keys = {"eng", "spa", "tur", "ara", "fra", "deu", "ita", "por", "rus"}
    return (
        subject_key in language_keys
        or custom_key in language_keys
        or (subject_key not in {"", "other"} and raw_subject not in {"mathematics", "math", "science", "music", "study_skills"})
        or custom_key not in {"", "other"}
        or raw_subject in {"language", "languages"}
        or raw_custom in {"language", "languages"}
    )


def native_language_label(value: str) -> str:
    from core.i18n import t

    key = normalize_native_language(value)
    if not key:
        label = t("native_language_not_set")
        return label if label != "native_language_not_set" else "Not set"
    label_key = f"native_language_{key}"
    label = t(label_key)
    if label != label_key:
        return label
    return _LANGUAGE_LABELS.get(key, key.replace("_", " ").title())


def _country_flag(country_code: str) -> str:
    code = str(country_code or "").strip().upper()
    if len(code) != 2 or not code.isalpha():
        return ""
    return "".join(chr(0x1F1E6 + ord(char) - ord("A")) for char in code)


def native_language_flag(value: str) -> str:
    key = normalize_native_language(value)
    if not key or key == "other":
        return ""
    country_code = _LANGUAGE_FLAG_COUNTRIES.get(key)
    if not country_code:
        alpha2 = _LANGUAGE_ALPHA2.get(key, "")
        if alpha2 and pycountry.countries.get(alpha_2=alpha2.upper()):
            country_code = alpha2
    return _country_flag(country_code)


def native_language_flag_label(value: str, *, include_name: bool = False) -> str:
    flag = native_language_flag(value)
    label = native_language_label(value)
    if flag and include_name:
        return f"{flag} {label}"
    return flag or label