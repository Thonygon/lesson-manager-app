"""Synthetic, reproducible PII redaction evaluation; no production records."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from helpers.ai_prompt_privacy import redact_direct_identifiers  # noqa: E402


CASES = (
    ("es", "email", "Correo: ana@example.com", "ana@example.com", True),
    ("en", "email", "Contact: ben@example.org", "ben@example.org", True),
    ("tr", "email", "E-posta: elif@example.com", "elif@example.com", True),
    ("es", "phone", "Teléfono: +34 612 345 678", "+34 612 345 678", True),
    ("en", "phone", "Phone: +44 7700 900123", "+44 7700 900123", True),
    ("tr", "phone", "GSM: +90 532 123 4567", "+90 532 123 4567", True),
    ("es", "identity", "DNI: 12345678Z", "12345678Z", True),
    ("en", "identity", "Passport: ABCDEF", "ABCDEF", True),
    ("tr", "identity", "TCKN: 10000000146", "10000000146", True),
    ("tr", "bank", "IBAN TR33 0006 1005 1978 6457 8413 26", "TR33 0006 1005 1978 6457 8413 26", True),
    ("es", "address", "Dirección: Calle Mayor 12", "Calle Mayor 12", True),
    ("en", "address", "Address: 12 Main Street", "12 Main Street", True),
    ("tr", "address", "Adres: Atatürk Caddesi 10", "Atatürk Caddesi 10", True),
    ("es", "pedagogy", "Tema: números y fracciones", "números y fracciones", False),
    ("en", "pedagogy", "Lesson topic: passport vocabulary and travel", "passport vocabulary and travel", False),
    ("tr", "pedagogy", "Konu: Sayılar ve toplama", "Sayılar ve toplama", False),
    ("es", "pedagogy", "Ejercicio: 12345678901 + 2", "12345678901 + 2", False),
)


def evaluate() -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0, "tn": 0})
    for locale, entity, prompt, marker, has_pii in CASES:
        output = redact_direct_identifiers(prompt)
        removed = marker not in output
        outcome = "tp" if has_pii and removed else "fn" if has_pii else "fp" if removed else "tn"
        for segment in ("all", f"locale:{locale}", f"entity:{entity}", f"locale:{locale}/entity:{entity}"):
            counts[segment][outcome] += 1
    return dict(sorted(counts.items()))


if __name__ == "__main__":
    result = evaluate()
    print(json.dumps({"dataset": "synthetic_v1", "cases": len(CASES), "confusion": result}, sort_keys=True))
    if result["all"]["fn"] or result["all"]["fp"]:
        raise SystemExit(1)
