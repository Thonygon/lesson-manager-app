from __future__ import annotations

import html as _html
import math

import pandas as pd
import streamlit as st


def render_section_callout(title: str, subtitle: str) -> None:
    st.markdown(
        f"<div class='admin-section-card'><div class='admin-card-title'>{_html.escape(title)}</div><div class='admin-card-subtitle'>{_html.escape(subtitle)}</div></div>",
        unsafe_allow_html=True,
    )


def slice_dataframe_page(
    df: pd.DataFrame | None,
    state_key: str,
    *,
    page_size: int,
) -> tuple[pd.DataFrame | None, int, int, int, int, int]:
    if df is None:
        return df, 1, 1, 0, 0, 0
    total_items = len(df)
    total_pages = max(1, math.ceil(total_items / page_size)) if total_items else 1
    current_page = int(st.session_state.get(state_key, 1) or 1)
    current_page = max(1, min(current_page, total_pages))
    st.session_state[state_key] = current_page
    start_idx = (current_page - 1) * page_size
    end_idx = min(start_idx + page_size, total_items)
    page_df = df.iloc[start_idx:end_idx].copy() if total_items else df
    return page_df, current_page, total_pages, start_idx, end_idx, total_items


def render_pagination_controls(
    df: pd.DataFrame,
    state_key: str,
    *,
    page_size: int,
    previous_label: str | None = "←",
    next_label: str | None = "→",
) -> None:
    _, current_page, total_pages, start_idx, end_idx, total_items = slice_dataframe_page(
        df,
        state_key,
        page_size=page_size,
    )
    if total_items <= page_size:
        return

    prev_col, info_col, next_col = st.columns([1, 3, 1])
    with prev_col:
        if st.button(
            previous_label or "←",
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
            next_label or "→",
            key=f"{state_key}_next",
            use_container_width=True,
            disabled=current_page >= total_pages,
        ):
            st.session_state[state_key] = min(total_pages, current_page + 1)
            st.rerun()
