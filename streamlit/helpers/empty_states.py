import html
from collections.abc import Iterable

import streamlit as st

from core.i18n import t


def render_empty_state(
    *,
    title_key: str,
    body_key: str,
    steps: Iterable[str] | None = None,
    eyebrow_key: str = "empty_state_eyebrow",
    icon: str = "",
) -> None:
    title = html.escape(t(title_key))
    body = html.escape(t(body_key))
    eyebrow = html.escape(t(eyebrow_key))
    icon_html = f"<div class='classio-empty-icon'>{html.escape(icon)}</div>" if icon else ""
    step_items = ""
    if steps:
        safe_steps = [html.escape(t(step_key)) for step_key in steps]
        step_items = "".join(
            f"<li><span>{idx}</span><p>{step}</p></li>"
            for idx, step in enumerate(safe_steps, start=1)
        )

    steps_html = f"<ol class='classio-empty-steps'>{step_items}</ol>" if step_items else ""

    st.markdown(
        f"""
        <style>
        .classio-empty-state {{
            margin: 12px 0 16px;
            padding: 18px;
            border-radius: 16px;
            border: 1px solid var(--border-strong, rgba(17,24,39,.10));
            background:
                linear-gradient(135deg, rgba(59,130,246,.09), rgba(16,185,129,.06)),
                linear-gradient(180deg, var(--panel, rgba(255,255,255,.96)), var(--panel-2, rgba(248,250,252,.88)));
            box-shadow: var(--shadow-md, 0 14px 34px rgba(15,23,42,.10));
        }}
        .classio-empty-top {{
            display: flex;
            align-items: flex-start;
            gap: 12px;
        }}
        .classio-empty-icon {{
            width: 42px;
            height: 42px;
            border-radius: 14px;
            display: flex;
            align-items: center;
            justify-content: center;
            flex: 0 0 auto;
            background: rgba(59,130,246,.12);
            border: 1px solid rgba(59,130,246,.18);
            font-size: 1.25rem;
        }}
        .classio-empty-eyebrow {{
            font-size: .75rem;
            font-weight: 900;
            color: var(--primary-strong, #2563eb);
            text-transform: uppercase;
            letter-spacing: 0;
        }}
        .classio-empty-title {{
            margin-top: 3px;
            font-size: 1.15rem;
            line-height: 1.2;
            font-weight: 950;
            color: var(--text, #0f172a);
        }}
        .classio-empty-body {{
            margin-top: 7px;
            max-width: 840px;
            color: var(--muted, #475569);
            font-size: .92rem;
            line-height: 1.5;
        }}
        .classio-empty-steps {{
            margin: 14px 0 0;
            padding: 0;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 10px;
            list-style: none;
        }}
        .classio-empty-steps li {{
            display: flex;
            gap: 9px;
            align-items: flex-start;
            padding: 10px 11px;
            border-radius: 12px;
            background: var(--panel-soft, rgba(255,255,255,.68));
            border: 1px solid var(--border, rgba(148,163,184,.20));
        }}
        .classio-empty-steps span {{
            width: 22px;
            height: 22px;
            border-radius: 50%;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            flex: 0 0 auto;
            background: var(--primary, #3b82f6);
            color: #fff;
            font-size: .74rem;
            font-weight: 900;
        }}
        .classio-empty-steps p {{
            margin: 0;
            color: var(--text, #0f172a);
            font-size: .86rem;
            line-height: 1.35;
            font-weight: 650;
        }}
        </style>
        <div class="classio-empty-state">
          <div class="classio-empty-top">
            {icon_html}
            <div>
              <div class="classio-empty-eyebrow">{eyebrow}</div>
              <div class="classio-empty-title">{title}</div>
              <div class="classio-empty-body">{body}</div>
            </div>
          </div>
          {steps_html}
        </div>
        """,
        unsafe_allow_html=True,
    )
