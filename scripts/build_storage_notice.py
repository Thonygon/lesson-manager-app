"""Build the public, versioned cookie and device-storage inventory."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "legal/storage-notice.v1.json"
PURPOSE_INDEX = (0, 3, 1, 2, 3, 4, 5, 6, 6, 7)
LOCATIONS = {
    "en": ("HTTP cookie on masterclassio.com", "Browser local storage on masterclassio.com", "Browser local storage or native app storage", "Browser session storage on app.masterclassio.com", "Browser local storage or native app storage", "Browser local storage or native app storage", "Browser local storage or native app storage", "Browser local storage on masterclassio.com", "Browser local storage or native app storage", "Browser session storage on app.masterclassio.com"),
    "es": ("Cookie HTTP en masterclassio.com", "Almacenamiento local del navegador en masterclassio.com", "Almacenamiento local del navegador o de la app nativa", "Almacenamiento de sesión del navegador en app.masterclassio.com", "Almacenamiento local del navegador o de la app nativa", "Almacenamiento local del navegador o de la app nativa", "Almacenamiento local del navegador o de la app nativa", "Almacenamiento local del navegador en masterclassio.com", "Almacenamiento local del navegador o de la app nativa", "Almacenamiento de sesión del navegador en app.masterclassio.com"),
    "tr": ("masterclassio.com üzerinde HTTP çerezi", "masterclassio.com tarayıcı yerel depolaması", "Tarayıcı yerel depolaması veya yerel uygulama depolaması", "app.masterclassio.com tarayıcı oturum depolaması", "Tarayıcı yerel depolaması veya yerel uygulama depolaması", "Tarayıcı yerel depolaması veya yerel uygulama depolaması", "Tarayıcı yerel depolaması veya yerel uygulama depolaması", "masterclassio.com tarayıcı yerel depolaması", "Tarayıcı yerel depolaması veya yerel uygulama depolaması", "app.masterclassio.com tarayıcı oturum depolaması"),
}
HEADERS = {"en": ("Provider", "Location"), "es": ("Proveedor", "Ubicación"), "tr": ("Sağlayıcı", "Konum")}


def e(value: str) -> str:
    return html.escape(value, quote=True)


def render(data: dict, language: str) -> str:
    locale = data["locales"][language]
    rows = "".join(
        f"<tr><th scope='row'>{e(entry['name'])}</th><td>{e(entry['provider'])}</td>"
        f"<td>{e(LOCATIONS[language][index])}</td><td>{e(locale['purposes'][PURPOSE_INDEX[index]])}</td></tr>"
        for index, entry in enumerate(data["entries"])
    )
    languages = " ".join(f'<a lang="{code}" hreflang="{code}" href="/cookies/{code}/"'
                         + (' aria-current="page"' if language == code else '')
                         + f'>{code.upper()}</a>' for code in ("tr", "en", "es"))
    return f'''<!doctype html><html lang="{language}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="index,follow">
<meta name="description" content="{e(locale['summary'])}"><link rel="canonical" href="https://masterclassio.com/cookies/{language}/">
<link rel="stylesheet" href="/privacy/privacy.css"><title>{e(locale['title'])} · Master Classio</title></head><body>
<header><div class="wrap header"><a class="brand" href="/">Master Classio</a><nav class="languages" aria-label="Languages">{languages}</nav></div></header>
<main class="wrap" id="notice"><p class="eyebrow">{e(data['version'])} · {e(data['effective_date'])}</p>
<h1>{e(locale['title'])}</h1><p class="lead">{e(locale['summary'])}</p>
<section class="notice-section"><p>{e(locale['details'])}</p><p>{e(locale['limits'])}</p></section>
<div class="storage-table-wrap"><table><thead><tr><th scope="col">{e(locale['storage'])}</th><th scope="col">{e(HEADERS[language][0])}</th><th scope="col">{e(HEADERS[language][1])}</th><th scope="col">{e(locale['category'])}</th></tr></thead><tbody>{rows}</tbody></table></div>
<p><a href="/privacy/{language}/website/">{e(locale['privacy'])}</a> · <a href="mailto:info@masterclassio.com">{e(locale['contact'])} info@masterclassio.com</a></p>
</main><footer><div class="wrap"><a href="/">{e(locale['back'])}</a></div></footer></body></html>'''


def build(output: Path) -> None:
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    assert len(data["entries"]) == len(PURPOSE_INDEX)
    for language in ("tr", "en", "es"):
        assert len(data["locales"][language]["purposes"]) == 8
        assert len(LOCATIONS[language]) == len(data["entries"])
        destination = output / language / "index.html"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(render(data, language), encoding="utf-8")
    (output / "index.html").write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Cookies · Master Classio</title>'
        '<link rel="canonical" href="https://masterclassio.com/cookies/"><link rel="stylesheet" href="/privacy/privacy.css">'
        '<main class="wrap"><h1>Cookies and device storage</h1><nav class="audiences"><a href="/cookies/tr/">Türkçe</a><a href="/cookies/en/">English</a><a href="/cookies/es/">Español</a></nav></main></html>',
        encoding="utf-8",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    build(parser.parse_args().output)
