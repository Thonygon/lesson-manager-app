"""Keep AI outbound routes and destination hosts attached to a reviewed inventory."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "docs/AI_DATA_FLOW_INVENTORY.json"
AI_ROUTE_GLOBS = ("expo/src/app/api/*+api.ts", "expo/src/server/ai-provider-chain.ts", "streamlit/helpers/*.py")
OUTBOUND_MARKERS = ("requestAiProvider(", "fetchBoundedAiJson(")
SDK_CALL_PATTERN = re.compile(r"\b(?:chat\s*\.\s*completions\s*\.\s*(?:create|stream)|models\s*\.\s*(?:generate_content|generateContent|generate_content_stream|generateContentStream)|images\s*\.\s*(?:generate|edit)|responses\s*\.\s*(?:create|stream))\s*\(")
HOST_PATTERN = re.compile(r"https://([A-Za-z0-9.-]+)")
NON_PROVIDER_REFERERS = {"app.masterclassio.com", "classio.app"}
APPROVAL_CALLS = {
    "expo": "approvedAiProviders(",
    "streamlit": "require_ai_runtime_approval(",
}


def _python_unguarded_sdk_calls(source: str) -> list[int]:
    """Find SDK calls whose containing function has no earlier approval check."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []  # Python syntax is checked separately by CI.
    failures: list[int] = []

    class Visit(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self._function(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self._function(node)

        def _function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
            calls: list[ast.Call] = []

            def collect(child: ast.AST) -> None:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    return
                if isinstance(child, ast.Call):
                    calls.append(child)
                for descendant in ast.iter_child_nodes(child):
                    collect(descendant)

            for statement in node.body:
                collect(statement)
            guards = [call.lineno for call in calls
                      if isinstance(call.func, ast.Name) and call.func.id == "require_ai_runtime_approval"]
            for call in calls:
                name = ast.unparse(call.func)
                if SDK_CALL_PATTERN.search(name + "(") and not any(line < call.lineno for line in guards):
                    failures.append(call.lineno)
            for statement in node.body:
                self.visit(statement)

    Visit().visit(tree)
    return sorted(set(failures))


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
        for key in ("purpose", "data_categories", "destinations", "live_check", "approval_surface", "approval_version"):
            if not flow.get(key):
                errors.append(f"{flow['id']}: missing {key}")
        if not set(flow["destinations"]) <= approved:
            errors.append(f"{flow['id']}: destination outside approved list")
        for key in ("source", "boundary"):
            if not (ROOT / flow[key]).is_file():
                errors.append(f"{flow['id']}: missing {key} file")
        source_path = ROOT / flow["source"]
        if source_path.is_file() and flow.get("approval_surface") and flow.get("approval_version"):
            text = source_path.read_text(errors="replace")
            call = APPROVAL_CALLS["streamlit" if flow["source"].startswith("streamlit/") else "expo"]
            if call not in text or flow["approval_surface"] not in text or flow["approval_version"] not in text:
                errors.append(f"{flow['id']}: missing runtime approval for inventoried surface/version")
            elif flow["source"].startswith("expo/"):
                first_outbound = min((position for marker in OUTBOUND_MARKERS
                                      if (position := text.find(marker)) >= 0), default=-1)
                sdk_match = SDK_CALL_PATTERN.search(text)
                if sdk_match and (first_outbound < 0 or sdk_match.start() < first_outbound):
                    first_outbound = sdk_match.start()
                if first_outbound >= 0 and text.find(call) > first_outbound:
                    errors.append(f"{flow['id']}: provider call precedes runtime approval")
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
                if relative.startswith("streamlit/"):
                    for line in _python_unguarded_sdk_calls(source):
                        errors.append(f"AI SDK call without an earlier approval check: {relative}:{line}")
    return errors


if __name__ == "__main__":
    findings = check()
    if findings:
        raise SystemExit("\n".join(findings))
    print("AI data-flow inventory check passed.")
