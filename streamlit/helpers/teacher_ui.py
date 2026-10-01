import streamlit as st
import streamlit.components.v1 as components
from core.i18n import t


def render_quick_stat_card(label: str, value: str, icon: str = None, color: str = "#3B82F6"):
    """Render a compact stat card with optional icon."""
    icon_html = f'<span style="font-size:1.2rem;margin-right:0.5rem;">{icon}</span>' if icon else ''

    st.markdown(
        f"""
        <div style="
            background: linear-gradient(135deg, {color}08, {color}15);
            border: 1px solid {color}30;
            border-radius: 12px;
            padding: 0.85rem 1rem;
            text-align: center;
            transition: all 200ms ease;
        ">
            <div style="font-size:0.8rem;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.3rem;">
                {icon_html}{label}
            </div>
            <div style="font-size:1.4rem;font-weight:800;color:#0f172a;">
                {value}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_action_card(title: str, description: str, button_text: str, on_click_key: str, icon: str = None):
    """Render an action card for quick teacher workflows."""
    icon_html = f'<div style="font-size:2rem;margin-bottom:0.5rem;">{icon}</div>' if icon else ''

    with st.container():
        st.markdown(
            f"""
            <div style="
                background: linear-gradient(180deg, #ffffff, #f8fafc);
                border: 1px solid rgba(17,24,39,0.1);
                border-radius: 14px;
                padding: 1.2rem;
                text-align: center;
                box-shadow: 0 2px 8px rgba(15,23,42,0.04);
                transition: all 250ms ease;
                margin-bottom: 1rem;
            ">
                {icon_html}
                <div style="font-size:1.1rem;font-weight:700;color:#0f172a;margin-bottom:0.4rem;">
                    {title}
                </div>
                <div style="font-size:0.9rem;color:#64748b;margin-bottom:0.8rem;line-height:1.5;">
                    {description}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        st.button(button_text, key=on_click_key, use_container_width=True)


def render_contextual_help(help_text: str, placement: str = "inline"):
    """Render contextual help for teachers."""
    if placement == "inline":
        st.markdown(
            f"""
            <div style="
                background: linear-gradient(90deg, #dbeafe, #eff6ff);
                border-left: 3px solid #3B82F6;
                border-radius: 8px;
                padding: 0.75rem 1rem;
                margin: 0.75rem 0;
                font-size: 0.9rem;
                color: #1e40af;
                line-height: 1.6;
            ">
                <strong style="margin-right:0.3rem;">💡</strong>{help_text}
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        st.info(help_text)


def render_progress_indicator(current: int, total: int, label: str = ""):
    """Render a visual progress indicator."""
    percentage = int((current / total * 100)) if total > 0 else 0

    st.markdown(
        f"""
        <div style="margin:0.75rem 0;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.4rem;">
                <span style="font-size:0.85rem;font-weight:600;color:#64748b;">{label}</span>
                <span style="font-size:0.85rem;font-weight:700;color:#0f172a;">{current}/{total}</span>
            </div>
            <div style="
                width:100%;
                height:8px;
                background:#e2e8f0;
                border-radius:999px;
                overflow:hidden;
            ">
                <div style="
                    width:{percentage}%;
                    height:100%;
                    background:linear-gradient(90deg, #3B82F6, #60A5FA);
                    border-radius:999px;
                    transition: width 400ms ease;
                "></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_status_badge(status: str, color_map: dict = None):
    """Render a status badge with color coding."""
    default_colors = {
        "active": "#10B981",
        "completed": "#8B5CF6",
        "pending": "#F59E0B",
        "cancelled": "#EF4444",
        "scheduled": "#3B82F6",
    }

    colors = color_map or default_colors
    color = colors.get(status.lower(), "#64748b")

    st.markdown(
        f"""
        <span style="
            display:inline-block;
            background:{color}15;
            color:{color};
            border:1px solid {color}40;
            padding:0.25rem 0.75rem;
            border-radius:999px;
            font-size:0.8rem;
            font-weight:600;
            text-transform:uppercase;
            letter-spacing:0.05em;
        ">
            {status}
        </span>
        """,
        unsafe_allow_html=True
    )


def render_section_header(title: str, subtitle: str = None, icon: str = None):
    """Render a section header with optional subtitle and icon."""
    icon_html = f'<span style="margin-right:0.5rem;">{icon}</span>' if icon else ''
    subtitle_html = f'<div style="font-size:0.9rem;color:#64748b;margin-top:0.3rem;font-weight:400;">{subtitle}</div>' if subtitle else ''

    st.markdown(
        f"""
        <div style="margin:1.5rem 0 1rem 0;">
            <h2 style="
                font-size:1.5rem;
                font-weight:800;
                color:#0f172a;
                letter-spacing:-0.02em;
                margin:0;
            ">
                {icon_html}{title}
            </h2>
            {subtitle_html}
        </div>
        """,
        unsafe_allow_html=True
    )


def render_empty_state(message: str, action_text: str = None, action_key: str = None, icon: str = "📚"):
    """Render an empty state with optional action."""
    action_button = ""

    st.markdown(
        f"""
        <div style="
            text-align:center;
            padding:3rem 1.5rem;
            background:linear-gradient(180deg, #f8fafc, #ffffff);
            border:2px dashed rgba(17,24,39,0.1);
            border-radius:16px;
            margin:1.5rem 0;
        ">
            <div style="font-size:3rem;margin-bottom:1rem;opacity:0.6;">{icon}</div>
            <div style="font-size:1.1rem;color:#64748b;margin-bottom:1rem;line-height:1.6;">
                {message}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    if action_text and action_key:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.button(action_text, key=action_key, use_container_width=True)


def render_loading_placeholder(text: str = None):
    """Render an animated loading placeholder."""
    display_text = text or t("loading")

    st.markdown(
        f"""
        <div style="
            display:flex;
            align-items:center;
            justify-content:center;
            padding:2rem;
            gap:0.75rem;
        ">
            <div style="
                width:8px;
                height:8px;
                background:#3B82F6;
                border-radius:50%;
                animation: pulse 1.5s ease-in-out infinite;
            "></div>
            <div style="
                width:8px;
                height:8px;
                background:#3B82F6;
                border-radius:50%;
                animation: pulse 1.5s ease-in-out 0.2s infinite;
            "></div>
            <div style="
                width:8px;
                height:8px;
                background:#3B82F6;
                border-radius:50%;
                animation: pulse 1.5s ease-in-out 0.4s infinite;
            "></div>
            <span style="margin-left:0.5rem;color:#64748b;font-weight:600;">{display_text}</span>
        </div>
        <style>
            @keyframes pulse {{
                0%, 100% {{ opacity: 0.3; transform: scale(0.8); }}
                50% {{ opacity: 1; transform: scale(1.2); }}
            }}
        </style>
        """,
        unsafe_allow_html=True
    )
