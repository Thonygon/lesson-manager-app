import streamlit as st
import pandas as pd
from core.i18n import t
from core.database import load_table
import streamlit.components.v1 as components
from styles.theme import _is_dark

# 07.16) KPI BUBBLES (ROBUST: NO AUTO-RESIZE DEPENDENCY)
# =========================
def kpi_stat_cards(values, accent_colors):
    """
    Flat KPI cards with subtle colored top accent.
    Scrollable horizontally so all KPIs stay in one row.
    """
    compact = bool(st.session_state.get("compact_mode", False))
    is_dark = _is_dark()

    gap = 10 if compact else 12
    card_width = 110 if compact else 120
    card_bg = "#0f172a" if is_dark else "#f5f7fb"
    card_border = card_bg if is_dark else "#f5f7fb"
    value_color = "#f1f5f9" if is_dark else "#0f172a"
    label_color = "#cbd5e1" if is_dark else "#475569"
    scrollbar_thumb = "rgba(148,163,184,0.28)" if is_dark else "rgba(0,0,0,0.15)"

    style = f"""
    <style>

      .kpi-stat-wrap {{
        display: flex;
        flex-direction: row;
        gap: {gap}px;
        overflow-x: auto;
        overflow-y: hidden;
        padding-bottom: 6px;
        margin: 10px 0 12px 0;
        scroll-snap-type: x proximity;
        -webkit-overflow-scrolling: touch;
        font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
      }}

      /* hide scrollbar but keep scroll */
      .kpi-stat-wrap::-webkit-scrollbar {{
        height: 6px;
      }}

      .kpi-stat-wrap::-webkit-scrollbar-thumb {{
        background: {scrollbar_thumb};
        border-radius: 6px;
      }}

      .kpi-stat-card {{
        flex: 0 0 {card_width}px;
        position: relative;
        background: {card_bg};
        border: 1px solid {card_border};
        border-radius: 14px;
        box-shadow: 0 0 0 0;
        padding: 8px 8px 10px 8px;
        box-sizing: border-box;
        overflow: hidden;
        cursor: default;
        scroll-snap-align: start;
      }}

      .kpi-stat-card::before {{
        content: "";
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 4px;
        background: var(--accent);
      }}

      .kpi-stat-value {{
        font-size: 1rem;
        line-height: 1.0;
        font-weight: 800;
        color: {value_color};
        margin-top: 6px;
        margin-bottom: 6px;
        text-align: center;
      }}

      .kpi-stat-label {{
        font-size: 0.62rem;
        line-height: 1.15;
        font-weight: 600;
        color: {label_color};
        text-transform: uppercase;
        letter-spacing: 0.03em;
        text-align: center;
        word-break: keep-all;
      }}

      /* Mobile adjustments */
      @media (max-width: 700px) {{

        .kpi-stat-card {{
          flex: 0 0 100px;
        }}

        .kpi-stat-value {{
          font-size: 0.9rem;
        }}

        .kpi-stat-label {{
          font-size: 0.58rem;
        }}

      }}

    </style>
    """

    cards_html = '<div class="kpi-stat-wrap">'

    for (label, val), accent in zip(values, accent_colors):
        cards_html += f"""
        <div class="kpi-stat-card" style="--accent:{accent};">
            <div class="kpi-stat-value">{val}</div>
            <div class="kpi-stat-label">{label}</div>
        </div>
        """

    cards_html += "</div>"

    components.html(style + cards_html, height=120 if compact else 110, scrolling=False)

# =========================
