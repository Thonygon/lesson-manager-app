from __future__ import annotations

import html
import json
from typing import Any

import streamlit as st

from core.i18n import t


def inject_resource_gallery_styles() -> None:
    st.markdown(
        """
        <style>
        .cm-resource-card{
          --resource-accent:#8b5cf6;
          position:relative;
          overflow:hidden;
          border-radius:22px;
          border:1px solid color-mix(in srgb, var(--border) 82%, var(--resource-accent) 18%);
          border-left:4px solid var(--resource-accent);
          background:linear-gradient(180deg, color-mix(in srgb, var(--panel) 96%, white 4%), var(--panel-soft));
          box-shadow:0 18px 42px rgba(15,23,42,.08);
          transition:transform .18s ease, border-color .18s ease, box-shadow .18s ease;
          margin-bottom:.6rem;
        }
        .cm-resource-card:hover{
          transform:translateY(-3px);
          border-color:color-mix(in srgb, var(--resource-accent) 48%, var(--border));
          box-shadow:0 24px 60px rgba(15,23,42,.14), 0 0 0 1px color-mix(in srgb, var(--resource-accent) 16%, transparent);
        }
        .cm-resource-worksheet{--resource-accent:#8b5cf6;}
        .cm-resource-exam{--resource-accent:#10b981;}
        .cm-resource-plan{--resource-accent:#f59e0b;}
        .cm-resource-program{--resource-accent:#3b82f6;}
        .cm-resource-hero{
          position:relative;
          aspect-ratio:16/9;
          overflow:hidden;
          border-radius:18px 18px 0 0;
          background:
            radial-gradient(circle at 20% 20%, color-mix(in srgb, var(--resource-accent) 34%, transparent), transparent 32%),
            radial-gradient(circle at 82% 12%, rgba(56,189,248,.24), transparent 30%),
            linear-gradient(135deg, color-mix(in srgb, var(--panel-soft) 80%, var(--resource-accent) 20%), color-mix(in srgb, var(--panel) 88%, black 12%));
        }
        .cm-resource-hero img{
          width:100%;
          height:100%;
          display:block;
          object-fit:cover;
        }
        .cm-resource-hero-placeholder{
          height:100%;
          display:flex;
          flex-direction:column;
          justify-content:flex-end;
          gap:6px;
          padding:18px;
          color:var(--text);
        }
        .cm-resource-hero-placeholder span:first-child{
          width:max-content;
          max-width:100%;
          border-radius:999px;
          padding:5px 10px;
          font-size:.72rem;
          font-weight:900;
          color:var(--text);
          background:color-mix(in srgb, var(--panel) 72%, transparent);
          border:1px solid color-mix(in srgb, var(--border) 70%, var(--resource-accent) 30%);
        }
        .cm-resource-hero-placeholder span:last-child{
          max-width:100%;
          font-size:1.1rem;
          font-weight:950;
          line-height:1.15;
          text-shadow:0 1px 18px rgba(15,23,42,.18);
          overflow:hidden;
          text-overflow:ellipsis;
          display:-webkit-box;
          -webkit-line-clamp:2;
          -webkit-box-orient:vertical;
        }
        .cm-resource-body{padding:14px 16px 16px;}
        .cm-resource-card__title{
          color:var(--text);
          font-weight:950;
          font-size:1.02rem;
          line-height:1.25;
          min-height:2.5rem;
          overflow:hidden;
          text-overflow:ellipsis;
          display:-webkit-box;
          -webkit-line-clamp:2;
          -webkit-box-orient:vertical;
        }
        .cm-resource-chip-row{display:flex;gap:7px;flex-wrap:wrap;margin-top:10px;}
        .cm-resource-chip{
          display:inline-flex;
          align-items:center;
          gap:4px;
          max-width:100%;
          border-radius:999px;
          padding:5px 9px;
          font-size:.72rem;
          font-weight:850;
          color:var(--text);
          background:color-mix(in srgb, var(--resource-accent) 13%, var(--panel));
          border:1px solid color-mix(in srgb, var(--resource-accent) 28%, var(--border));
          white-space:nowrap;
          overflow:hidden;
          text-overflow:ellipsis;
        }
        .cm-resource-preview{
          margin-top:10px;
          color:var(--muted);
          font-size:.86rem;
          line-height:1.45;
          min-height:1.25rem;
          overflow:hidden;
          text-overflow:ellipsis;
          white-space:nowrap;
        }
        .cm-resource-meta-row{
          display:flex;
          gap:10px;
          flex-wrap:wrap;
          margin-top:12px;
        }
        .cm-resource-meta{
          min-width:0;
          color:var(--muted);
          font-size:.78rem;
          font-weight:750;
          overflow:hidden;
          text-overflow:ellipsis;
          white-space:nowrap;
        }
        @media (max-width: 900px){
          .cm-resource-body{padding:13px 14px 15px;}
          .cm-resource-card__title{font-size:.98rem;}
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _parse_jsonish(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return {}
        try:
            return json.loads(stripped)
        except Exception:
            return value
    return value


def extract_gallery_image_url(payload: Any) -> str:
    payload = _parse_jsonish(payload)
    if isinstance(payload, dict):
        for key in (
            "image_data_url",
            "data_url",
            "data_uri",
            "dataUri",
            "image_url",
            "imageUrl",
            "thumbnail_url",
            "thumbnailUrl",
            "cover_image_url",
            "coverImageUrl",
            "hero_image_url",
            "heroImageUrl",
            "src",
            "url",
            "uri",
        ):
            raw_value = payload.get(key)
            if isinstance(raw_value, dict):
                found = extract_gallery_image_url(raw_value)
                if found:
                    return found
                continue
            value = str(raw_value or "").strip()
            if value.startswith(("data:image/", "http://", "https://")):
                return value
        for key in ("b64_json", "base64", "image_base64"):
            value = str(payload.get(key) or "").strip()
            if value:
                return "data:image/png;base64," + value
        for key in (
            "visual_support",
            "cover_image",
            "hero_image",
            "image",
            "thumbnail",
            "program_data",
            "program_json",
            "plan_json",
            "lesson_plan_json",
            "worksheet_json",
            "exam_data",
            "content_snapshot",
        ):
            found = extract_gallery_image_url(payload.get(key))
            if found:
                return found
        for key in ("visual_supports", "sections", "activities", "units", "topics", "items", "images"):
            found = extract_gallery_image_url(payload.get(key))
            if found:
                return found
    if isinstance(payload, list):
        for item in payload:
            found = extract_gallery_image_url(item)
            if found:
                return found
    return ""


def extract_gallery_language_label(payload: Any) -> str:
    payload = _parse_jsonish(payload)
    if isinstance(payload, dict):
        for key in (
            "student_material_language",
            "plan_language",
            "program_language",
            "language",
            "lang",
        ):
            value = str(payload.get(key) or "").strip()
            if value:
                return value.upper()
        for key in (
            "cover_image",
            "hero_image",
            "image",
            "program_data",
            "program_json",
            "plan_json",
            "lesson_plan_json",
            "worksheet_json",
            "exam_data",
            "content_snapshot",
        ):
            found = extract_gallery_language_label(payload.get(key))
            if found:
                return found
    if isinstance(payload, list):
        for item in payload:
            found = extract_gallery_language_label(item)
            if found:
                return found
    return ""


def render_gallery_card_html(
    *,
    kind: str,
    title: str,
    chips_html: str,
    description: str,
    meta_html: str,
    image_url: str = "",
    placeholder_label: str = "",
) -> str:
    safe_title = html.escape(str(title or ""))
    safe_description = html.escape(str(description or t("no_description_available")))
    safe_placeholder = html.escape(str(placeholder_label or kind.replace("_", " ").title()))
    if image_url:
        hero = f'<div class="cm-resource-hero"><img src="{html.escape(image_url, quote=True)}" alt="{safe_title}" loading="lazy"></div>'
    else:
        hero = (
            '<div class="cm-resource-hero">'
            '<div class="cm-resource-hero-placeholder">'
            f"<span>{safe_placeholder}</span><span>{safe_title}</span>"
            "</div></div>"
        )
    return (
        f'<div class="cm-resource-card cm-resource-{html.escape(kind)}">'
        f"{hero}"
        '<div class="cm-resource-body">'
        f'<div class="cm-resource-card__title">{safe_title}</div>'
        f'<div class="cm-resource-chip-row">{chips_html}</div>'
        f'<div class="cm-resource-preview">{safe_description}</div>'
        f'<div class="cm-resource-meta-row">{meta_html}</div>'
        "</div></div>"
    )
