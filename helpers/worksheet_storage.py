# CLASSIO — Worksheet Storage
# ============================================================
import streamlit as st
import json, re, math, os
from typing import Optional
from datetime import datetime as _dt, timezone
import pandas as pd
from io import BytesIO
from core.i18n import t
from core.state import get_current_user_id, with_owner
from core.timezone import now_local, today_local, get_app_tz
from core.database import get_sb, load_table, clear_app_caches
import math
import html
import textwrap
from core.navigation import home_go
import re
import unicodedata
from xml.sax.saxutils import escape as xml_escape
from styles.pdf_styles import (
    ensure_pdf_fonts_registered,
    get_student_pdf_styles,
    get_answer_key_pdf_styles,
    get_pdf_layout_constants,
    C as _C,
)


def _wb():
    import helpers.worksheet_builder as wb
    return wb


def _lp():
    import helpers.lesson_planner as lp
    return lp


_LEADING_NUM_RE = re.compile(r"^\s*\d+[\.\)\-]\s*")
_MC_OPTION_PREFIX_RE = re.compile(r"^\s*(?:[A-Da-d]|[1-9])[\)\.\-:]\s*")
_MC_STEM_PREFIX_RE = re.compile(r"^\s*\d+[\)\.\-:]\s*")
_LEADING_ENUM_RE = re.compile(r"^\s*(?:\d+|[A-Za-z])[\.\)\-:]\s*")

def _strip_leading_enum(text: str) -> str:
    return _LEADING_ENUM_RE.sub("", _normalize_text(text or "").strip())

def _strip_mc_option_prefix(text: str) -> str:
    return _MC_OPTION_PREFIX_RE.sub("", _normalize_text(text or "").strip())

def _strip_mc_stem_prefix(text: str) -> str:
    return _MC_STEM_PREFIX_RE.sub("", _normalize_text(text or "").strip())


def _strip_leading_number(text: str) -> str:
    return _LEADING_NUM_RE.sub("", str(text or ""))


def _normalize_text(value) -> str:
    return unicodedata.normalize("NFC", str(value or ""))


def _normalize_text_list(values) -> list[str]:
    if not isinstance(values, list):
        return []
    return [_normalize_text(v) for v in values if str(v).strip()]


def _normalize_mc_items(items) -> list[dict]:
    out = []
    if not isinstance(items, list):
        return out

    for item in items:
        if not isinstance(item, dict):
            continue

        stem = _strip_mc_stem_prefix(item.get("stem", ""))
        options = item.get("options") or []
        if not isinstance(options, list):
            options = [str(options)]

        cleaned_options = []
        for opt in options:
            cleaned = _strip_mc_option_prefix(opt)
            if cleaned:
                cleaned_options.append(cleaned)

        answer = _strip_mc_option_prefix(item.get("answer", ""))

        if stem and len(cleaned_options) >= 3:
            out.append({
                "stem": stem,
                "options": cleaned_options[:4],
                "answer": answer,
            })
    return out


def _normalize_worksheet_unicode(ws: dict) -> dict:
    ws = dict(ws or {})

    text_keys = [
        "title",
        "instructions",
        "reading_passage",
        "answer_key",
        "topic",
        "subject",
        "worksheet_type",
        "learner_stage",
        "level_or_band",
        "plan_language",
        "student_material_language",
        "source_text",
        "text",
    ]
    for key in text_keys:
        if key in ws:
            ws[key] = _normalize_text(ws.get(key))

    list_keys = [
        "questions",
        "teacher_notes",
        "vocabulary_bank",
        "true_false_statements",
        "left_items",
        "right_items",
    ]
    for key in list_keys:
        if key in ws:
            ws[key] = _normalize_text_list(ws.get(key))

    if "multiple_choice_items" in ws:
        ws["multiple_choice_items"] = _normalize_mc_items(ws.get("multiple_choice_items"))

    return ws


def _pdf_safe_text(value) -> str:
    return xml_escape(_normalize_text(value))



def _split_answer_key(answer_key) -> list[str]:
    if isinstance(answer_key, list):
        return [_normalize_text(a) for a in answer_key if str(a).strip()]

    text = _normalize_text(answer_key or "")
    parts = re.split(r"(?:^|\n)\s*(\d+[\.\)\-])", text)

    if len(parts) > 2:
        lines = []
        i = 1
        while i < len(parts) - 1:
            num = parts[i].strip()
            body = parts[i + 1].strip()
            if body:
                lines.append(f"{num} {body}")
            i += 2
        if lines:
            return lines

    lines = [l.strip() for l in text.split("\n") if l.strip()]
    return lines if lines else [text]

# ── clean helpers ───────────────────────────────────────────────

def _clean_worksheet_data(ws: dict) -> dict:
    out = dict(ws or {})
    if isinstance(out.get("questions"), list):
        out["questions"] = [
            _strip_leading_enum(q) if isinstance(q, str) else q
            for q in out["questions"]
        ]
    return out


def _clean_display_text(text: str) -> str:
    s = _normalize_text(text).strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s+([.,!?;:])", r"\1", s)
    s = re.sub(r"\s*-\s*", " - ", s)
    s = re.sub(r"\s*/\s*", " / ", s)
    s = re.sub(r"\s+", " ", s).strip()

    if s:
        s = s[0].upper() + s[1:]

    return s


def _clean_card_fields(title: str, topic: str) -> tuple[str, str]:
    return _clean_display_text(title), _clean_display_text(topic)




# ── Wordsearch helpers ───────────────────────────────────────────────
def _wordsearch_safe_upper(text: str) -> str:
    s = _normalize_text(text).strip()
    s = s.replace("i", "İ").replace("ı", "I")
    return s.upper()


def _normalize_wordsearch_words(words: list[str], max_words: int = 12) -> list[str]:
    out = []
    seen = set()

    for w in words or []:
        s = _normalize_text(w).strip()
        s = re.sub(r"\(.*?\)", "", s)
        s = re.split(r"\s[-–—]\s", s)[0]
        s = s.split(",")[0]
        s = _wordsearch_safe_upper(s)
        s = re.sub(r"[^A-ZÁÉÍÓÚÜÑÇĞİÖŞ0-9 ]", "", s)
        s = re.sub(r"\s+", "", s)

        if len(s) < 2:
            continue

        key = s.casefold()
        if key in seen:
            continue

        seen.add(key)
        out.append(s)

    out.sort(key=len, reverse=True)
    return out[:max_words]


def _build_wordsearch_alphabet(words: list[str]) -> list[str]:
    chars = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    for word in words or []:
        for ch in str(word):
            if ch.strip():
                chars.add(ch)
    return sorted(chars)


def _resolve_wordsearch_size(words: list[str], size: int | None = None) -> int:
    if not words:
        return 0

    longest = max(len(w) for w in words)
    suggested = max(
        10,
        longest + 2,
        int(math.ceil(math.sqrt(sum(len(w) for w in words)))) + 3,
        len(words) + 3,
    )

    if size is None:
        return suggested

    return max(size, longest + 1)


