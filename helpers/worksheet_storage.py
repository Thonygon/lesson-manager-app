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

def _wb():
    import helpers.worksheet_builder as wb
    return wb


def _lp():
    import helpers.lesson_planner as lp
    return lp


# ── Worksheet text cleanup helpers ──────────────────────────────────
_LEADING_NUM_RE = re.compile(r"^\s*\d+[\.\)\-]\s*")


def _strip_leading_number(text: str) -> str:
    """Remove a leading number like '1. ', '2) ', '3- ' from a string."""
    return _LEADING_NUM_RE.sub("", text)


def _split_answer_key(answer_key) -> list[str]:
    """Split an answer key string into individual numbered lines."""
    if isinstance(answer_key, list):
        return [str(a) for a in answer_key if str(a).strip()]
    text = str(answer_key or "")
    # Try splitting on numbered patterns like "1. ", "2. ", etc.
    parts = re.split(r"(?:^|\n)\s*(\d+[\.\)\-])", text)
    if len(parts) > 2:
        # re.split with groups: ['prefix', '1.', 'answer1', '2.', 'answer2', ...]
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
    # Fallback: split on newlines
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    return lines if lines else [text]


def _clean_worksheet_data(ws: dict) -> dict:
    """Clean questions to strip leading numbers (prevents 1. 1. doubling)."""
    out = dict(ws)
    if isinstance(out.get("questions"), list):
        out["questions"] = [_strip_leading_number(q) if isinstance(q, str) else q
                            for q in out["questions"]]
    return out

def _clean_display_text(text: str) -> str:
    s = str(text or "").strip()

    # Collapse repeated spaces
    s = re.sub(r"\s+", " ", s)

    # Remove spaces before punctuation
    s = re.sub(r"\s+([.,!?;:])", r"\1", s)

    # Normalize surrounding spaces around hyphens/slashes
    s = re.sub(r"\s*-\s*", " - ", s)
    s = re.sub(r"\s*/\s*", " / ", s)
    s = re.sub(r"\s+", " ", s).strip()

    # Capitalize first letter
    if s:
        s = s[0].upper() + s[1:]

    return s


def _clean_card_fields(title: str, topic: str) -> tuple[str, str]:
    return _clean_display_text(title), _clean_display_text(topic)

# ── Word search helpers ──────────────────────────────────────────────

def _wordsearch_safe_upper(text: str) -> str:
    s = str(text or "").strip()

    # Turkish-safe upper first
    s = (
        s.replace("i", "İ")
         .replace("ı", "I")
    )

    return s.upper()


def _normalize_wordsearch_words(words: list[str], max_words: int = 12) -> list[str]:
    out = []
    seen = set()

    for w in words or []:
        s = str(w or "").strip()

        # Remove translations inside parentheses
        # Example: "LEVANTARSE (to get up)" → "LEVANTARSE"
        s = re.sub(r"\(.*?\)", "", s)

        # Remove dash translations
        # Example: "LEVANTARSE - to get up"
        s = re.split(r"\s[-–—]\s", s)[0]

        # Remove comma translations
        # Example: "LEVANTARSE, to get up"
        s = s.split(",")[0]

        # Uppercase safely
        s = _wordsearch_safe_upper(s)

        # Keep Spanish + Turkish + Latin
        s = re.sub(r"[^A-ZÁÉÍÓÚÜÑÇĞİÖŞ0-9 ]", "", s)

        # Remove spaces
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

    directions = [
        (0, 1),   # right
        (1, 0),   # down
        (1, 1),   # down-right
        (-1, 1),  # up-right
    ]

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

                # row start range
                if dr == 0:
                    r_min, r_max = 0, size - 1
                elif dr == 1:
                    r_min, r_max = 0, size - len(word)
                else:  # dr == -1
                    r_min, r_max = len(word) - 1, size - 1

                # col start range
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

                placements.append({
                    "word": word,
                    "coords": coords,
                })
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
            "is_public": True,
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


