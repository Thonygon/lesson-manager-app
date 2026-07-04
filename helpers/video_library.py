from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import streamlit as st

from core.database import clear_app_caches, get_sb, load_profile_row, register_cache
from core.i18n import t
from core.navigation import go_to
from core.state import get_current_user_id
from helpers.archive_utils import filter_archived_rows, is_archived_status
from helpers.recommendation_models import log_teacher_material_open
from helpers.resource_gallery import inject_resource_gallery_styles, render_gallery_card_html

YOUTUBE_HOST_MARKERS = (
    "youtube.com",
    "youtu.be",
    "youtube-nocookie.com",
)

_SUBJECT_NORMALIZE = {
    "english": "english",
    "inglés": "english",
    "ingilizce": "english",
    "spanish": "spanish",
    "español": "spanish",
    "ispanyolca": "spanish",
    "mathematics": "mathematics",
    "matemáticas": "mathematics",
    "matematik": "mathematics",
    "math": "mathematics",
    "maths": "mathematics",
    "science": "science",
    "ciencias": "science",
    "fen": "science",
    "fen_bilimleri": "science",
    "music": "music",
    "música": "music",
    "müzik": "music",
    "study_skills": "study_skills",
    "técnicas_de_estudio": "study_skills",
    "çalışma_becerileri": "study_skills",
    "turkish": "turkish",
    "turco": "turkish",
    "türkçe": "turkish",
    "other": "other",
    "otro": "other",
    "otra_materia": "other",
    "diğer": "other",
    "otra": "other",
}


def _rows(result) -> list[dict]:
    return getattr(result, "data", None) or []


