"""Regenerate the Expo Admin intelligence catalog from Streamlit's reviewed blueprint."""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def constant(path: str, name: str):
    module = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    for node in module.body:
        target = node.target if isinstance(node, ast.AnnAssign) else node.targets[0] if isinstance(node, ast.Assign) and len(node.targets) == 1 else None
        if isinstance(target, ast.Name) and target.id == name:
            return ast.literal_eval(node.value)
    raise ValueError(f"{name} missing from {path}")


blueprint = constant("streamlit/services/eic_service.py", "COMPONENT_BLUEPRINT")
names = constant("streamlit/services/eic_display_service.py", "COMPONENT_NAME_KEYS")
texts = constant("streamlit/services/eic_display_service.py", "COMPONENT_TEXT_KEYS")
dictionaries = {
    "en": constant("streamlit/translations_en.py", "EN"),
    "es": constant("streamlit/translations_es.py", "ES"),
    "tr": constant("streamlit/translations_tr.py", "TR"),
}
fields = ("business_question", "decision_supported", "production_use", "limitation", "product_surface", "educational_value", "outcome_metric")
rows = []
for component in blueprint:
    component_id = component["component_id"]
    translations = {}
    for language, dictionary in dictionaries.items():
        localized = {"name": dictionary.get(names.get(component_id, ""), component["name"])}
        for field in fields:
            localized[field] = dictionary.get(texts.get(component_id, {}).get(field, ""), component.get(field, ""))
        translations[language] = localized
    rows.append({
        "component_id": component_id,
        "component_type": component.get("component_type", ""),
        "operational_status": component.get("operational_status", ""),
        "data_maturity": component.get("data_maturity", ""),
        "evidence_maturity": component.get("evidence_maturity", ""),
        "translations": translations,
    })
output = ROOT / "expo/src/data/admin-intelligence-catalog.ts"
output.write_text("// Generated from Streamlit's reviewed EIC blueprint and translation catalogs.\nexport const ADMIN_INTELLIGENCE_CATALOG = " + json.dumps(rows, ensure_ascii=False, indent=2) + " as const;\n", encoding="utf-8")
print(f"Wrote {len(rows)} intelligence systems to {output.relative_to(ROOT)}")
