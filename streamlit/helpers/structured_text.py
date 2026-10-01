from __future__ import annotations

import html
import re
import unicodedata
from typing import Any


_HEADER_RE = re.compile(r"^(de|from|para|to|asunto|subject)\s*:\s*(.+)$", re.IGNORECASE)
_INLINE_HEADER_RE = re.compile(r"\b(de|from|para|to|asunto|subject)\s*:\s*", re.IGNORECASE)
_GREETING_RE = re.compile(
    r"\b(estimad[oa]s?|dear|buenos dias|buenos días|buenas tardes|hola|sayin|sayın)\b",
    re.IGNORECASE,
)
_SIGNOFF_RE = re.compile(
    r"\b(atentamente|cordialmente|saludos|sincerely|kind regards|best regards|regards|saygilar|saygılar)\b",
    re.IGNORECASE,
)
_SPEAKER_RE = re.compile(r"^([A-ZÁÉÍÓÚÜÑÇ][\wÁÉÍÓÚÜÑÇáéíóúüñç .'-]{0,34})\s*:\s+(.+)$")
_INLINE_DIALOGUE_BREAK_RE = re.compile(
    r"\s+[—–-]\s+(?=[A-ZÁÉÍÓÚÜÑÇ][\wÁÉÍÓÚÜÑÇáéíóúüñç .'-]{0,34}\s*:)"
)
_INLINE_SPEAKER_BREAK_RE = re.compile(
    r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÜÑÇ][\wÁÉÍÓÚÜÑÇáéíóúüñç .'-]{0,34}\s*:)"
)


def preserve_text_format(value: Any) -> str:
    text = unicodedata.normalize("NFC", str(value or ""))
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    compacted: list[str] = []
    blank_seen = False
    for line in lines:
        if not line:
            if not blank_seen:
                compacted.append("")
            blank_seen = True
            continue
        compacted.append(line)
        blank_seen = False
    return "\n".join(compacted)


def _clean_inline(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _sentence_chunks(text: str) -> list[str]:
    chunks = [
        _clean_inline(part)
        for part in re.split(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÜÑ¿¡])", text)
        if _clean_inline(part)
    ]
    return chunks or [_clean_inline(text)] if _clean_inline(text) else []


def _split_body_segments(body: str) -> list[dict[str, str]]:
    text = preserve_text_format(body)
    if "\n" in text:
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
        return [{"type": "paragraph", "text": part} for part in paragraphs]

    segments: list[dict[str, str]] = []
    signoff_match = _SIGNOFF_RE.search(text)
    before_signoff = text[: signoff_match.start()].strip() if signoff_match else text
    signoff = text[signoff_match.start() :].strip() if signoff_match else ""

    if before_signoff:
        chunks = _sentence_chunks(before_signoff)
        if chunks:
            greeting = chunks[0]
            if _GREETING_RE.search(greeting):
                segments.append({"type": "greeting", "text": greeting})
                chunks = chunks[1:]
        for chunk in chunks:
            segments.append({"type": "paragraph", "text": chunk})

    if signoff:
        pieces = _sentence_chunks(signoff)
        if pieces:
            segments.append({"type": "signoff", "text": pieces[0]})
            for piece in pieces[1:]:
                segments.append({"type": "paragraph", "text": piece})
    return segments


def _extract_inline_headers(text: str) -> tuple[dict[str, str], str]:
    matches = list(_INLINE_HEADER_RE.finditer(text))
    if not matches:
        return {}, text

    headers: dict[str, str] = {}
    remainder_start = 0
    for idx, match in enumerate(matches):
        key = match.group(1).lower()
        value_start = match.end()
        value_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        value = text[value_start:value_end].strip()
        if key in {"asunto", "subject"}:
            greeting = _GREETING_RE.search(value)
            if greeting:
                remainder_start = value_start + greeting.start()
                value = value[: greeting.start()].strip()
                headers[key] = _clean_inline(value)
                break
        headers[key] = _clean_inline(value)
        remainder_start = value_end
    return headers, text[remainder_start:].strip()


def _email_blocks(text: str) -> list[dict[str, str]]:
    normalized = preserve_text_format(text)
    headers: dict[str, str] = {}
    body_lines: list[str] = []
    if "\n" in normalized:
        for line in normalized.split("\n"):
            match = _HEADER_RE.match(line.strip())
            if match:
                headers[match.group(1).lower()] = _clean_inline(match.group(2))
            else:
                body_lines.append(line)
        body = "\n".join(body_lines)
    else:
        headers, body = _extract_inline_headers(normalized)

    blocks: list[dict[str, str]] = []
    for keys, label in ((("de", "from"), "from"), (("para", "to"), "to"), (("asunto", "subject"), "subject")):
        value = next((headers.get(key) for key in keys if headers.get(key)), "")
        if value:
            blocks.append({"type": label, "label": label, "text": value})
    blocks.extend(_split_body_segments(body))
    return blocks