# ── AI usage tracking (per-feature) ──────────────────────────────────

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
    today_start_utc = _dt.combine(
        today_local(), _dt.min.time()
    ).replace(tzinfo=get_app_tz()).astimezone(timezone.utc)

    limit = _wb().AI_WORKSHEET_DAILY_LIMIT
    cooldown = _wb().AI_WORKSHEET_COOLDOWN_SECONDS

    if df.empty:
        return {"used_today": 0, "remaining_today": limit, "cooldown_ok": True, "seconds_left": 0, "last_request_at": None}

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
    ws = _clean_worksheet_data(ws)

    if not read_only:
        st.success(t("worksheet_ready"))
        warning = st.session_state.get("worksheet_warning")
        if warning:
            st.warning(warning)

    st.markdown(f"### {ws.get('title', '')}")
    st.caption(
        f"{t('plan_language')}: {ws.get('plan_language', '').upper()} · "
        f"{t('student_material_language')}: {ws.get('student_material_language', '').upper()}"
    )

    if ws.get("instructions"):
        st.markdown(f"**{t('ws_instructions')}**")
        st.write(ws["instructions"])

    if ws.get("worksheet_type") == "reading_comprehension" and ws.get("reading_passage", "").strip():
        st.markdown(f"**{t('ws_reading_passage')}**")
        st.write(ws["reading_passage"])

    if ws.get("vocabulary_bank"):
        st.markdown(f"**{t('ws_vocabulary_bank')}**")
        st.write(", ".join(ws["vocabulary_bank"]))

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

    if ws.get("worksheet_type") != "word_search_vocab" and ws.get("questions"):
        st.markdown(f"**{t('ws_questions')}**")
        for idx, q in enumerate(ws["questions"], 1):
            st.write(f"{idx}. {_strip_leading_number(q)}")

    if ws.get("worksheet_type") == "word_search_vocab":
        with st.expander(t("ws_answer_key"), expanded=False):
            _render_wordsearch_answer_grid(wordsearch_grid, wordsearch_placements)

    elif ws.get("answer_key"):
        with st.expander(t("ws_answer_key"), expanded=False):
            for line in _split_answer_key(ws["answer_key"]):
                st.write(line)

    if ws.get("teacher_notes"):
        with st.expander(t("ws_teacher_notes"), expanded=False):
            for note in ws["teacher_notes"]:
                st.write(f"- {note}")

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
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem, Table, TableStyle, PageBreak
    from reportlab.platypus import Image as RLImage
    from reportlab.lib import colors

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.8*cm, rightMargin=1.8*cm, topMargin=1.5*cm, bottomMargin=1.5*cm)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle("WsTitle", parent=styles["Title"], fontSize=18, leading=22, textColor=colors.HexColor("#1D4ED8"), spaceAfter=10)
    heading_style = ParagraphStyle("WsH", parent=styles["Heading2"], fontSize=12, leading=15, textColor=colors.HexColor("#0F172A"), spaceBefore=8, spaceAfter=4)
    body_style = ParagraphStyle("WsBody", parent=styles["BodyText"], fontSize=10.5, leading=14, textColor=colors.HexColor("#0F172A"), spaceAfter=4)

    story = []

    wordsearch_grid = None
    wordsearch_placements = None
    wordsearch_seed = None

    if ws.get("worksheet_type") == "word_search_vocab":
        wordsearch_seed = "|".join(_normalize_wordsearch_words(ws.get("vocabulary_bank", [])))
        wordsearch_grid, _, wordsearch_placements = _generate_wordsearch_grid(
            ws.get("vocabulary_bank", []),
            seed=wordsearch_seed,
            size=12,  # safe now because helper auto-expands if needed
        )    

    logo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, "static", "logo_classio_light.png"))
    if os.path.isfile(logo_path):
        story.append(RLImage(logo_path, width=2.8*cm, height=2.8*cm, kind="proportional"))
        story.append(Spacer(1, 6))

    story.append(Paragraph(str(ws.get("title") or t("untitled_worksheet")), title_style))

    meta_parts = []
    if subject:
        subject_key = "subject_" + str(subject).strip().lower().replace(" ", "_")
        subject_label = t(subject_key)
        if subject_label == subject_key:
            subject_label = str(subject).strip()
        meta_parts.append(f"<b>{t('subject_label')}:</b> {subject_label}")
    if topic:
        meta_parts.append(f"<b>{t('topic_label')}:</b> {topic}")
    if ws_type:
        meta_parts.append(f"<b>{t('worksheet_type_label')}:</b> {t(ws_type)}")
    if learner_stage:
        meta_parts.append(f"<b>{t('learner_stage')}:</b> {t(learner_stage)}")
    if level_or_band:
        lbl = level_or_band if level_or_band in ["A1","A2","B1","B2","C1","C2"] else t(level_or_band)
        meta_parts.append(f"<b>{t('level_or_band')}:</b> {lbl}")
    if meta_parts:
        story.append(Paragraph(" | ".join(meta_parts), body_style))
        story.append(Spacer(1, 8))

    def _sec(title_key, value):
        if not value:
            return
        story.append(Paragraph(t(title_key), heading_style))
        if isinstance(value, list):
            items = [ListItem(Paragraph(str(x), body_style)) for x in value if str(x).strip()]
            if items:
                story.append(ListFlowable(items, bulletType="bullet"))
        else:
            story.append(Paragraph(str(value), body_style))
        story.append(Spacer(1, 6))

    _sec("ws_instructions", ws.get("instructions", ""))

    if ws.get("vocabulary_bank"):
        _sec("ws_vocabulary_bank", ", ".join(ws["vocabulary_bank"]))

    if ws.get("worksheet_type") == "word_search_vocab":
        grid = wordsearch_grid

        if grid:
            story.append(Paragraph(t("word_search_grid"), heading_style))
            story.append(Spacer(1, 12))  

            page_width = A4[0] - doc.leftMargin - doc.rightMargin
            grid_size = len(grid)
            cell_size = (page_width / grid_size) * 0.85

            grid_cell_style = ParagraphStyle(
                "GridCell",
                parent=body_style,
                fontName="Courier-Bold",
                fontSize=max(10, min(12, int(cell_size / 1.4))),
                leading=max(10, int(cell_size / 1.2)),
                alignment=1,
            )

            table_data = [
                [Paragraph(ch, grid_cell_style) for ch in row]
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
    # Reading passage
    if ws.get("worksheet_type") == "reading_comprehension" and str(ws.get("reading_passage") or "").strip():
        _sec("ws_reading_passage", ws["reading_passage"])

    # Questions as numbered list
    questions = ws.get("questions", [])
    if ws.get("worksheet_type") != "word_search_vocab" and questions:
        story.append(Paragraph(t("ws_questions"), heading_style))
        for idx, q in enumerate(questions, 1):
            story.append(Paragraph(f"{idx}. {_strip_leading_number(q)}", body_style))
        story.append(Spacer(1, 6))

    if not student_only:
        if ws.get("worksheet_type") == "word_search_vocab":
            answer_grid = wordsearch_grid
            placements = wordsearch_placements

            if answer_grid:
                story.append(PageBreak())
                story.append(Paragraph(t("ws_answer_key"), heading_style))
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
                    parent=body_style,
                    fontName="Courier-Bold",
                    fontSize=max(10, min(12, int(cell_size / 1.4))),
                    leading=max(10, int(cell_size / 1.2)),
                    alignment=1,
                    textColor=colors.HexColor("#0F172A"),
                )

                table_data = []
                for r, row in enumerate(answer_grid):
                    table_row = []
                    for c, ch in enumerate(row):
                        table_row.append(Paragraph(ch, grid_cell_style))
                    table_data.append(table_row)

                ws_answer_table = Table(
                    table_data,
                    colWidths=[cell_size] * grid_size,
                    rowHeights=[cell_size] * grid_size,
                    hAlign="CENTER",
                )

                style_cmds = [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#94A3B8")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]

                for r, c in hit_cells:
                    style_cmds.append(("BACKGROUND", (c, r), (c, r), colors.HexColor("#DBEAFE")))
                    style_cmds.append(("BOX", (c, r), (c, r), 1.2, colors.HexColor("#2563EB")))

                ws_answer_table.setStyle(TableStyle(style_cmds))
                story.append(ws_answer_table)
                story.append(Spacer(1, 8))

        else:
            ak = ws.get("answer_key", "")
            if ak:
                story.append(Paragraph(t("ws_answer_key"), heading_style))
                for line in _split_answer_key(ak):
                    story.append(Paragraph(str(line), body_style))
                story.append(Spacer(1, 6))

        _sec("ws_teacher_notes", ws.get("teacher_notes", []))

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()


# ── Expander UI ──────────────────────────────────────────────────────

def render_quick_worksheet_maker_expander() -> None:
    with st.expander(t("worksheet_maker"), expanded=False):
        st.caption(t("worksheet_maker_caption"))

        usage = get_ai_worksheet_usage_status()
        st.caption(t("ai_plans_left_today", remaining=usage["remaining_today"], limit=_wb().AI_WORKSHEET_DAILY_LIMIT))

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
                    st.session_state["worksheet_result"] = ws
                    st.session_state["worksheet_kept"] = False
                    st.session_state["worksheet_warning"] = warning

                    # Auto-save to DB + community
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

# =========================
