"""Render versioned legal pages and a matching Expo publication manifest."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "legal/agreements.v1.json"
LANGUAGES = ("en", "es", "tr")
SLUGS = ("terms", "teacher-data")
NAV = {
    "en": ("Terms of use", "Educator data terms", "Privacy", "Cookies and storage"),
    "es": ("Condiciones de uso", "Datos docentes", "Privacidad", "Cookies y almacenamiento"),
    "tr": ("Kullanım koşulları", "Eğitimci veri koşulları", "Gizlilik", "Çerezler ve depolama"),
}


def escape(value: str) -> str:
    return html.escape(value, quote=True)


def document_hash(document: dict) -> str:
    canonical = json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def render(data: dict, slug: str, language: str, *, canonical_slug: str | None = None) -> str:
    document = data["documents"][slug][language]
    digest = document_hash(document)
    canonical = f"https://masterclassio.com/{canonical_slug or slug}/{language}/" if canonical_slug is None else f"https://masterclassio.com/{slug}/"
    languages = "".join(
        f'<a lang="{code}" hreflang="{code}" href="/{slug}/{code}/"{active}>{code.upper()}</a>'
        for code in LANGUAGES
        for active in (' aria-current="page"' if code == language else '',)
    )
    navigation = "".join(
        f'<a href="/{target}/{language}/"{active}>{escape(label)}</a>'
        for target, label in zip(SLUGS, NAV[language][:2])
        for active in (' aria-current="page"' if target == slug else '',)
    )
    sections = "".join(
        f'<section class="notice-section"><h2>{escape(section["title"])}</h2>'
        + "".join(f'<p>{escape(paragraph)}</p>' for paragraph in section["paragraphs"])
        + "</section>"
        for section in document["sections"]
    )
    return f'''<!doctype html><html lang="{language}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="index,follow">
<meta name="description" content="{escape(document['lead'])}"><meta name="classio:version" content="{escape(data['version'])}">
<meta name="classio:effective-date" content="{escape(data['effective_date'])}"><meta name="classio:publication-approver" content="{escape(data['publication_approver'])}">
<meta name="classio:sha256" content="{digest}"><link rel="canonical" href="{canonical}">
<link rel="stylesheet" href="/privacy/privacy.css"><title>{escape(document['title'])} · Master Classio</title></head><body>
<a class="skip" href="#notice">{escape({'en':'Skip to content','es':'Ir al contenido','tr':'İçeriğe geç'}[language])}</a>
<header><div class="wrap header"><a class="brand" href="/">Master Classio</a><nav class="languages" aria-label="Languages">{languages}</nav></div></header>
<main class="wrap" id="notice"><p class="eyebrow">{escape(data['version'])} · {escape(data['effective_date'])}</p><h1>{escape(document['title'])}</h1>
<p class="lead">{escape(document['lead'])}</p><nav class="audiences" aria-label="Legal documents">{navigation}</nav>
<article>{sections}</article><p><a href="/privacy/{language}/app/">{escape(NAV[language][2])}</a> · <a href="/cookies/{language}/">{escape(NAV[language][3])}</a> · <a href="mailto:info@masterclassio.com">info@masterclassio.com</a></p>
</main><footer><div class="wrap"><a href="/">Master Classio</a><span>{escape(data['publication_approver'])} · {escape(data['effective_date'])}</span></div></footer></body></html>'''


def build(output: Path, expo_output: Path | None = None) -> dict:
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    assert data["version"] and data["effective_date"] and data["publication_approver"]
    assert set(data["documents"]) == set(SLUGS)
    manifest = {"version": data["version"], "effectiveDate": data["effective_date"], "publicationApprover": data["publication_approver"], "documents": []}
    for slug in SLUGS:
        assert set(data["documents"][slug]) == set(LANGUAGES)
        for language in LANGUAGES:
            document = data["documents"][slug][language]
            assert len(document["sections"]) >= 5
            assert all(section["paragraphs"] for section in document["sections"])
            page = render(data, slug, language)
            if "TODO" in page or "[insert" in page.lower():
                raise ValueError(f"Unfinished document {slug}/{language}")
            destination = output / slug / language / "index.html"
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(page, encoding="utf-8")
            manifest["documents"].append({"slug": slug, "language": language, "url": f"https://masterclassio.com/{slug}/{language}/", "sha256": document_hash(document)})
        (output / slug / "index.html").write_text(render(data, slug, "en", canonical_slug=slug), encoding="utf-8")
    (output / "legal-publication.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if expo_output:
        expo_output.parent.mkdir(parents=True, exist_ok=True)
        expo_output.write_text("// Generated by scripts/build_legal_agreements.py.\nexport const LEGAL_PUBLICATION = " + json.dumps(manifest, ensure_ascii=False, indent=2) + " as const;\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expo-output", type=Path)
    args = parser.parse_args()
    build(args.output, args.expo_output)