def _dialogue_blocks(text: str) -> list[dict[str, str]]:
    normalized = preserve_text_format(text)
    normalized = _INLINE_DIALOGUE_BREAK_RE.sub("\n", normalized)
    normalized = _INLINE_SPEAKER_BREAK_RE.sub("\n", normalized)
    blocks = []
    for line in normalized.split("\n"):
        if not line.strip():
            continue
        match = _SPEAKER_RE.match(line.strip())
        if match:
            blocks.append({"type": "turn", "speaker": match.group(1).strip(), "text": match.group(2).strip()})
        else:
            blocks.append({"type": "paragraph", "text": line.strip()})
    return blocks


def infer_text_kind(text: str, explicit_kind: str = "") -> str:
    kind = str(explicit_kind or "").strip().lower()
    if kind in {"passage", "email", "dialogue", "essay", "article", "letter", "message"}:
        return kind
    normalized = preserve_text_format(text)
    if not normalized:
        return "passage"
    if re.search(r"\b(de|from)\s*:", normalized, re.IGNORECASE) and re.search(
        r"\b(asunto|subject|para|to)\s*:", normalized,
        re.IGNORECASE,
    ):
        return "email"
    if re.search(r"\b(asunto|subject)\s*:", normalized, re.IGNORECASE) and (
        _GREETING_RE.search(normalized) or _SIGNOFF_RE.search(normalized)
    ):
        return "email"
    if len([block for block in _dialogue_blocks(normalized) if block.get("type") == "turn"]) >= 2:
        return "dialogue"
    if len([line for line in normalized.split("\n") if line.strip()]) >= 4:
        return "article"
    return "passage"


def build_text_asset(text: str, *, title: str = "", text_kind: str = "", blocks: Any = None) -> dict[str, Any]:
    kind = infer_text_kind(text, text_kind)
    clean_title = _clean_inline(title)
    if isinstance(blocks, list) and any(isinstance(item, dict) and str(item.get("text") or "").strip() for item in blocks):
        clean_blocks = [
            {str(key): preserve_text_format(value) if key == "text" else _clean_inline(value) for key, value in item.items()}
            for item in blocks
            if isinstance(item, dict) and str(item.get("text") or "").strip()
        ]
    elif kind == "email":
        clean_blocks = _email_blocks(text)
    elif kind == "dialogue":
        clean_blocks = _dialogue_blocks(text)
    else:
        preserved = preserve_text_format(text)
        parts = [part.strip() for part in re.split(r"\n\s*\n", preserved) if part.strip()]
        if not clean_title and parts:
            first_lines = parts[0].split("\n")
            first_line = first_lines[0].strip()
            title_like = (
                len(first_line) <= 90
                and len(first_lines) > 1
                and not re.search(r"[.!?;:]$", first_line)
            )
            if title_like:
                clean_title = first_line
                remainder = "\n".join(line for line in first_lines[1:] if line.strip()).strip()
                parts = ([remainder] if remainder else []) + parts[1:]
        clean_blocks = [{"type": "paragraph", "text": part} for part in parts]
        if not clean_blocks and preserve_text_format(text):
            clean_blocks = [{"type": "paragraph", "text": preserve_text_format(text)}]

    return {
        "text_kind": kind,
        "title": clean_title,
        "raw_text": preserve_text_format(text),
        "blocks": clean_blocks,
    }


def text_asset_to_markdown(text: str, *, title: str = "", text_kind: str = "", blocks: Any = None) -> str:
    asset = build_text_asset(text, title=title, text_kind=text_kind, blocks=blocks)
    lines: list[str] = []
    if asset.get("title"):
        lines.append(f"#### {html.escape(str(asset['title']))}")
        lines.append("")
    for block in asset.get("blocks") or []:
        block_type = str(block.get("type") or "paragraph")
        if block_type in {"from", "to", "subject"}:
            label = {"from": "De/From", "to": "Para/To", "subject": "Asunto/Subject"}.get(block_type, block_type.title())
            lines.append(f"**{html.escape(label)}:** {html.escape(str(block.get('text') or ''))}")
        elif block_type == "turn":
            speaker = html.escape(str(block.get("speaker") or "").strip())
            text_value = html.escape(str(block.get("text") or "").strip())
            lines.append(f"**{speaker}:** {text_value}" if speaker else text_value)
        else:
            lines.append(html.escape(str(block.get("text") or "").strip()).replace("\n", "<br>"))
        lines.append("")
    return "\n".join(lines).strip()
