"""Keep AI outbound routes and destination hosts attached to a reviewed inventory."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "docs/AI_DATA_FLOW_INVENTORY.json"
AI_ROUTE_GLOBS = ("expo/src/app/api/*+api.ts", "expo/src/server/ai-provider-chain.ts", "streamlit/helpers/*.py")
OUTBOUND_MARKERS = ("requestAiProvider(", "fetchBoundedAiJson(")
SDK_CALL_PATTERN = re.compile(r"\b(?:chat\s*\.\s*completions\s*\.\s*create|models\s*\.\s*generate_content|images\s*\.\s*generate|responses\s*\.\s*create)\s*\(")
HOST_PATTERN = re.compile(r"https://([A-Za-z0-9.-]+)")
NON_PROVIDER_REFERERS = {"app.masterclassio.com", "classio.app"}


def check() -> list[str]:
    data = json.loads(INVENTORY.read_text())
    errors: list[str] = []
    approved = set(data["approved_hosts"])
    flows = data["flows"]
    ids = [flow["id"] for flow in flows]
    if len(ids) != len(set(ids)):
        errors.append("Duplicate flow ID")
    covered = {flow["source"] for flow in flows} | {flow["boundary"] for flow in flows}
    for flow in flows:
        for key in ("purpose", "data_categories", "destinations", "live_check"):
            if not flow.get(key):
                errors.append(f"{flow['id']}: missing {key}")
        if not set(flow["destinations"]) <= approved:
            errors.append(f"{flow['id']}: destination outside approved list")
        for key in ("source", "boundary"):
            if not (ROOT / flow[key]).is_file():
                errors.append(f"{flow['id']}: missing {key} file")
    for pattern in AI_ROUTE_GLOBS:
        for path in ROOT.glob(pattern):
            source = path.read_text(errors="replace")
            relative = str(path.relative_to(ROOT))
            hosts = HOST_PATTERN.findall(source)
            if any(marker in source for marker in OUTBOUND_MARKERS) or SDK_CALL_PATTERN.search(source) or any(host in approved for host in hosts):
                if relative not in covered:
                    errors.append(f"Uninventoried AI boundary: {relative}")
                for host in hosts:
                    if host not in approved | NON_PROVIDER_REFERERS:
                        errors.append(f"Unreviewed external host in AI boundary: {relative}: {host}")
    return errors


if __name__ == "__main__":
    findings = check()
    if findings:
        raise SystemExit("\n".join(findings))
    print("AI data-flow inventory check passed.")