def _generate_wordsearch_grid(
    words: list[str],
    size: int | None = None,
    seed: str | int | None = None,
) -> tuple[list[list[str]], list[str], list[dict]]:
    words = _normalize_wordsearch_words(words)
    if not words:
        return [], [], []

    size = _resolve_wordsearch_size(words, size=size)
    directions = [(0, 1), (1, 0), (1, 1), (-1, 1)]

    import random
    rng = random.Random(seed if seed is not None else "|".join(words))
    alphabet = _build_wordsearch_alphabet(words)

    def try_build():
        grid = [["" for _ in range(size)] for _ in range(size)]
        placements = []

        for word in words:
            placed = False

            for _ in range(500):
                dr, dc = rng.choice(directions)

                if dr == 0:
                    r_min, r_max = 0, size - 1
                elif dr == 1:
                    r_min, r_max = 0, size - len(word)
                else:
                    r_min, r_max = len(word) - 1, size - 1

                if dc == 0:
                    c_min, c_max = 0, size - 1
                elif dc == 1:
                    c_min, c_max = 0, size - len(word)
                else:
                    c_min, c_max = len(word) - 1, size - 1

                if r_min > r_max or c_min > c_max:
                    continue

                r = rng.randint(r_min, r_max)
                c = rng.randint(c_min, c_max)

                ok = True
                rr, cc = r, c
                coords = []

                for ch in word:
                    if not (0 <= rr < size and 0 <= cc < size):
                        ok = False
                        break

                    cell = grid[rr][cc]
                    if cell not in ("", ch):
                        ok = False
                        break

                    coords.append((rr, cc))
                    rr += dr
                    cc += dc

                if not ok:
                    continue

                for (rr, cc), ch in zip(coords, word):
                    grid[rr][cc] = ch

                placements.append({"word": word, "coords": coords})
                placed = True
                break

            if not placed:
                return None, None

        for r in range(size):
            for c in range(size):
                if not grid[r][c]:
                    grid[r][c] = rng.choice(alphabet)

        return grid, placements

    for _ in range(20):
        built_grid, placements = try_build()
        if built_grid is not None:
            return built_grid, words, placements

    return [], words, []


