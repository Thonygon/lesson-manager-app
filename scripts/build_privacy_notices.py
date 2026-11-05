"""Render versioned privacy notices for the public Master Classio Site.

The JSON source is reviewed in this repository. Publish the generated `privacy/`
directory to the separate Sites source repository with the same version.
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "legal/privacy-notices.v1.json"
AUDIENCES = ("website", "app", "students")
LANGUAGES = ("tr", "en", "es")


def escape(value: str) -> str:
    return html.escape(value, quote=True)


def render_section(title: str, paragraphs: list[str], items: list[str] | None = None) -> str:
    body = "".join(f"<p>{escape(text)}</p>" for text in paragraphs)
    if items:
        body += "<ul>" + "".join(f"<li>{escape(item)}</li>" for item in items) + "</ul>"
    return f"<section class=\"notice-section\"><h2>{escape(title)}</h2>{body}</section>"


def render_page(data: dict, language: str, audience: str) -> str:
    locale = data["locales"][language]
    topic = locale["audiences"][audience]
    site = "https://masterclassio.com"
    title = f"{topic['title']} · Master Classio"
    current = ' aria-current="page"'
    language_links = "".join(
        f'<a lang="{code}" hreflang="{code}" href="/privacy/{code}/{audience}/"'
        f'{current if code == language else ""}>{code.upper()}</a>'
        for code in LANGUAGES
    )
    audience_links = "".join(
        f'<a href="/privacy/{language}/{key}/"'
        f'{current if key == audience else ""}>{escape(locale["audiences"][key]["nav"])}</a>'
        for key in AUDIENCES
    )
    sections = render_section(topic["data_title"], topic["data"], topic.get("data_items"))
    sections += render_section(topic["purpose_title"], topic["purposes"], topic.get("purpose_items"))
    sections += "".join(render_section(item["title"], item["paragraphs"], item.get("items")) for item in locale["common"])
    controller = data["controller"]
    contact = (
        f'<p><strong>{escape(controller["name"])}</strong> · {escape(controller["trade_name"])} · '
        f'{escape(controller["tax_label"])} {escape(controller["tax_number"])}</p>'
        f'<p>{escape(controller["address"])}</p>'
        f'<p><a href="mailto:{escape(controller["email"])}">{escape(controller["email"])}</a> · '
        f'<a href="tel:{escape(controller["phone_e164"])}">{escape(controller["phone_display"])}</a></p>'
    )
    canonical = f"{site}/privacy/{language}/{audience}/"
    return f'''<!doctype html>
<html lang="{language}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{escape(topic['description'])}"><link rel="canonical" href="{canonical}">
<meta name="robots" content="index,follow"><link rel="stylesheet" href="/privacy/privacy.css">
<title>{escape(title)}</title></head><body>
<a class="skip" href="#notice">{escape(locale['skip'])}</a>
<header><div class="wrap header"><a class="brand" href="/">Master Classio</a><nav aria-label="{escape(locale['languages'])}" class="languages">{language_links}</nav></div></header>
<main class="wrap" id="notice"><p class="eyebrow">{escape(locale['eyebrow'])} · {escape(data['version'])} · {escape(data['effective_date'])}</p>
<h1>{escape(topic['title'])}</h1><p class="lead">{escape(topic['lead'])}</p>
<nav class="audiences" aria-label="{escape(locale['audience_nav'])}">{audience_links}</nav>
<div class="notice-layout"><article>{sections}</article><aside><h2>{escape(locale['controller_title'])}</h2>{contact}<p>{escape(locale['contact_help'])}</p></aside></div>
</main><footer><div class="wrap"><a href="/">Master Classio</a><a href="/cookies/{language}/">{escape({'en': 'Cookies and storage', 'es': 'Cookies y almacenamiento', 'tr': 'Çerezler ve depolama'}[language])}</a><span>{escape(locale['footer'])}</span></div></footer>
</body></html>'''


def build(output: Path) -> None:
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    assert data["version"] and data["effective_date"]
    assert set(data["locales"]) == set(LANGUAGES)
    for language in LANGUAGES:
        locale = data["locales"][language]
        assert set(locale["audiences"]) == set(AUDIENCES)
        assert len(locale["common"]) >= 4
        for audience in AUDIENCES:
            text = render_page(data, language, audience)
            if "TODO" in text or "[insert" in text.lower():
                raise ValueError("Unfinished privacy notice")
            destination = output / language / audience / "index.html"
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(text, encoding="utf-8")
    (output / "privacy.css").write_text((ROOT / "legal/privacy.css").read_text(encoding="utf-8"), encoding="utf-8")
    index = output / "index.html"
    index.write_text((ROOT / "legal/privacy-index.html").read_text(encoding="utf-8"), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    build(parser.parse_args().output)