def _profile_name_map(user_ids: list[str]) -> dict[str, dict]:
    ids = [str(item or "").strip() for item in user_ids if str(item or "").strip()]
    if not ids:
        return {}
    try:
        rows = _rows(
            get_sb()
            .table("profiles")
            .select("user_id,display_name,username,email")
            .in_("user_id", ids)
            .limit(max(1, len(ids)))
            .execute()
        )
        return {str(row.get("user_id") or "").strip(): row for row in rows}
    except Exception:
        return {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _clean_display_text(value: Any) -> str:
    text = _clean_text(value)
    if text:
        return text[0].upper() + text[1:]
    return ""


def normalize_subject(raw: Any) -> str:
    key = str(raw or "").strip().lower().replace(" ", "_")
    return _SUBJECT_NORMALIZE.get(key, key)


def subject_label(subject_key: Any) -> str:
    key = str(subject_key or "").strip().lower().replace(" ", "_")
    if key == "other":
        return t("subject_other")
    translated = t(f"subject_{key}")
    return translated if translated and translated != f"subject_{key}" else _clean_display_text(subject_key or key)


def parse_youtube_video_id(value: Any) -> str:
    text = _clean_text(value)
    if not text:
        return ""
    patterns = [
        r"(?:v=)([A-Za-z0-9_-]{11})",
        r"(?:youtu\.be/)([A-Za-z0-9_-]{11})",
        r"(?:embed/)([A-Za-z0-9_-]{11})",
        r"(?:shorts/)([A-Za-z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", text):
        return text
    return ""


def is_supported_youtube_url(value: Any) -> bool:
    text = _clean_text(value).lower()
    return bool(text and any(host in text for host in YOUTUBE_HOST_MARKERS) and parse_youtube_video_id(text))


def youtube_watch_url(video_id: Any) -> str:
    safe_id = parse_youtube_video_id(video_id)
    return f"https://www.youtube.com/watch?v={safe_id}" if safe_id else ""


def youtube_embed_url(video_id: Any) -> str:
    safe_id = parse_youtube_video_id(video_id)
    return f"https://www.youtube.com/embed/{safe_id}" if safe_id else ""


def youtube_thumbnail_url(video_id: Any) -> str:
    safe_id = parse_youtube_video_id(video_id)
    return f"https://img.youtube.com/vi/{safe_id}/hqdefault.jpg" if safe_id else ""


def _normalize_video_row(row: dict) -> dict:
    row = dict(row or {})
    video_id = parse_youtube_video_id(row.get("video_id") or row.get("youtube_url") or row.get("watch_url"))
    youtube_url = _clean_text(row.get("youtube_url") or youtube_watch_url(video_id))
    row["video_id"] = video_id
    row["youtube_url"] = youtube_url
    row["watch_url"] = youtube_watch_url(video_id) or youtube_url
    row["embed_url"] = youtube_embed_url(video_id)
    row["thumbnail_url"] = _clean_text(row.get("thumbnail_url") or youtube_thumbnail_url(video_id))
    row["title"] = _clean_display_text(row.get("title") or t("video_default_title"))
    row["topic"] = _clean_display_text(row.get("topic") or row.get("title") or "")
    row["subject"] = normalize_subject(row.get("subject") or "")
    row["subject_display"] = subject_label(row["subject"]) if row["subject"] else _clean_display_text(row.get("custom_subject_name") or "")
    row["description"] = _clean_text(row.get("description"))
    row["author_name"] = _clean_display_text(row.get("author_name"))
    return row


def _video_row_to_card(row: dict) -> str:
    row = _normalize_video_row(row)
    chips = "".join(
        [
            f'<span class="cm-resource-chip">🎬 {html.escape(t("video_label"))}</span>',
            f'<span class="cm-resource-chip">📚 {html.escape(row.get("subject_display") or t("subject_other"))}</span>' if row.get("subject_display") else "",
            f'<span class="cm-resource-chip">🏷️ {html.escape(str(row.get("level_or_band") or ""))}</span>' if row.get("level_or_band") else "",
        ]
    )
    meta = "".join(
        [
            f'<div class="cm-resource-meta">👤 {html.escape(str(row.get("author_name") or ""))}</div>' if row.get("author_name") else "",
            f'<div class="cm-resource-meta">🕒 {html.escape(str(row.get("created_at") or ""))[:10]}</div>' if row.get("created_at") else "",
        ]
    )
    return render_gallery_card_html(
        kind="video",
        title=row.get("title") or t("video_default_title"),
        chips_html=chips,
        description=row.get("description") or row.get("topic") or t("video_default_description"),
        meta_html=meta,
        image_url=row.get("thumbnail_url") or "",
        placeholder_label=t("video_label"),
    )


def save_video_resource(
    *,
    youtube_url: str,
    title: str = "",
    description: str = "",
    subject: str = "",
    custom_subject_name: str = "",
    learner_stage: str = "",
    level_or_band: str = "",
    topic: str = "",
    is_public: bool = False,
) -> tuple[bool, int | None, str]:
    import helpers.lesson_planner as _lp

    user_id = str(get_current_user_id() or "").strip()
    if not user_id:
        return False, None, "no_data"
    if not is_supported_youtube_url(youtube_url):
        return False, None, "video_invalid_url"
    video_id = parse_youtube_video_id(youtube_url)
    normalized_subject = normalize_subject(subject)
    normalized_stage = _clean_text(learner_stage)
    if normalized_stage not in _lp.LEARNER_STAGES:
        normalized_stage = ""
    level_options = _lp.get_level_options(normalized_subject)
    normalized_level = _clean_text(level_or_band)
    if normalized_level not in level_options:
        normalized_level = _lp.recommend_default_level(normalized_subject, normalized_stage or _lp.LEARNER_STAGES[0])
    payload = {
        "user_id": user_id,
        "video_id": video_id,
        "youtube_url": youtube_watch_url(video_id) or _clean_text(youtube_url),
        "thumbnail_url": youtube_thumbnail_url(video_id),
        "title": _clean_display_text(title) or t("video_default_title"),
        "description": _clean_text(description),
        "subject": normalized_subject,
        "custom_subject_name": _clean_display_text(custom_subject_name),
        "learner_stage": normalized_stage,
        "level_or_band": normalized_level,
        "topic": _clean_display_text(topic),
        "is_public": bool(is_public),
        "status": "active",
        "updated_at": _now_iso(),
    }
    try:
        existing = _rows(
            get_sb()
            .table("videos")
            .select("id")
            .eq("user_id", user_id)
            .eq("video_id", video_id)
            .limit(1)
            .execute()
        )
        if existing:
            video_id_value = int(existing[0].get("id") or 0)
            get_sb().table("videos").update(payload).eq("id", video_id_value).eq("user_id", user_id).execute()
            clear_app_caches()
            return True, video_id_value, "video_saved_success"

        payload["created_at"] = _now_iso()
        inserted = _rows(get_sb().table("videos").insert(payload).execute())
        clear_app_caches()
        return True, int((inserted[0] if inserted else {}).get("id") or 0) or None, "video_saved_success"
    except Exception as exc:
        if "videos" in str(exc or "").lower():
            return False, None, "video_table_unavailable"
        return False, None, "save_failed"


@st.cache_data(ttl=45, show_spinner=False)
def _load_my_videos_cached(uid: str, limit: int = 500) -> pd.DataFrame:
    if not uid:
        return pd.DataFrame()
    try:
        rows = _rows(
            get_sb()
            .table("videos")
            .select("*")
            .eq("user_id", uid)
            .order("updated_at", desc=True)
            .limit(limit)
            .execute()
        )
        return pd.DataFrame([_normalize_video_row(row) for row in rows])
    except Exception:
        return pd.DataFrame()


register_cache(_load_my_videos_cached)


def load_my_videos(*, include_archived: bool = False, archived_only: bool = False) -> pd.DataFrame:
    df = _load_my_videos_cached(str(get_current_user_id() or ""))
    if df.empty:
        return df
    if archived_only:
        return df[df.get("status", pd.Series(dtype=str)).astype(str).map(is_archived_status)].reset_index(drop=True)
    if include_archived:
        return df.reset_index(drop=True)
    return filter_archived_rows(df).reset_index(drop=True)


@st.cache_data(ttl=45, show_spinner=False)
def _load_public_videos_cached(limit: int = 500) -> pd.DataFrame:
    try:
        rows = _rows(
            get_sb()
            .table("videos")
            .select("*")
            .eq("is_public", True)
            .order("updated_at", desc=True)
            .limit(limit)
            .execute()
        )
    except Exception:
        return pd.DataFrame()
    profiles = _profile_name_map([str(row.get("user_id") or "") for row in rows])
    normalized_rows = []
    for row in rows:
        profile = profiles.get(str(row.get("user_id") or "").strip()) or load_profile_row(str(row.get("user_id") or ""))
        normalized_rows.append(
            _normalize_video_row(
                {
                    **row,
                    "author_name": profile.get("display_name") or profile.get("username") or profile.get("email") or "",
                }
            )
        )
    return pd.DataFrame(normalized_rows)


register_cache(_load_public_videos_cached)


def load_public_videos() -> pd.DataFrame:
    return filter_archived_rows(_load_public_videos_cached()).reset_index(drop=True)


@st.cache_data(ttl=45, show_spinner=False)
def load_video_record(video_record_id: int | str) -> dict:
    safe_id = str(video_record_id or "").strip()
    if not safe_id:
        return {}
    try:
        rows = _rows(get_sb().table("videos").select("*").eq("id", safe_id).limit(1).execute())
        return _normalize_video_row(rows[0]) if rows else {}
    except Exception:
        return {}


def _open_video_library_record(
    row: dict,
    *,
    open_in_files: bool = False,
    require_signup: bool = False,
    expand_assign: bool = False,
) -> None:
    if require_signup:
        st.session_state["_post_signup_open_panel"] = "files"
        st.session_state["_post_signup_open_tab"] = "my_videos"
        st.session_state["_explore_go_signup"] = True
        st.rerun()
    row = _normalize_video_row(row)
    st.session_state["files_selected_video"] = row
    st.session_state["files_selected_video_id"] = row.get("id")
    st.session_state["files_selected_video_status"] = str(row.get("status") or "").strip()
    st.session_state["files_selected_video_assign_expanded"] = bool(expand_assign)
    current_user_id = str(get_current_user_id() or "").strip()
    row_owner_id = str(row.get("user_id") or "").strip()
    log_teacher_material_open(
        row,
        "video",
        "own" if current_user_id and current_user_id == row_owner_id else "community",
        surface="home_preview" if open_in_files else "resources",
    )
    if open_in_files:
        go_to("resources")
    else:
        st.toast(t("scroll_down_to_view"))
    st.rerun()


def update_video_visibility(video_id: int, is_public: bool) -> tuple[bool, str]:
    uid = str(get_current_user_id() or "").strip()
    if not uid or video_id <= 0:
        return False, "save_failed"
    try:
        get_sb().table("videos").update({"is_public": bool(is_public), "updated_at": _now_iso()}).eq("id", int(video_id)).eq("user_id", uid).execute()
        clear_app_caches()
        return True, "video_visibility_updated"
    except Exception:
        return False, "save_failed"


def update_video_archive(video_id: int, archived: bool) -> tuple[bool, str]:
    uid = str(get_current_user_id() or "").strip()
    if not uid or video_id <= 0:
        return False, "save_failed"
    try:
        get_sb().table("videos").update({"status": "archived" if archived else "active", "updated_at": _now_iso()}).eq("id", int(video_id)).eq("user_id", uid).execute()
        clear_app_caches()
        return True, "video_archive_updated"
    except Exception:
        return False, "save_failed"


def render_video_library_cards(
    df: pd.DataFrame,
    *,
    prefix: str,
    show_author: bool = False,
    open_in_files: bool = False,
    require_signup: bool = False,
    allow_visibility_toggle: bool = False,
    allow_archive_toggle: bool = False,
) -> None:
    if df is None or df.empty:
        return
    inject_resource_gallery_styles()
    rows = [_normalize_video_row(row) for row in df.reset_index(drop=True).to_dict("records")]
    for idx in range(0, len(rows), 3):
        trio = rows[idx: idx + 3]
        cols = st.columns(3, gap="medium")
        for col_idx, row in enumerate(trio):
            row_id = row.get("id", idx + col_idx)
            with cols[col_idx]:
                display_row = dict(row)
                if not show_author:
                    display_row["author_name"] = ""
                st.markdown(_video_row_to_card(display_row), unsafe_allow_html=True)
                is_owner = str(row.get("user_id") or "").strip() == str(get_current_user_id() or "").strip()
                show_owner_controls = is_owner and (allow_visibility_toggle or allow_archive_toggle)
                action_cols = st.columns([1, 1, 1, 1] if show_owner_controls else [1, 1])
                with action_cols[0]:
                    if st.button(t("watch_video"), key=f"{prefix}_watch_{row_id}_{idx}_{col_idx}", use_container_width=True):
                        _open_video_library_record(row, open_in_files=open_in_files, require_signup=require_signup, expand_assign=False)
                with action_cols[1]:
                    if st.button(
                        t("assign_to_student"),
                        key=f"{prefix}_assign_{row_id}_{idx}_{col_idx}",
                        use_container_width=True,
                        disabled=is_archived_status(row.get("status")),
                    ):
                        _open_video_library_record(row, open_in_files=open_in_files, require_signup=require_signup, expand_assign=True)
                if show_owner_controls:
                    with action_cols[2]:
                        if allow_visibility_toggle and is_owner and str(row.get("id") or "").strip() and not is_archived_status(row.get("status")):
                            public_now = bool(row.get("is_public"))
                            toggle_key = re.sub(r"[^A-Za-z0-9._-]+", "_", str(row.get("id") or "").strip()) or f"{idx}_{col_idx}"
                            new_public = st.toggle(
                                t("public_toggle_label"),
                                value=public_now,
                                key=f"{prefix}_toggle_visibility_{toggle_key}_{idx}_{col_idx}",
                            )
                            if new_public != public_now:
                                ok, key = update_video_visibility(int(row.get("id") or 0), new_public)
                                if ok:
                                    st.success(
                                        t(
                                            "resource_visibility_updated",
                                            visibility=t("public_label") if new_public else t("private_label"),
                                        )
                                    )
                                    st.rerun()
                                st.error(t("resource_visibility_update_failed", error=key))
                    with action_cols[3]:
                        if allow_archive_toggle and is_owner and str(row.get("id") or "").strip():
                            archived_now = is_archived_status(row.get("status"))
                            toggle_key = re.sub(r"[^A-Za-z0-9._-]+", "_", str(row.get("id") or "").strip()) or f"{idx}_{col_idx}"
                            new_archived = st.toggle(
                                t("archive_toggle_label"),
                                value=archived_now,
                                key=f"{prefix}_toggle_archive_{toggle_key}_{idx}_{col_idx}",
                            )
                            if new_archived != archived_now:
                                ok, key = update_video_archive(int(row.get("id") or 0), new_archived)
                                if ok:
                                    st.success(
                                        t(
                                            "resource_archive_updated",
                                            state=t("archived_label") if new_archived else t("restored_label"),
                                        )
                                    )
                                    st.rerun()
                                st.error(t("resource_archive_update_failed", error=key))


def render_video_detail(
    video: dict,
    *,
    action_key_prefix: str,
    allow_assign: bool = True,
    assign_expanded: bool = False,
) -> None:
    video = _normalize_video_row(video)
    if not video:
        st.info(t("no_data"))
        return
    inject_resource_gallery_styles()
    st.markdown(f"### {html.escape(str(video.get('title') or t('video_default_title')))}")
    meta_bits = []
    if video.get("subject_display"):
        meta_bits.append(f"📚 {html.escape(str(video.get('subject_display') or ''))}")
    if video.get("level_or_band"):
        meta_bits.append(f"🏷️ {html.escape(str(video.get('level_or_band') or ''))}")
    if video.get("topic"):
        meta_bits.append(f"🧠 {html.escape(str(video.get('topic') or ''))}")
    if meta_bits:
        st.caption(" · ".join(meta_bits))
    if video.get("watch_url"):
        st.video(video.get("watch_url"))
        st.link_button(t("open_on_youtube"), video.get("watch_url"), use_container_width=True)
    if video.get("description"):
        st.caption(video.get("description"))
    if allow_assign:
        with st.expander(t("assign_to_student"), expanded=assign_expanded):
            from helpers.teacher_student_integration import render_assignment_panel_for_video

            render_assignment_panel_for_video(
                prefix=f"{action_key_prefix}_assign_video",
                video=video,
                subject=str(video.get("subject") or ""),
                topic=str(video.get("topic") or video.get("title") or ""),
                learner_stage=str(video.get("learner_stage") or ""),
                level_or_band=str(video.get("level_or_band") or ""),
                source_record_id=video.get("id"),
            )


def _topic_link_payload(program_id: int, topic_id: int, video_id: int) -> dict:
    uid = str(get_current_user_id() or "").strip()
    return {
        "teacher_id": uid,
        "program_id": int(program_id),
        "topic_id": int(topic_id),
        "video_id": int(video_id),
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }


def attach_video_to_topic(program_id: int, topic_id: int, video_id: int) -> tuple[bool, str]:
    uid = str(get_current_user_id() or "").strip()
    if not uid or program_id <= 0 or topic_id <= 0 or video_id <= 0:
        return False, "save_failed"
    try:
        existing = _rows(
            get_sb()
            .table("learning_program_topic_videos")
            .select("id")
            .eq("teacher_id", uid)
            .eq("program_id", int(program_id))
            .eq("topic_id", int(topic_id))
            .eq("video_id", int(video_id))
            .limit(1)
            .execute()
        )
        if not existing:
            get_sb().table("learning_program_topic_videos").insert(_topic_link_payload(program_id, topic_id, video_id)).execute()
        clear_app_caches()
        return True, "video_attached_success"
    except Exception:
        return False, "video_topic_link_failed"


def detach_video_from_topic(link_id: int) -> tuple[bool, str]:
    uid = str(get_current_user_id() or "").strip()
    if not uid or link_id <= 0:
        return False, "save_failed"
    try:
        get_sb().table("learning_program_topic_videos").delete().eq("id", int(link_id)).eq("teacher_id", uid).execute()
        clear_app_caches()
        return True, "video_detached_success"
    except Exception:
        return False, "save_failed"


@st.cache_data(ttl=45, show_spinner=False)
def _load_topic_video_links_cached(program_ids_key: tuple[int, ...]) -> dict[int, list[dict]]:
    program_ids = [int(pid) for pid in program_ids_key if int(pid or 0) > 0]
    if not program_ids:
        return {}
    try:
        rows = _rows(
            get_sb()
            .table("learning_program_topic_videos")
            .select("*")
            .in_("program_id", program_ids)
            .order("created_at", desc=False)
            .execute()
        )
    except Exception:
        return {}
    video_ids = sorted({int(row.get("video_id") or 0) for row in rows if int(row.get("video_id") or 0) > 0})
    video_lookup = {int(row.get("id") or 0): _normalize_video_row(row) for row in load_videos_by_ids(video_ids)}
    topic_map: dict[int, list[dict]] = {}
    for row in rows:
        topic_id = int(row.get("topic_id") or 0)
        if topic_id <= 0:
            continue
        video = dict(video_lookup.get(int(row.get("video_id") or 0)) or {})
        if not video:
            continue
        topic_map.setdefault(topic_id, []).append({**row, "video": video})
    return topic_map


register_cache(_load_topic_video_links_cached)


def load_videos_by_ids(video_ids: list[int]) -> list[dict]:
    safe_ids = [int(video_id) for video_id in video_ids if int(video_id or 0) > 0]
    if not safe_ids:
        return []
    try:
        rows = _rows(get_sb().table("videos").select("*").in_("id", safe_ids).execute())
        normalized = []
        for row in rows:
            if is_archived_status(row.get("status")):
                continue
            profile = load_profile_row(str(row.get("user_id") or ""))
            normalized.append(
                _normalize_video_row(
                    {
                        **row,
                        "author_name": profile.get("display_name") or profile.get("username") or profile.get("email") or "",
                    }
                )
            )
        return normalized
    except Exception:
        return []


def load_topic_video_links(program_ids: list[int] | tuple[int, ...]) -> dict[int, list[dict]]:
    return _load_topic_video_links_cached(tuple(sorted({int(pid) for pid in program_ids if int(pid or 0) > 0})))


def render_topic_video_manager(
    *,
    program_id: int,
    topic: dict,
    subject: str,
    learner_stage: str,
    level_or_band: str,
    prefix: str,
) -> None:
    topic_id = int(topic.get("topic_id") or 0)
    if program_id <= 0 or topic_id <= 0:
        return

    attached = load_topic_video_links([program_id]).get(topic_id, [])
    with st.expander(t("topic_videos_label"), expanded=False):
        if attached:
            for idx, item in enumerate(attached, start=1):
                video = _normalize_video_row(item.get("video") or {})
                title = html.escape(str(video.get("title") or t("video_default_title")))
                watch_url = str(video.get("watch_url") or "")
                st.markdown(
                    f"<div class='cm-resource-meta' style='margin-bottom:.35rem;'><strong>{idx}. {title}</strong></div>",
                    unsafe_allow_html=True,
                )
                action_cols = st.columns([1, 1], gap="small")
                with action_cols[0]:
                    if watch_url:
                        st.link_button(t("watch_video"), watch_url, key=f"{prefix}_watch_{topic_id}_{idx}", use_container_width=True)
                with action_cols[1]:
                    if st.button(t("remove_video"), key=f"{prefix}_remove_{topic_id}_{idx}", use_container_width=True):
                        ok, key = detach_video_from_topic(int(item.get("id") or 0))
                        if ok:
                            st.success(t(key))
                            st.rerun()
                        st.error(t(key))
        else:
            st.caption(t("topic_videos_empty"))

        my_videos = load_my_videos()
        if not my_videos.empty:
            options = {str(row.get("title") or t("video_default_title")) + f" · {row.get('id')}": row for row in my_videos.to_dict("records")}
            selected_label = st.selectbox(
                t("attach_existing_video"),
                [t("select_video_placeholder")] + list(options.keys()),
                key=f"{prefix}_existing_video_{topic_id}",
            )
            if selected_label != t("select_video_placeholder") and st.button(t("attach_video_button"), key=f"{prefix}_attach_existing_btn_{topic_id}", use_container_width=True):
                selected = options[selected_label]
                ok, key = attach_video_to_topic(program_id, topic_id, int(selected.get("id") or 0))
                if ok:
                    st.success(t(key))
                    st.rerun()
                st.error(t(key))

        st.markdown(f"**{t('add_new_video')}**")
        youtube_url = st.text_input(
            t("youtube_link_label"),
            key=f"{prefix}_youtube_url_{topic_id}",
            placeholder=t("youtube_link_placeholder"),
        )
        title = st.text_input(
            t("video_title_optional"),
            key=f"{prefix}_video_title_{topic_id}",
            value=str(topic.get("title") or ""),
        )
        description = st.text_area(
            t("video_description_optional"),
            key=f"{prefix}_video_description_{topic_id}",
            value=str(topic.get("student_summary") or topic.get("lesson_focus") or ""),
            height=80,
        )
        public_toggle = st.checkbox(t("share_video_with_community"), key=f"{prefix}_video_public_{topic_id}")
        if st.button(t("save_and_attach_video"), key=f"{prefix}_save_attach_video_{topic_id}", use_container_width=True):
            ok, video_record_id, key = save_video_resource(
                youtube_url=youtube_url,
                title=title,
                description=description,
                subject=subject,
                learner_stage=learner_stage,
                level_or_band=level_or_band,
                topic=str(topic.get("title") or ""),
                is_public=public_toggle,
            )
            if not ok or not video_record_id:
                st.error(t(key))
                return
            link_ok, link_key = attach_video_to_topic(program_id, topic_id, int(video_record_id))
            if link_ok:
                st.success(t(link_key))
                st.rerun()
            st.error(t(link_key))
