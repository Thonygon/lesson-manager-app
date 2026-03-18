import streamlit as st
import datetime
from core.i18n import t
from core.state import get_current_user_id
from core.timezone import now_local, today_local, get_app_tz
from core.database import get_sb, load_table, load_students

# 07.1B) HOME PAGE HELPERS
# =========================

def neon_button_css(
    glow_rgba: str,
    text_color: str = "#0B1220",
    min_height: int = 58,
    radius: int = 18,
) -> str:
    return f"""
    button {{
        width: 100%;
        min-height: {min_height}px !important;
        border-radius: {radius}px !important;
        border: 1px solid rgba(255,255,255,0.88) !important;
        background: linear-gradient(
            180deg,
            rgba(255,255,255,0.98),
            rgba(241,245,249,0.95)
        ) !important;
        color: {text_color} !important;
        -webkit-text-fill-color: {text_color} !important;
        font-weight: 800 !important;
        letter-spacing: -0.01em !important;
        box-shadow:
            0 0 0 1px rgba(255,255,255,0.45) inset,
            0 0 10px {glow_rgba},
            0 0 22px {glow_rgba},
            0 10px 22px rgba(0,0,0,0.22) !important;
        animation: homeNeonPulse 2.2s ease-in-out infinite !important;
        transition: all 160ms ease !important;
    }}

    button:hover {{
        transform: translateY(-1px) !important;
        box-shadow:
            0 0 0 1px rgba(255,255,255,0.55) inset,
            0 0 14px {glow_rgba},
            0 0 30px {glow_rgba},
            0 12px 26px rgba(0,0,0,0.26) !important;
    }}

    button:focus {{
        outline: none !important;
        color: {text_color} !important;
        -webkit-text-fill-color: {text_color} !important;
        box-shadow:
            0 0 0 2px rgba(255,255,255,0.45) inset,
            0 0 0 3px {glow_rgba},
            0 0 14px {glow_rgba},
            0 0 28px {glow_rgba},
            0 12px 26px rgba(0,0,0,0.26) !important;
    }}
    """


def top_neon_button_css(glow_rgba: str, text_color: str = "#0B1220") -> str:
    return neon_button_css(
        glow_rgba=glow_rgba,
        text_color=text_color,
        min_height=38,
        radius=12,
    )
# =========================
