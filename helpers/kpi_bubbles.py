import streamlit as st
import pandas as pd
from core.i18n import t
from core.database import load_table
import streamlit.components.v1 as components
from styles.theme import get_theme_mode

# 07.16) KPI BUBBLES (ROBUST: NO AUTO-RESIZE DEPENDENCY)
# =========================
def kpi_stat_cards(values, accent_colors):
    """
    Flat KPI cards with subtle colored top accent.
    Scrollable horizontally so all KPIs stay in one row.
    """
    compact = bool(st.session_state.get("compact_mode", False))
    theme_mode = get_theme_mode()

    gap = 10 if compact else 12
    card_width = 110 if compact else 120

    style = f"""
    <style>
      html, body {{
        margin: 0;
        padding: 0;
        background: transparent;
        color-scheme: light dark;
      }}

      :root {{
        --kpi-card-bg: transparent;
        --kpi-card-border: transparent;
        --kpi-value: #0f172a;
        --kpi-label: #475569;
        --kpi-scrollbar-thumb: rgba(0,0,0,0.15);
        --kpi-card-shadow: none;
      }}

      @media (prefers-color-scheme: dark) {{
        :root {{
          --kpi-card-bg: transparent;
          --kpi-card-border: transparent;
          --kpi-value: #f1f5f9;
          --kpi-label: #cbd5e1;
          --kpi-scrollbar-thumb: rgba(148,163,184,0.28);
          --kpi-card-shadow: none;
        }}
      }}

      .theme-dark {{
        --kpi-card-bg: transparent;
        --kpi-card-border: transparent;
        --kpi-value: #f1f5f9;
        --kpi-label: #cbd5e1;
        --kpi-scrollbar-thumb: rgba(148,163,184,0.28);
        --kpi-card-shadow: none;
      }}

      .theme-light {{
        --kpi-card-bg: transparent;
        --kpi-card-border: transparent;
        --kpi-value: #0f172a;
        --kpi-label: #475569;
        --kpi-scrollbar-thumb: rgba(0,0,0,0.15);
        --kpi-card-shadow: none;
      }}

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
        background: var(--kpi-scrollbar-thumb);
        border-radius: 6px;
      }}

      .kpi-stat-card {{
        flex: 0 0 {card_width}px;
        position: relative;
        background: var(--kpi-card-bg);
        border: 1px solid var(--kpi-card-border);
        border-radius: 18px;
        box-shadow: var(--kpi-card-shadow);
        padding: 10px 10px 12px 10px;
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
        font-size: 1.02rem;
        line-height: 1.0;
        font-weight: 900;
        color: var(--kpi-value);
        margin-top: 8px;
        margin-bottom: 8px;
        text-align: center;
      }}

      .kpi-stat-label {{
        font-size: 0.62rem;
        line-height: 1.15;
        font-weight: 700;
        color: var(--kpi-label);
        text-transform: uppercase;
        letter-spacing: 0.05em;
        text-align: center;
        word-break: keep-all;
      }}

      .theme-dark .kpi-stat-value {{
        color: #f1f5f9 !important;
      }}

      .theme-dark .kpi-stat-label {{
        color: #cbd5e1 !important;
      }}

      .theme-light .kpi-stat-value {{
        color: #0f172a !important;
      }}

      .theme-light .kpi-stat-label {{
        color: #475569 !important;
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
    <script>
      window.__THEME_MODE__ = "{theme_mode}";
    </script>
    <script>
      function applyTheme() {{
        const mode = window.__THEME_MODE__ || "auto";
        const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
        const dark = mode === "dark" || (mode === "auto" && prefersDark);
        document.documentElement.classList.toggle("theme-dark", dark);
        document.documentElement.classList.toggle("theme-light", !dark);
        document.body.classList.toggle("theme-dark", dark);
        document.body.classList.toggle("theme-light", !dark);
      }}
      applyTheme();
      const media = window.matchMedia("(prefers-color-scheme: dark)");
      if (media && media.addEventListener) {{
        media.addEventListener("change", applyTheme);
      }}
    </script>
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
