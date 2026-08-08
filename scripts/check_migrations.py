from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


LEDGER_VERSION = 1
DEFAULT_MIGRATION_DIR = Path("migrations")
DEFAULT_LEDGER_PATH = DEFAULT_MIGRATION_DIR / "ledger.json"


@dataclass(frozen=True)
class MigrationIssue:
    code: str
    message: str


def migration_checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _contains_executable_sql(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"--[^\n]*", "", text)
    return bool(text.strip().strip(";"))


def load_ledger(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("version") != LEDGER_VERSION:
        raise ValueError(f"unsupported migration ledger version in {path}")
    if not isinstance(payload.get("migrations"), list):
        raise ValueError(f"migration ledger entries must be a list in {path}")
    return payload


def validate_local_migrations(
    migration_dir: Path = DEFAULT_MIGRATION_DIR,
    ledger_path: Path = DEFAULT_LEDGER_PATH,
) -> tuple[list[dict[str, str]], list[MigrationIssue]]:
    issues: list[MigrationIssue] = []
    try:
        payload = load_ledger(ledger_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [], [MigrationIssue("ledger_invalid", str(exc))]

    entries: list[dict[str, str]] = []
    seen_names: set[str] = set()
    seen_checksums: dict[str, str] = {}
    for raw_entry in payload["migrations"]:
        if not isinstance(raw_entry, dict):
            issues.append(MigrationIssue("ledger_entry_invalid", "migration ledger entry is not an object"))
            continue
        name = str(raw_entry.get("name") or "").strip()
        checksum = str(raw_entry.get("sha256") or "").strip().lower()
        normalized_name = name.lower()
        if not name.endswith(".sql") or Path(name).name != name:
            issues.append(MigrationIssue("migration_name_invalid", f"invalid migration name: {name or '<empty>'}"))
            continue
        if normalized_name in seen_names:
            issues.append(MigrationIssue("migration_duplicate", f"duplicate ledger migration: {name}"))
            continue
        seen_names.add(normalized_name)
        if not re.fullmatch(r"[0-9a-f]{64}", checksum):
            issues.append(MigrationIssue("checksum_invalid", f"invalid checksum for {name}"))
        previous_name = seen_checksums.get(checksum)
        if previous_name:
            issues.append(MigrationIssue("content_duplicate", f"{name} duplicates {previous_name}"))
        elif checksum:
            seen_checksums[checksum] = name
        entries.append({"name": name, "sha256": checksum})

    disk_files = sorted(path for path in migration_dir.glob("*.sql") if path.is_file())
    disk_names = {path.name.lower(): path for path in disk_files}
    ledger_names = {entry["name"].lower(): entry for entry in entries}

    for normalized_name, path in disk_names.items():
        if normalized_name not in ledger_names:
            issues.append(MigrationIssue("migration_untracked", f"migration is missing from ledger: {path.name}"))
        if not _contains_executable_sql(path):
            issues.append(MigrationIssue("migration_empty", f"migration has no executable SQL: {path.name}"))

    for normalized_name, entry in ledger_names.items():
        path = disk_names.get(normalized_name)
        if path is None:
            issues.append(MigrationIssue("migration_missing", f"ledger migration is missing from disk: {entry['name']}"))
            continue
        actual_checksum = migration_checksum(path)
        if actual_checksum != entry["sha256"]:
            issues.append(
                MigrationIssue(
                    "checksum_mismatch",
                    f"checksum changed for {entry['name']}: expected {entry['sha256']}, got {actual_checksum}",
                )
            )
    return entries, issues


def compare_applied_migrations(
    expected: list[dict[str, str]],
    applied: list[dict[str, Any]],
) -> list[MigrationIssue]:
    issues: list[MigrationIssue] = []
    expected_by_name = {entry["name"]: entry["sha256"] for entry in expected}
    applied_by_name = {str(row.get("name") or ""): str(row.get("checksum") or "") for row in applied}
    for name, checksum in expected_by_name.items():
        if name not in applied_by_name:
            issues.append(MigrationIssue("migration_unapplied", f"migration is not recorded as applied: {name}"))
        elif applied_by_name[name] != checksum:
            issues.append(MigrationIssue("applied_checksum_mismatch", f"applied checksum differs for {name}"))
    for name in sorted(set(applied_by_name) - set(expected_by_name)):
        issues.append(MigrationIssue("applied_migration_unknown", f"database contains unknown migration: {name}"))
    return issues


def load_remote_migration_ledger(url: str, key: str) -> list[dict[str, Any]]:
    endpoint = f"{url.rstrip('/')}/rest/v1/app_schema_migrations?{urlencode({'select': 'name,checksum,applied_at', 'order': 'applied_at.asc'})}"
    request = Request(
        endpoint,
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
        },
    )
    with urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Supabase migration ledger response was not a list")
    return [dict(row) for row in payload if isinstance(row, dict)]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate Classio SQL migrations and optional Supabase application ledger.")
    parser.add_argument("--migration-dir", type=Path, default=DEFAULT_MIGRATION_DIR)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER_PATH)
    parser.add_argument("--require-applied", action="store_true", help="Compare local migrations with Supabase app_schema_migrations.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    entries, issues = validate_local_migrations(args.migration_dir, args.ledger)
    if args.require_applied and not issues:
        url = str(os.getenv("SUPABASE_URL") or "").strip()
        key = str(os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
        if not url or not key:
            issues.append(
                MigrationIssue(
                    "remote_configuration_missing",
                    "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required",
                )
            )
        else:
            try:
                issues.extend(compare_applied_migrations(entries, load_remote_migration_ledger(url, key)))
            except Exception as exc:
                issues.append(MigrationIssue("remote_ledger_unavailable", f"could not read Supabase migration ledger: {type(exc).__name__}"))

    if issues:
        for issue in issues:
            print(f"ERROR [{issue.code}] {issue.message}", file=sys.stderr)
        print(f"Migration check failed with {len(issues)} issue(s).", file=sys.stderr)
        return 1
    scope = "local and applied" if args.require_applied else "local"
    print(f"Migration check passed ({scope}): {len(entries)} migrations verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