def _render_wordsearch_grid(grid: list[list[str]]) -> None:
    if not grid:
        st.warning(t("word_search_grid_failed"))
        return

    html_rows = []
    for row in grid:
        cells = "".join(f"<td>{html.escape(ch)}</td>" for ch in row)
        html_rows.append(f"<tr>{cells}</tr>")

    st.markdown(
        f"""
        <style>
        .ws-wordsearch-wrap {{
            overflow-x: auto;
            margin: 0.5rem 0 1rem 0;
        }}
        .ws-wordsearch-grid {{
            border-collapse: collapse;
            margin: 0 auto;
        }}
        .ws-wordsearch-grid td {{
            width: 32px;
            height: 32px;
            text-align: center;
            vertical-align: middle;
            border: 1px solid rgba(148,163,184,.35);
            font-weight: 700;
            font-size: 0.95rem;
            border-radius: 6px;
            font-family: "DejaVu Sans", "Noto Sans", "Arial Unicode MS", Arial, sans-serif;
        }}
        </style>
        <div class="ws-wordsearch-wrap">
          <table class="ws-wordsearch-grid">
            {''.join(html_rows)}
          </table>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_wordsearch_answer_grid(grid: list[list[str]], placements: list[dict]) -> None:
    if not grid:
        st.warning(t("word_search_grid_failed"))
        return

    hit_cells = set()
    for item in placements or []:
        for coord in item.get("coords", []):
            hit_cells.add(tuple(coord))

    html_rows = []
    for r, row in enumerate(grid):
        cells = []
        for c, ch in enumerate(row):
            cls = "ws-answer-hit" if (r, c) in hit_cells else ""
            cells.append(f"<td class='{cls}'>{html.escape(ch)}</td>")
        html_rows.append(f"<tr>{''.join(cells)}</tr>")

    st.markdown(
        f"""
        <style>
        .ws-wordsearch-wrap {{
            overflow-x: auto;
            margin: 0.5rem 0 1rem 0;
        }}
        .ws-wordsearch-grid {{
            border-collapse: collapse;
            margin: 0 auto;
        }}
        .ws-wordsearch-grid td {{
            width: 32px;
            height: 32px;
            text-align: center;
            vertical-align: middle;
            border: 1px solid rgba(148,163,184,.35);
            font-weight: 700;
            font-size: 0.95rem;
            border-radius: 6px;
            font-family: "DejaVu Sans", "Noto Sans", "Arial Unicode MS", Arial, sans-serif;
        }}
        .ws-wordsearch-grid td.ws-answer-hit {{
            background: rgba(59,130,246,.20);
            border: 2px solid rgba(29,78,216,.85);
            color: #0F172A;
            box-shadow: inset 0 0 0 1px rgba(29,78,216,.15);
        }}
        </style>
        <div class="ws-wordsearch-wrap">
          <table class="ws-wordsearch-grid">
            {''.join(html_rows)}
          </table>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Matching helpers ─────────────────────────────────────────────────
def _get_matching_pairs(ws: dict) -> list[dict]:
    ws = dict(ws or {})
    pairs = ws.get("matching_pairs") or []

    out = []
    if isinstance(pairs, list):
        for item in pairs:
            if not isinstance(item, dict):
                continue
            left = _normalize_text(item.get("left", "")).strip()
            right = _normalize_text(item.get("right", "")).strip()
            if left and right:
                out.append({"left": left, "right": right})

    if out:
        return out

    left_items = ws.get("left_items") or []
    right_items = ws.get("right_items") or []

    if isinstance(left_items, list) and isinstance(right_items, list):
        for left, right in zip(left_items, right_items):
            left = _normalize_text(left).strip()
            right = _normalize_text(right).strip()
            if left and right:
                out.append({"left": left, "right": right})

    return out


def _build_matching_columns(ws: dict) -> tuple[list[str], list[str], list[tuple[int, str]]]:
    pairs = _get_matching_pairs(ws)
    if not pairs:
        return [], [], []

    import random

    left_items = [p["left"] for p in pairs]
    right_items = [p["right"] for p in pairs]

    rng = random.Random("|".join(left_items + right_items))
    shuffled_right = right_items[:]
    rng.shuffle(shuffled_right)

    letters = [chr(97 + i) for i in range(len(shuffled_right))]
    right_lookup = {value: letters[idx] for idx, value in enumerate(shuffled_right)}
    answer_map = [(idx + 1, right_lookup[p["right"]]) for idx, p in enumerate(pairs)]

    return left_items, shuffled_right, answer_map


def _render_matching_exercise(ws: dict) -> None:
    left_items, right_items, _ = _build_matching_columns(ws)

    if not left_items or not right_items:
        st.warning(t("no_data"))
        return

    c1, c2 = st.columns(2)

    with c1:
        st.markdown(f"**{t('ws_column_a') if t('ws_column_a') != 'ws_column_a' else 'Column A'}**")
        for idx, item in enumerate(left_items, 1):
            st.write(f"{idx}. {_strip_leading_enum(item)}")

    with c2:
        st.markdown(f"**{t('ws_column_b') if t('ws_column_b') != 'ws_column_b' else 'Column B'}**")
        for idx, item in enumerate(right_items):
            letter = chr(97 + idx)
            st.write(f"{letter}) {_strip_leading_enum(item)}")


def _render_matching_answer_key(ws: dict) -> None:
    _, _, answer_map = _build_matching_columns(ws)
    if not answer_map:
        st.warning(t("no_data"))
        return
    for num, letter in answer_map:
        st.write(f"{num} → {letter}")


# ── True/False helpers ───────────────────────────────────────────────
def _get_true_false_statements(ws: dict) -> list[str]:
    ws = dict(ws or {})

    statements = ws.get("true_false_statements") or []
    if isinstance(statements, list):
        out = [_normalize_text(x).strip() for x in statements if str(x).strip()]
        if out:
            return out

    questions = ws.get("questions") or []
    if isinstance(questions, list):
        return [_normalize_text(x).strip() for x in questions if str(x).strip()]

    return []


def _get_true_false_source_text(ws: dict) -> str:
    ws = dict(ws or {})
    for key in ["source_text", "reading_passage", "text"]:
        value = _normalize_text(ws.get(key, "")).strip()
        if value:
            return value
    return ""


def _render_true_false_exercise(ws: dict) -> None:
    source_text = _get_true_false_source_text(ws)
    statements = _get_true_false_statements(ws)

    if not source_text:
        st.warning(
            t("true_false_missing_text")
            if t("true_false_missing_text") != "true_false_missing_text"
            else "This true/false worksheet needs a source text."
        )
        return

    st.markdown(
        f"**{t('ws_read_and_decide') if t('ws_read_and_decide') != 'ws_read_and_decide' else 'Read the text and decide if the statements are true or false.'}**"
    )
    st.write(source_text)

    if statements:
        st.markdown(f"**{t('ws_questions')}**")
        for idx, item in enumerate(statements, 1):
            st.write(f"{idx}. {_strip_leading_enum(item)}")
    else:
        st.warning(t("no_data"))


def _render_true_false_answer_key(ws: dict) -> None:
    answer_key = ws.get("answer_key")

    if isinstance(answer_key, list):
        for line in answer_key:
            if str(line).strip():
                st.write(_normalize_text(line))
        return

    if answer_key:
        for line in _split_answer_key(answer_key):
            st.write(_normalize_text(line))
        return

    st.warning(t("no_data"))


# ── Multiple choice helpers ──────────────────────────────────────────
def _get_multiple_choice_items(ws: dict) -> list[dict]:
    items = ws.get("multiple_choice_items") or []
    items = _normalize_mc_items(items)

    if items:
        return items

    # Fallback: parse old one-line question format
    parsed = []
    questions = ws.get("questions") or []
    for q in questions:
        text = _normalize_text(q).strip()
        m = re.match(
            r"^(.*?)(?:\s+A\)|\s+A\.)(.*?)(?:\s+B\)|\s+B\.)(.*?)(?:\s+C\)|\s+C\.)(.*?)(?:(?:\s+D\)|\s+D\.)(.*))?$",
            text,
            flags=re.IGNORECASE,
        )
        if m:
            stem = m.group(1).strip()
            opts = [m.group(2).strip(), m.group(3).strip(), m.group(4).strip()]
            if m.group(5):
                opts.append(m.group(5).strip())
            parsed.append({"stem": stem, "options": opts, "answer": ""})

    return parsed


def _mc_item_is_compact(item: dict) -> bool:
    stem = _normalize_text(item.get("stem", ""))
    options = [_normalize_text(x) for x in item.get("options", [])]
    if len(stem) > 120:
        return False
    if any(len(opt) > 55 for opt in options):
        return False
    return True


def _render_multiple_choice_exercise(ws: dict) -> None:
    items = _get_multiple_choice_items(ws)
    if not items:
        st.warning(t("no_data"))
        return

    rows = [items[i:i+2] for i in range(0, len(items), 2)]

    global_idx = 1
    for pair in rows:
        cols = st.columns(2, gap="medium")
        for col_idx, item in enumerate(pair):
            with cols[col_idx]:
                options_html = ""
                for opt_idx, opt in enumerate(item["options"]):
                    letter = chr(65 + opt_idx)
                    options_html += f"<div style='margin-top:6px;'>{letter}) {html.escape(opt)}</div>"

                card_html = f"""
                <div style="
                    border:1px solid rgba(148,163,184,.28);
                    border-radius:16px;
                    padding:14px 16px;
                    margin-bottom:14px;
                    background:rgba(255,255,255,.02);
                    min-height:220px;
                ">
                    <div style="font-weight:700; margin-bottom:10px;">
                        {global_idx}. {html.escape(item.get("stem", ""))}
                    </div>
                    <div style="line-height:1.6;">
                        {options_html}
                    </div>
                </div>
                """
                st.markdown(card_html, unsafe_allow_html=True)
                global_idx += 1


def _render_multiple_choice_answer_key(ws: dict) -> None:
    items = _get_multiple_choice_items(ws)

    has_answers = any(_normalize_text(item.get("answer", "")).strip() for item in items)
    if has_answers:
        for idx, item in enumerate(items, 1):
            ans = _normalize_text(item.get("answer", "")).strip()
            if ans:
                st.write(f"{idx}. {ans}")
        return

    answer_key = ws.get("answer_key")
    if answer_key:
        for line in _split_answer_key(answer_key):
            st.write(_normalize_text(line))
        return

    st.warning(t("no_data"))


# ── CRUD ──────────────────────────────────────────────────────────────
def save_worksheet_record(
    subject: str,
    learner_stage: str,
    level_or_band: str,
    worksheet_type: str,
    topic: str,
    worksheet: dict,
) -> bool:
    try:
        worksheet = _normalize_worksheet_unicode(worksheet)

        from helpers.branding import resolve_is_public

        payload = with_owner({
            "subject": str(subject).strip(),
            "topic": _clean_display_text(topic),
            "learner_stage": str(learner_stage).strip(),
            "level_or_band": str(level_or_band).strip(),
            "worksheet_type": str(worksheet_type).strip(),
            "plan_language": str(worksheet.get("plan_language") or _wb().get_plan_language()).strip(),
            "student_material_language": str(worksheet.get("student_material_language") or "").strip(),
            "source_type": "ai",
            "worksheet_json": worksheet,
            "title": _clean_display_text(worksheet.get("title") or ""),
            "author_name": str(st.session_state.get("user_name") or "Unknown").strip(),
            "subject_display": subject,
            "is_public": resolve_is_public(),
            "created_at": _dt.now(timezone.utc).isoformat(),
        })
        get_sb().table("worksheets").insert(payload).execute()
        return True
    except Exception as e:
        st.warning(f"Could not save worksheet: {e}")
        return False


def load_my_worksheets() -> pd.DataFrame:
    try:
        df = load_table("worksheets")
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.copy()
        if "created_at" in df.columns:
            df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
        sort_col = "created_at" if "created_at" in df.columns else None
        if sort_col:
            df = df.sort_values(sort_col, ascending=False, na_position="last")
        return df.reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


def load_public_worksheets() -> pd.DataFrame:
    try:
        res = (
            get_sb().table("worksheets")
            .select("*")
            .eq("is_public", True)
            .order("created_at", desc=True)
            .limit(500)
            .execute()
        )
        df = pd.DataFrame(res.data or [])
        if df.empty:
            return pd.DataFrame()
        if "created_at" in df.columns:
            df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
        return df.reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


# ── AI usage tracking ────────────────────────────────────────────────
def log_ai_usage(request_kind: str, status: str, meta: Optional[dict] = None) -> None:
    try:
        payload = with_owner({
            "feature_name": str(request_kind).strip(),
            "status": str(status).strip(),
            "meta_json": meta or {},
            "created_at": _dt.now(timezone.utc).isoformat(),
        })
        get_sb().table("ai_usage_logs").insert(payload).execute()
        clear_app_caches()
    except Exception:
        pass


def _safe_ai_logs_df() -> pd.DataFrame:
    try:
        df = load_table("ai_usage_logs")
    except Exception:
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()
    for col, default in {"created_at": None, "status": "", "feature_name": ""}.items():
        if col not in df.columns:
            df[col] = default
    df = df.copy()
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce", utc=True)
    df["status"] = df["status"].fillna("").astype(str).str.strip().str.lower()
    df["feature_name"] = df["feature_name"].fillna("").astype(str).str.strip().str.lower()
    return df


def get_ai_worksheet_usage_status() -> dict:
    df = _safe_ai_logs_df()
    now_utc = _dt.now(timezone.utc)
    today_start_utc = _dt.combine(today_local(), _dt.min.time()).replace(
        tzinfo=get_app_tz()
    ).astimezone(timezone.utc)

    limit = _wb().AI_WORKSHEET_DAILY_LIMIT
    cooldown = _wb().AI_WORKSHEET_COOLDOWN_SECONDS

    if df.empty:
        return {
            "used_today": 0,
            "remaining_today": limit,
            "cooldown_ok": True,
            "seconds_left": 0,
            "last_request_at": None,
        }

    feat_df = df[(df["feature_name"] == "quick_worksheet_ai") & (df["status"] == "success")].copy()
    today_df = feat_df[(feat_df["created_at"].notna()) & (feat_df["created_at"] >= today_start_utc)]
    used_today = int(len(today_df))

    cd_df = df[df["feature_name"] == "quick_worksheet_ai"].dropna(subset=["created_at"]).sort_values("created_at")
    cooldown_ok = True
    seconds_left = 0
    last_request_at = None
    if not cd_df.empty:
        last_request_at = cd_df.iloc[-1]["created_at"]
        delta = (now_utc - last_request_at.to_pydatetime()).total_seconds()
        if delta < cooldown:
            cooldown_ok = False
            seconds_left = int(math.ceil(cooldown - delta))

    return {
        "used_today": used_today,
        "remaining_today": max(0, limit - used_today),
        "cooldown_ok": cooldown_ok,
        "seconds_left": max(0, seconds_left),
        "last_request_at": last_request_at,
    }


# ── Library cards ────────────────────────────────────────────────────
def _format_dt(value) -> str:
    try:
        dt = pd.to_datetime(value, errors="coerce")
        return "" if pd.isna(dt) else dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ""


def render_worksheet_library_cards(
    df: pd.DataFrame,
    prefix: str = "ws",
    show_author: bool = False,
    open_in_files: bool = False,
    require_signup: bool = False,
) -> None:
    if df is None or df.empty:
        st.info(t("no_data"))
        return

    rows = df.reset_index(drop=True).to_dict("records")

    for idx in range(0, len(rows), 2):
        pair = rows[idx:idx + 2]
        cols = st.columns(2, gap="medium")

        for col_idx, row in enumerate(pair):
            row_id = row.get("id", idx + col_idx)
            title = str(row.get("title") or t("untitled_worksheet")).strip()
            subject = str(row.get("subject") or "").strip()
            topic = str(row.get("topic") or "").strip()
            title, topic = _clean_card_fields(title, topic)
            learner_stage = str(row.get("learner_stage") or "").strip()
            level_or_band = str(row.get("level_or_band") or "").strip()
            worksheet_type = str(row.get("worksheet_type") or "").strip()
            source_type = str(row.get("source_type") or "").strip()
            author_name = str(row.get("author_name") or "").strip()
            created_at = _format_dt(row.get("created_at"))

            subject_label = ""
            if subject:
                subj_key = "subject_" + subject.lower().replace(" ", "_")
                subject_label = t(subj_key)

            level_label = ""
            if level_or_band:
                if level_or_band in ["A1", "A2", "B1", "B2", "C1", "C2"]:
                    level_label = level_or_band
                else:
                    level_label = t(level_or_band)

            stage_label = t(learner_stage) if learner_stage else ""
            ws_type_label = t(worksheet_type) if worksheet_type else ""
            source_label = t("mode_ai") if source_type == "ai" else t("mode_template")

            safe_title = html.escape(title)
            safe_author = html.escape(author_name)
            preview_text = html.escape((topic or t("no_description_available"))[:180])

            chips = "".join([
                f'<span class="cm-resource-chip">📚 {html.escape(subject_label)}</span>' if subject_label else "",
                f'<span class="cm-resource-chip">🧩 {html.escape(ws_type_label)}</span>' if ws_type_label else "",
                f'<span class="cm-resource-chip">👥 {html.escape(stage_label)}</span>' if stage_label else "",
                f'<span class="cm-resource-chip">🏷️ {html.escape(level_label)}</span>' if level_label else "",
                f'<span class="cm-resource-chip">⚙️ {html.escape(source_label)}</span>' if source_label else "",
            ])

            meta = "".join([
                f'<div class="cm-resource-meta">👤 {safe_author}</div>' if show_author and author_name else "",
                f'<div class="cm-resource-meta">🕒 {html.escape(created_at)}</div>' if created_at else "",
            ])

            card_html = (
                f'<div class="cm-resource-card cm-resource-worksheet">'
                f'<div class="cm-resource-card__title">{safe_title}</div>'
                f'<div class="cm-resource-chip-row">{chips}</div>'
                f'<div class="cm-resource-preview">{preview_text}</div>'
                f'{meta}'
                f'</div>'
            )

            with cols[col_idx]:
                st.markdown(card_html, unsafe_allow_html=True)

                if st.button(
                    t("preview"),
                    key=f"{prefix}_preview_{row_id}_{idx}_{col_idx}",
                    use_container_width=True,
                ):
                    st.session_state["files_selected_worksheet"] = row.get("worksheet_json") or {}
                    st.session_state["files_ws_subject"] = subject
                    st.session_state["files_ws_stage"] = learner_stage
                    st.session_state["files_ws_level"] = level_or_band
                    st.session_state["files_ws_type"] = worksheet_type
                    st.session_state["files_ws_topic"] = topic
                    st.session_state["files_ws_title"] = title

                    if require_signup:
                        st.session_state["_post_signup_open_panel"] = "files"
                        st.session_state["_post_signup_open_tab"] = "community_library"
                        st.session_state["_explore_go_signup"] = True
                    elif open_in_files:
                        home_go("home", panel="files")
                    else:
                        st.toast(t("scroll_down_to_view"))

                    st.rerun()


# ── Render worksheet result ──────────────────────────────────────────
def render_worksheet_result(ws: dict, read_only: bool = False, **meta) -> None:
    if not ws:
        return

    ws = _normalize_worksheet_unicode(ws)
    ws = _clean_worksheet_data(ws)

    if not read_only:
        st.success(t("worksheet_ready"))
        warning = st.session_state.get("worksheet_warning")
        if warning:
            st.warning(warning)

    st.markdown(f"### {_normalize_text(ws.get('title', ''))}")
    st.caption(
        f"{t('plan_language')}: {_normalize_text(ws.get('plan_language', '')).upper()} · "
        f"{t('student_material_language')}: {_normalize_text(ws.get('student_material_language', '')).upper()}"
    )

    if ws.get("instructions"):
        st.markdown(f"**{t('ws_instructions')}**")
        st.write(_normalize_text(ws["instructions"]))

    if ws.get("worksheet_type") == "reading_comprehension" and str(ws.get("reading_passage") or "").strip():
        st.markdown(f"**{t('ws_reading_passage')}**")
        st.write(_normalize_text(ws["reading_passage"]))

    if ws.get("vocabulary_bank"):
        st.markdown(f"**{t('ws_vocabulary_bank')}**")
        st.write(", ".join(_normalize_text_list(ws["vocabulary_bank"])))

    wordsearch_grid = None
    wordsearch_placements = None

    if ws.get("worksheet_type") == "word_search_vocab":
        st.markdown(f"**{t('word_search_grid')}**")
        wordsearch_seed = "|".join(_normalize_wordsearch_words(ws.get("vocabulary_bank", [])))
        wordsearch_grid, _, wordsearch_placements = _generate_wordsearch_grid(
            ws.get("vocabulary_bank", []),
            seed=wordsearch_seed,
        )
        _render_wordsearch_grid(wordsearch_grid)

    if ws.get("worksheet_type") == "matching":
        st.markdown(f"**{t('ws_matching_task') if t('ws_matching_task') != 'ws_matching_task' else t('match_the_items')}**")
        _render_matching_exercise(ws)

    elif ws.get("worksheet_type") == "true_false":
        _render_true_false_exercise(ws)

    elif ws.get("worksheet_type") == "multiple_choice":
        st.markdown(f"**{t('ws_questions')}**")
        _render_multiple_choice_exercise(ws)

    elif ws.get("worksheet_type") != "word_search_vocab" and ws.get("questions"):
        st.markdown(f"**{t('ws_questions')}**")
        for idx, q in enumerate(ws["questions"], 1):
            st.write(f"{idx}. {_strip_leading_number(_normalize_text(q))}")

    if ws.get("worksheet_type") == "word_search_vocab":
        with st.expander(t("ws_answer_key"), expanded=False):
            _render_wordsearch_answer_grid(wordsearch_grid, wordsearch_placements)

    elif ws.get("worksheet_type") == "matching":
        with st.expander(t("ws_answer_key"), expanded=False):
            _render_matching_answer_key(ws)

    elif ws.get("worksheet_type") == "true_false":
        with st.expander(t("ws_answer_key"), expanded=False):
            _render_true_false_answer_key(ws)

    elif ws.get("worksheet_type") == "multiple_choice":
        with st.expander(t("ws_answer_key"), expanded=False):
            _render_multiple_choice_answer_key(ws)

    elif ws.get("answer_key"):
        with st.expander(t("ws_answer_key"), expanded=False):
            for line in _split_answer_key(ws["answer_key"]):
                st.write(_normalize_text(line))

    if ws.get("teacher_notes"):
        with st.expander(t("ws_teacher_notes"), expanded=False):
            for note in ws["teacher_notes"]:
                st.write(f"- {_normalize_text(note)}")

    subject = meta.get("subject", ws.get("subject", ""))
    topic = meta.get("topic", ws.get("topic", ""))
    ws_type = meta.get("worksheet_type", ws.get("worksheet_type", ""))
    learner_stage = meta.get("learner_stage", ws.get("learner_stage", ""))
    level_or_band = meta.get("level_or_band", ws.get("level_or_band", ""))

    _pdf_kwargs = dict(
        subject=subject,
        topic=topic,
        ws_type=ws_type,
        learner_stage=learner_stage,
        level_or_band=level_or_band,
    )

    student_pdf = build_worksheet_pdf_bytes(ws, student_only=True, **_pdf_kwargs)
    teacher_pdf = build_worksheet_pdf_bytes(ws, student_only=False, **_pdf_kwargs)
    safe_title = re.sub(r"[^A-Za-z0-9._-]+", "_", str(ws.get("title") or "worksheet").strip()) or "worksheet"

    if read_only:
        dc1, dc2 = st.columns(2)
        with dc1:
            st.download_button(
                label=t("download_student_pdf"),
                data=student_pdf,
                file_name=f"{safe_title}_student.pdf",
                mime="application/pdf",
                key=f"dl_ws_stu_{safe_title}",
                use_container_width=True,
            )
        with dc2:
            st.download_button(
                label=t("download_teacher_pdf"),
                data=teacher_pdf,
                file_name=f"{safe_title}_teacher.pdf",
                mime="application/pdf",
                key=f"dl_ws_tch_{safe_title}",
                use_container_width=True,
            )
    else:
        c1, c2 = st.columns(2)
        with c1:
            if st.button(t("keep_worksheet"), key="btn_keep_ws", use_container_width=True):
                st.session_state["worksheet_kept"] = True
                st.success(t("worksheet_kept_msg"))
        with c2:
            if st.button(t("delete_worksheet"), key="btn_del_ws", use_container_width=True):
                _wb().reset_worksheet_maker_state()
                st.rerun()

        dc1, dc2 = st.columns(2)
        with dc1:
            st.download_button(
                label=t("download_student_pdf"),
                data=student_pdf,
                file_name=f"{safe_title}_student.pdf",
                mime="application/pdf",
                key=f"dl_ws_stu_inline_{safe_title}",
                use_container_width=True,
            )
        with dc2:
            st.download_button(
                label=t("download_teacher_pdf"),
                data=teacher_pdf,
                file_name=f"{safe_title}_teacher.pdf",
                mime="application/pdf",
                key=f"dl_ws_tch_inline_{safe_title}",
                use_container_width=True,
            )


# ── PDF generation ───────────────────────────────────────────────────

def build_worksheet_pdf_bytes(
    ws: dict,
    subject: str = "",
    topic: str = "",
    ws_type: str = "",
    learner_stage: str = "",
    level_or_band: str = "",
    student_only: bool = False,
) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem,
        Table, TableStyle, PageBreak, KeepTogether, CondPageBreak
    )
    from reportlab.platypus import Image as RLImage
    from reportlab.lib import colors

    ws = _normalize_worksheet_unicode(ws)
    subject = _normalize_text(subject)
    topic = _normalize_text(topic)
    ws_type = _normalize_text(ws_type)
    learner_stage = _normalize_text(learner_stage)
    level_or_band = _normalize_text(level_or_band)

    plan_lang = _normalize_text(ws.get("plan_language") or "").strip().lower()
    student_lang = _normalize_text(ws.get("student_material_language") or "").strip().lower()
    pdf_lang = plan_lang or student_lang or "en"

    def _t_pdf(key: str, **kwargs):
        try:
            return t(key, lang=pdf_lang, **kwargs)
        except TypeError:
            return t(key, **kwargs)

    # ── Centralised font + style setup ────────────────────────
    body_font, bold_font = ensure_pdf_fonts_registered()
    _L = get_pdf_layout_constants()
    _S = get_student_pdf_styles(body_font, bold_font)
    _AK = get_answer_key_pdf_styles(body_font, bold_font)

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        **_L["margins"],
    )

    styles = getSampleStyleSheet()

    title_style      = _S["title"]
    heading_style    = _S["section"]
    body_style       = _S["body"]
    mc_option_style  = _S["mc_option"]
    mc_stem_style    = _S["mc_stem"]
    line_style       = _S["line"]

    story = []

    wordsearch_grid = None
    wordsearch_placements = None

    if ws.get("worksheet_type") == "word_search_vocab":
        wordsearch_seed = "|".join(_normalize_wordsearch_words(ws.get("vocabulary_bank", [])))
        wordsearch_grid, _, wordsearch_placements = _generate_wordsearch_grid(
            ws.get("vocabulary_bank", []),
            seed=wordsearch_seed,
            size=12,
        )

    # ── Branding-aware header ─────────────────────────────────────
    from helpers.branding import get_user_branding, build_worksheet_header, has_custom_branding

    _branding = get_user_branding()

    # Student worksheet uses school header if enabled; answer key uses standard
    if student_only or not student_only:
        # For the student portion, use whichever header_style is configured
        build_worksheet_header(
            story, ws, _branding,
            styles=styles, doc=doc,
            bold_font=bold_font, body_font=body_font,
            _t_pdf=_t_pdf, _pdf_safe_text=_pdf_safe_text,
            subject=subject, topic=topic,
            ws_type=ws_type, learner_stage=learner_stage,
            level_or_band=level_or_band,
        )

    def _mc_item_block(item: dict, idx: int):
        block = [
            Paragraph(_pdf_safe_text(f"{idx}. {item['stem']}"), mc_stem_style),
            Spacer(1, 2),
        ]
        for opt_idx, opt in enumerate(item["options"]):
            letter = chr(65 + opt_idx)
            block.append(Paragraph(_pdf_safe_text(f"{letter}) {opt}"), mc_option_style))
        block.append(Spacer(1, 3))
        return block

    def _answer_lines(count: int = 3):
        line_flow = []
        for _ in range(count):
            line_tbl = Table(
                [[""]],
                colWidths=[16.2 * cm],
                rowHeights=[0.6 * cm],
                hAlign="LEFT",
            )
            line_tbl.setStyle(TableStyle([
                ("LINEBELOW", (0, 0), (-1, -1), 0.6, colors.HexColor("#64748B")),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]))
            line_flow.append(line_tbl)
            line_flow.append(Spacer(1, 4))
        return line_flow

    def _balanced_split(total_count: int) -> int:
        split_at = (total_count + 1) // 2
        if total_count - split_at == 1 and split_at > 2:
            split_at -= 1
        return split_at

    def _sec(title_key, value):
        if not value:
            return
        story.append(Paragraph(_pdf_safe_text(_t_pdf(title_key)), heading_style))
        if isinstance(value, list):
            items = [ListItem(Paragraph(_pdf_safe_text(x), body_style)) for x in value if str(x).strip()]
            if items:
                story.append(ListFlowable(items, bulletType="bullet"))
        else:
            story.append(Paragraph(_pdf_safe_text(value), body_style))
        story.append(Spacer(1, 6))

    def _render_vocab_bank(vocab_list):
        if not vocab_list:
            return []

        story_block = []

        story_block.append(
            Paragraph(
                _pdf_safe_text(_t_pdf("ws_vocabulary_bank")),
                heading_style
            )
        )

        cleaned_vocab = [_normalize_text(x).strip() for x in vocab_list if str(x).strip()]
        has_tail = any((" - " in item or ":" in item) for item in cleaned_vocab)

        if has_tail:
            column_count = 2
            col_widths = [8.2 * cm, 8.2 * cm]
        else:
            column_count = 5
            col_widths = [3.2 * cm, 3.2 * cm, 3.2 * cm, 3.2 * cm, 3.2 * cm]

        rows = []
        row = []

        for raw_word in cleaned_vocab:
            if " - " in raw_word:
                parts = raw_word.split(" - ", 1)
                head = _pdf_safe_text(parts[0].strip().capitalize())
                tail = _pdf_safe_text(parts[1].strip().capitalize())
                formatted = f"<b>{head}</b> — {tail}"

            elif ":" in raw_word:
                parts = raw_word.split(":", 1)
                head = _pdf_safe_text(parts[0].strip().capitalize())
                tail = _pdf_safe_text(parts[1].strip().capitalize())
                formatted = f"<b>{head}</b> — {tail}"

            else:
                formatted = f"<b>{_pdf_safe_text(raw_word.capitalize())}</b>"

            row.append(Paragraph(formatted, body_style))

            if len(row) == column_count:
                rows.append(row)
                row = []

        if row:
            while len(row) < column_count:
                row.append(Paragraph("", body_style))
            rows.append(row)

        table = Table(
            rows,
            colWidths=col_widths,
            hAlign="LEFT",
        )

        if column_count == 2:
            table.setStyle(
                TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LINEAFTER", (0, 0), (0, -1), 0.6, colors.HexColor("#CBD5E1")),
                    ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ])
            )
        else:
            table.setStyle(
                TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LINEAFTER", (0, 0), (0, -1), 0.4, colors.HexColor("#E2E8F0")),
                    ("LINEAFTER", (1, 0), (1, -1), 0.4, colors.HexColor("#E2E8F0")),
                    ("LINEAFTER", (2, 0), (2, -1), 0.4, colors.HexColor("#E2E8F0")),
                    ("LINEAFTER", (3, 0), (3, -1), 0.4, colors.HexColor("#E2E8F0")),
                    ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ])
            )

        story_block.append(table)
        story_block.append(Spacer(1, 6))

        return story_block

    # Skip instructions if school header already rendered them
    _school_header_active = (
        _branding.get("header_style") == "school"
        and _branding.get("header_enabled", False)
    )
    if not _school_header_active:
        _sec("ws_instructions", ws.get("instructions", ""))

    if ws.get("vocabulary_bank"):
        story.extend(_render_vocab_bank(ws.get("vocabulary_bank")))

    if ws.get("worksheet_type") == "word_search_vocab":
        grid = wordsearch_grid
        if grid:
            story.append(Paragraph(_pdf_safe_text(_t_pdf("word_search_grid")), heading_style))
            story.append(Spacer(1, 12))

            page_width = A4[0] - doc.leftMargin - doc.rightMargin
            grid_size = len(grid)
            cell_size = (page_width / grid_size) * 0.75

            grid_cell_style = ParagraphStyle(
                "GridCell",
                parent=body_style,
                fontName=bold_font,
                fontSize=max(10, min(12, int(cell_size / 1.4))),
                leading=max(10, int(cell_size / 1.2)),
                alignment=1,
            )

            table_data = [
                [Paragraph(_pdf_safe_text(ch), grid_cell_style) for ch in row]
                for row in grid
            ]

            ws_table = Table(
                table_data,
                colWidths=[cell_size] * grid_size,
                rowHeights=[cell_size] * grid_size,
                hAlign="CENTER",
            )

            ws_table.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#94A3B8")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]))

            story.append(ws_table)
            story.append(Spacer(1, 12))

    if ws.get("worksheet_type") == "reading_comprehension" and str(ws.get("reading_passage") or "").strip():
        _sec("ws_reading_passage", ws["reading_passage"])

    questions = ws.get("questions", [])

    if ws.get("worksheet_type") == "matching":
        left_items, right_items, _ = _build_matching_columns(ws)

        if left_items and right_items:
            story.append(
                Paragraph(
                    _pdf_safe_text(
                        _t_pdf("ws_matching_task") if _t_pdf("ws_matching_task") != "ws_matching_task" else _t_pdf("match_the_items")
                    ),
                    heading_style
                )
            )
            story.append(Spacer(1, 6))

            box_style = _S["box_label"]

            rows = []
            max_len = max(len(left_items), len(right_items))

            for i in range(max_len):
                left_text = f"{i+1}. {_strip_leading_enum(left_items[i])}" if i < len(left_items) else ""
                box_text = "[   ]" if i < len(left_items) else ""
                right_text = f"{chr(97+i)}) {_strip_leading_enum(right_items[i])}" if i < len(right_items) else ""

                rows.append([
                    Paragraph(_pdf_safe_text(left_text), body_style),
                    Paragraph(_pdf_safe_text(box_text), box_style),
                    Paragraph(_pdf_safe_text(right_text), body_style),
                ])

            match_table = Table(
                rows,
                colWidths=[9.0 * cm, 1.0 * cm, 6.4 * cm],
                hAlign="LEFT",
            )

            match_table.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 0), (1, -1), "CENTER"),
                ("LEFTPADDING", (0, 0), (0, -1), 2),
                ("RIGHTPADDING", (0, 0), (0, -1), 10),
                ("LEFTPADDING", (1, 0), (1, -1), 0),
                ("RIGHTPADDING", (1, 0), (1, -1), 0),
                ("LEFTPADDING", (2, 0), (2, -1), 10),
                ("RIGHTPADDING", (2, 0), (2, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]))

            story.append(match_table)
            story.append(Spacer(1, 8))

    elif ws.get("worksheet_type") == "true_false":
        source_text = _get_true_false_source_text(ws)
        statements = _get_true_false_statements(ws)

        if source_text:
            story.append(Paragraph(_pdf_safe_text(_t_pdf("read_and_decide_true_false")), heading_style))
            story.append(Spacer(1, 4))
            story.append(Paragraph(_pdf_safe_text(source_text), body_style))
            story.append(Spacer(1, 4))

        if statements:
            story.append(Paragraph(_pdf_safe_text(_t_pdf("ws_questions")), heading_style))
            story.append(Spacer(1, 4))

            tf_label_style = _S["tf_label"]

            tf_rows = []
            for idx, item in enumerate(statements, 1):
                statement_text = f"{idx}. {_strip_leading_enum(item)}"
                tf_rows.append([
                    Paragraph(_pdf_safe_text(statement_text), body_style),
                    Paragraph(_pdf_safe_text("True ☐   False ☐"), tf_label_style),
                ])

            tf_table = Table(
                tf_rows,
                colWidths=[11.8 * cm, 4.6 * cm],
                hAlign="LEFT",
                repeatRows=0,
            )

            tf_table.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (0, -1), 0),
                ("RIGHTPADDING", (0, 0), (0, -1), 4),
                ("LEFTPADDING", (1, 0), (1, -1), 2),
                ("RIGHTPADDING", (1, 0), (1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]))

            story.append(tf_table)
            story.append(Spacer(1, 6))

    elif ws.get("worksheet_type") == "multiple_choice":
        mc_items = _get_multiple_choice_items(ws)
        if mc_items:
            all_compact = all(_mc_item_is_compact(item) for item in mc_items)

            if all_compact:
                rows = [mc_items[i:i+2] for i in range(0, len(mc_items), 2)]

                q_num = 1
                for pair in rows:
                    story.append(CondPageBreak(6 * cm))

                    data_row = []
                    for item in pair:
                        data_row.append(_mc_item_block(item, q_num))
                        q_num += 1

                    if len(data_row) == 1:
                        data_row.append([Paragraph("", body_style)])

                    mc_table = Table(
                        [data_row],
                        colWidths=[8.2 * cm, 8.2 * cm],
                        hAlign="LEFT",
                    )
                    mc_table.setStyle(TableStyle([
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]))

                    story.append(KeepTogether([mc_table, Spacer(1, 4)]))

            else:
                for idx, item in enumerate(mc_items, 1):
                    story.append(KeepTogether(_mc_item_block(item, idx)))

    elif ws.get("worksheet_type") == "short_answer" and questions:
        story.append(Paragraph(_pdf_safe_text(_t_pdf("ws_questions")), heading_style))
        for idx, q in enumerate(questions, 1):
            block = [
                Paragraph(_pdf_safe_text(f"{idx}. {_strip_leading_number(q)}"), body_style),
                Spacer(1, 4),
                *_answer_lines(2),
                Spacer(1, 6),
            ]
            story.append(KeepTogether(block))

    elif ws.get("worksheet_type") == "reading_comprehension" and questions:
        story.append(Paragraph(_pdf_safe_text(_t_pdf("ws_questions")), heading_style))
        for idx, q in enumerate(questions, 1):
            block = [
                Paragraph(_pdf_safe_text(f"{idx}. {_strip_leading_number(q)}"), body_style),
                Spacer(1, 4),
                *_answer_lines(2),
                Spacer(1, 6),
            ]
            story.append(KeepTogether(block))

    elif ws.get("worksheet_type") == "fill_in_the_blanks" and questions:
        story.append(Paragraph(_pdf_safe_text(_t_pdf("ws_questions")), heading_style))

        for idx, q in enumerate(questions, 1):
            q = _strip_leading_number(q)
            q = re.sub(r"_+", "______________", q)
            story.append(
                Paragraph(
                    _pdf_safe_text(f"{idx}. {q}"),
                    body_style
                )
            )
            story.append(Spacer(1, 6))

    elif ws.get("worksheet_type") != "word_search_vocab" and questions:
        story.append(Paragraph(_pdf_safe_text(_t_pdf("ws_questions")), heading_style))
        for idx, q in enumerate(questions, 1):
            story.append(Paragraph(_pdf_safe_text(f"{idx}. {_strip_leading_number(q)}"), body_style))
        story.append(Spacer(1, 6))

    if not student_only:
        story.append(PageBreak())

        # Answer key page uses smaller, distinct typography
        ak_heading = _AK["section"]
        ak_body    = _AK["body"]

        if ws.get("worksheet_type") == "word_search_vocab":
            answer_grid = wordsearch_grid
            placements = wordsearch_placements

            if answer_grid:
                story.append(Paragraph(_pdf_safe_text(_t_pdf("ws_answer_key")), ak_heading))
                story.append(Spacer(1, 6))

                hit_cells = set()
                for item in placements or []:
                    for coord in item.get("coords", []):
                        hit_cells.add(tuple(coord))

                grid_size = len(answer_grid)
                page_width = A4[0] - doc.leftMargin - doc.rightMargin
                cell_size = (page_width / grid_size) * 0.85

                grid_cell_style = ParagraphStyle(
                    "GridCellAnswer",
                    parent=ak_body,
                    fontName=bold_font,
                    fontSize=max(10, min(12, int(cell_size / 1.4))),
                    leading=max(10, int(cell_size / 1.2)),
                    alignment=1,
                    textColor=_C.TEXT,
                )

                table_data = []
                for r, row in enumerate(answer_grid):
                    table_row = []
                    for c, ch in enumerate(row):
                        table_row.append(Paragraph(_pdf_safe_text(ch), grid_cell_style))
                    table_data.append(table_row)

                ws_answer_table = Table(
                    table_data,
                    colWidths=[cell_size] * grid_size,
                    rowHeights=[cell_size] * grid_size,
                    hAlign="CENTER",
                )

                style_cmds = [
                    ("GRID", (0, 0), (-1, -1), 0.5, _C.GRID),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]

                for r, c in hit_cells:
                    style_cmds.append(("BACKGROUND", (c, r), (c, r), _C.HIGHLIGHT_BG))
                    style_cmds.append(("BOX", (c, r), (c, r), 1.2, _C.HIGHLIGHT_BOX))

                ws_answer_table.setStyle(TableStyle(style_cmds))
                story.append(ws_answer_table)
                story.append(Spacer(1, 8))

        elif ws.get("worksheet_type") == "matching":
            _, _, answer_map = _build_matching_columns(ws)
            if answer_map:
                story.append(Paragraph(_pdf_safe_text(_t_pdf("ws_answer_key")), ak_heading))
                for num, letter in answer_map:
                    story.append(Paragraph(_pdf_safe_text(f"{num} \u2192 {letter}"), ak_body))
                story.append(Spacer(1, 6))

        elif ws.get("worksheet_type") == "true_false":
            ak = ws.get("answer_key", "")
            if ak:
                story.append(Paragraph(_pdf_safe_text(_t_pdf("ws_answer_key")), ak_heading))
                for line in _split_answer_key(ak):
                    story.append(Paragraph(_pdf_safe_text(line), ak_body))
                story.append(Spacer(1, 6))

        elif ws.get("worksheet_type") == "multiple_choice":
            mc_items = _get_multiple_choice_items(ws)
            if mc_items:
                story.append(Paragraph(_pdf_safe_text(_t_pdf("ws_answer_key")), ak_heading))
                for idx, item in enumerate(mc_items, 1):
                    ans = _normalize_text(item.get("answer", "")).strip()
                    if ans:
                        story.append(Paragraph(_pdf_safe_text(f"{idx}. {ans}"), ak_body))
                story.append(Spacer(1, 6))
            else:
                ak = ws.get("answer_key", "")
                if ak:
                    story.append(Paragraph(_pdf_safe_text(_t_pdf("ws_answer_key")), ak_heading))
                    for line in _split_answer_key(ak):
                        story.append(Paragraph(_pdf_safe_text(line), ak_body))
                    story.append(Spacer(1, 6))

        else:
            ak = ws.get("answer_key", "")
            if ak:
                story.append(Paragraph(_pdf_safe_text(_t_pdf("ws_answer_key")), ak_heading))
                for line in _split_answer_key(ak):
                    story.append(Paragraph(_pdf_safe_text(line), ak_body))
                story.append(Spacer(1, 6))

        _sec("ws_teacher_notes", ws.get("teacher_notes", []))

    from helpers.branding import build_pdf_footer_handler
    _footer_handler = build_pdf_footer_handler(_branding, bold_font=body_font)
    doc.build(story, onFirstPage=_footer_handler, onLaterPages=_footer_handler)
    buf.seek(0)
    return buf.getvalue()


