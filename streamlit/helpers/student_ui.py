from __future__ import annotations

import math
from typing import Any

import streamlit as st


DEFAULT_STUDENT_PAGE_SIZE = 6


def slice_student_page(rows: list[Any], state_key: str, *, page_size: int = DEFAULT_STUDENT_PAGE_SIZE):
    total_items = len(rows or [])
    total_pages = max(1, math.ceil(total_items / page_size)) if total_items else 1
    current_page = int(st.session_state.get(state_key, 1) or 1)
    current_page = max(1, min(current_page, total_pages))
    st.session_state[state_key] = current_page
    start_idx = (current_page - 1) * page_size
    end_idx = min(start_idx + page_size, total_items)
    return list((rows or [])[start_idx:end_idx]), current_page, total_pages, start_idx, end_idx, total_items


def render_student_pagination(rows: list[Any], state_key: str, *, page_size: int = DEFAULT_STUDENT_PAGE_SIZE) -> None:
    _, current_page, total_pages, start_idx, end_idx, total_items = slice_student_page(
        rows,
        state_key,
        page_size=page_size,
    )
    if total_items <= page_size:
        return
    prev_col, info_col, next_col = st.columns([1, 3, 1])
    with prev_col:
        if st.button(
            "←",
            key=f"{state_key}_prev",
            use_container_width=True,
            disabled=current_page <= 1,
        ):
            st.session_state[state_key] = max(1, current_page - 1)
            st.rerun()
    with info_col:
        st.caption(f"{start_idx + 1}-{end_idx} / {total_items} · {current_page}/{total_pages}")
    with next_col:
        if st.button(
            "→",
            key=f"{state_key}_next",
            use_container_width=True,
            disabled=current_page >= total_pages,
        ):
            st.session_state[state_key] = min(total_pages, current_page + 1)
            st.rerun()
