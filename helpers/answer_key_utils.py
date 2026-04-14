from __future__ import annotations

import ast
import json
import re


_LEADING_MARKER_RE = re.compile(
    r"^\s*(?:[\[\(\{]+\s*)?(?:['\"]+\s*)?(?:\(?\d+\)?|[A-Za-z])[\.\)\-:]\s*"
)
_NUMBERED_CHUNK_RE = re.compile(
    r"(?:^|[\s\[\(\{,;])['\"]?\s*((?:\(?\d+\)?|[A-Za-z])[\.\)\-:])\s*(.*?)"
    r"(?=(?:[\s\]\)\},;]+['\"]?\s*(?:\(?\d+\)?|[A-Za-z])[\.\)\-:]\s)|$)",
    re.S,
)


def _normalize_text(value) -> str:
    text = str(value or "")
    return (
        text.replace("“", '"')
        .replace("”", '"')
        .replace("‘", "'")
        .replace("’", "'")
        .replace("—", "-")
        .replace("–", "-")
    )


def _clean_str(value) -> str:
    return re.sub(r"\s+", " ", _normalize_text(value)).strip()


def _maybe_parse_sequence(raw):
    if isinstance(raw, (list, tuple)):
        return list(raw)
    if raw is None:
        return None

    text = _normalize_text(raw).strip()
    if not text:
        return None

    for parser in (json.loads, ast.literal_eval):
        try:
            parsed = parser(text)
        except Exception:
            parsed = None
        if isinstance(parsed, (list, tuple)):
            return list(parsed)

    return None


def strip_leading_answer_marker(value) -> str:
    text = _clean_str(value)
    if not text:
        return ""
    return _LEADING_MARKER_RE.sub("", text).strip()


def clean_answer_key_item(value) -> str:
    text = strip_leading_answer_marker(value)
    if not text:
        return ""

    text = re.sub(r"^\s*[\[\(\{]+\s*", "", text)
    text = re.sub(r"\s*[\]\)\}]+\s*$", "", text)
    text = text.strip().strip("'\"")
    text = re.sub(r"\s*[,;]+\s*$", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def split_answer_key_items(raw, expected_count: int | None = None) -> list[str]:
    parsed_seq = _maybe_parse_sequence(raw)
    if parsed_seq is not None:
        items = [clean_answer_key_item(item) for item in parsed_seq]
        items = [item for item in items if item]
    else:
        text = _normalize_text(raw).strip()
        if not text:
            items = []
        else:
            matches = [
                clean_answer_key_item(match.group(2))
                for match in _NUMBERED_CHUNK_RE.finditer(text)
            ]
            matches = [item for item in matches if item]

            if len(matches) >= 2 or (expected_count and len(matches) >= expected_count):
                items = matches
            else:
                candidate = text
                if candidate.startswith("[") and candidate.endswith("]"):
                    candidate = candidate[1:-1].strip()

                candidate = re.sub(r"['\"]\s*[,;]\s*['\"]", "\n", candidate)
                candidate = re.sub(
                    r"\s*;\s*(?=(?:\(?\d+\)?|[A-Za-z])[\.\)\-:]\s)",
                    "\n",
                    candidate,
                )

                if expected_count and expected_count > 1 and "\n" not in candidate:
                    candidate = re.sub(
                        r"\s+(?=(?:\(?\d+\)?|[A-Za-z])[\.\)\-:]\s)",
                        "\n",
                        candidate,
                    )

                parts = [part for part in re.split(r"\n+", candidate) if part.strip()]
                if len(parts) == 1 and ";" in candidate:
                    semicolon_parts = [part for part in re.split(r"\s*;\s*", candidate) if part.strip()]
                    if len(semicolon_parts) > 1:
                        parts = semicolon_parts

                items = [clean_answer_key_item(part) for part in parts]
                items = [item for item in items if item]

    if expected_count is not None:
        items = items[:expected_count]
        while len(items) < expected_count:
            items.append("")

    return items


def normalize_answer_key_text(raw, expected_count: int | None = None) -> str:
    items = split_answer_key_items(raw, expected_count=expected_count)
    return "\n".join(item for item in items if item)