# ── Expander UI ──────────────────────────────────────────────────────
def render_quick_worksheet_maker_expander() -> None:
    with st.expander(t("worksheet_maker"), expanded=False):
        st.caption(t("worksheet_maker_caption"))

        usage = get_ai_worksheet_usage_status()
        st.caption(
            t(
                "ai_plans_left_today",
                remaining=usage["remaining_today"],
                limit=_wb().AI_WORKSHEET_DAILY_LIMIT,
            )
        )

        subject = st.selectbox(
            t("subject_label"),
            _lp().QUICK_SUBJECTS,
            format_func=_lp().subject_label,
            key="quick_ws_subject",
        )

        other_subject_name = ""
        if subject == "other":
            other_subject_name = st.text_input(t("other_subject_label"), key="ws_other_subject").strip()

        learner_stage = st.selectbox(
            t("learner_stage"),
            _lp().LEARNER_STAGES,
            format_func=_lp()._stage_label,
            key="ws_stage",
        )

        default_level = _lp().recommend_default_level(subject, learner_stage)
        level_options = _lp().get_level_options(subject)
        if st.session_state.get("ws_level") not in level_options:
            st.session_state["ws_level"] = default_level

        c1, c2 = st.columns(2)
        with c1:
            level_or_band = st.selectbox(
                t("level_or_band"),
                level_options,
                format_func=_lp()._level_label,
                key="ws_level",
            )
        with c2:
            worksheet_type = st.selectbox(
                t("worksheet_type_label"),
                _wb().WORKSHEET_TYPES,
                format_func=lambda x: t(x),
                key="ws_type",
            )

        topic = st.text_input(t("topic_label"), key="ws_topic")

        if st.button(t("generate_worksheet"), key="btn_gen_ws", use_container_width=True):
            if not topic.strip():
                st.error(t("enter_topic"))
            elif subject == "other" and not other_subject_name:
                st.error(t("enter_subject_name"))
            else:
                effective_subject = other_subject_name if subject == "other" else subject
                with st.spinner(t("generating")):
                    ws, warning = _wb().generate_worksheet_with_limit(
                        subject=effective_subject,
                        learner_stage=learner_stage,
                        level_or_band=level_or_band,
                        worksheet_type=worksheet_type,
                        topic=topic,
                    )

                if warning and not ws:
                    st.warning(warning)
                else:
                    ws = _normalize_worksheet_unicode(ws)
                    st.session_state["worksheet_result"] = ws
                    st.session_state["worksheet_kept"] = False
                    st.session_state["worksheet_warning"] = warning

                    save_worksheet_record(
                        subject=effective_subject,
                        learner_stage=learner_stage,
                        level_or_band=level_or_band,
                        worksheet_type=worksheet_type,
                        topic=topic,
                        worksheet=ws,
                    )

        result = st.session_state.get("worksheet_result")
        if result:
            if st.session_state.get("worksheet_kept"):
                st.info(f"📌 {t('worksheet_kept_msg')}")
            render_worksheet_result(
                result,
                subject=subject,
                learner_stage=learner_stage,
                level_or_band=level_or_band,
                worksheet_type=worksheet_type,
                topic=topic,
            )