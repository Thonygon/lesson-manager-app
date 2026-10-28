"""Fail CI when a tracked source file contains a likely private credential."""

from __future__ import annotations

import base64
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "private key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "OpenAI key": re.compile(rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}\b"),
    "Google API key": re.compile(rb"\bAIza[0-9A-Za-z_-]{35}\b"),
    "GitHub token": re.compile(rb"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}\b"),
}
JWT = re.compile(rb"\beyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")


def has_service_role_jwt(data: bytes) -> bool:
    for match in JWT.finditer(data):
        payload = match.group().split(b".")[1]
        try:
            decoded = json.loads(base64.urlsafe_b64decode(payload + b"=" * (-len(payload) % 4)))
        except (ValueError, UnicodeDecodeError):
            continue
        if decoded.get("role") == "service_role":
            return True
    return False


def main() -> int:
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).split(b"\0")
    findings: list[str] = []
    for name in filter(None, tracked):
        path = ROOT / name.decode("utf-8", errors="surrogateescape")
        if not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        data = path.read_bytes()
        if b"\0" in data:
            continue
        for label, pattern in PATTERNS.items():
            if pattern.search(data):
                findings.append(f"{path.relative_to(ROOT)}: {label}")
        if has_service_role_jwt(data):
            findings.append(f"{path.relative_to(ROOT)}: Supabase service role JWT")
    if findings:
        print("Potential secrets in tracked files (values suppressed):")
        print("\n".join(findings))
        return 1
    print(f"Secret exposure check passed ({len(tracked) - 1} tracked paths inspected).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
