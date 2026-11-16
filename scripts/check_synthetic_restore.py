"""Compare restored synthetic payment, class, and profile rows without exporting PII.

Use a separate restored Supabase project. Set SUPABASE_URL and
SUPABASE_SERVICE_ROLE_KEY for the source when capturing a manifest, then set
them for the restored project when verifying it. Set
CLASSIO_RESTORE_CONFIRM_SYNTHETIC=1 and pass only fixture IDs. The manifest
contains IDs and SHA-256 digests, never row contents or credentials.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


TABLE_KEYS = {"payments": "id", "classes": "id", "profiles": "user_id"}


def fetch_row(table: str, row_id: str, *, base: str, key: str, open_url=urlopen) -> dict:
    column = TABLE_KEYS[table]
    query = urlencode({"select": "*", column: f"eq.{row_id}", "limit": "2"})
    request = Request(
        f"{base.rstrip('/')}/rest/v1/{table}?{query}",
        headers={"apikey": key, "Authorization": f"Bearer {key}", "Accept": "application/json"},
    )
    with open_url(request, timeout=20) as response:
        if response.status != 200:
            raise RuntimeError(f"{table}: expected HTTP 200, got {response.status}")
        rows = json.load(response)
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise RuntimeError(f"{table}: expected exactly one fixture row")
    return rows[0]


def digest(row: dict) -> str:
    encoded = json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def compare(fixtures: dict[str, str], *, base: str, key: str, expected: dict | None = None, open_url=urlopen) -> dict:
    if set(fixtures) != set(TABLE_KEYS) or any(not isinstance(value, str) or not value for value in fixtures.values()):
        raise ValueError("Provide one nonempty synthetic row ID for payments, classes, and profiles")
    if expected is not None and expected.get("fixtures") != fixtures:
        raise ValueError("Restore fixture IDs do not match the baseline manifest")
    fingerprints = {
        table: digest(fetch_row(table, fixtures[table], base=base, key=key, open_url=open_url))
        for table in TABLE_KEYS
    }
    if expected is not None:
        mismatches = [table for table in TABLE_KEYS if expected.get("sha256", {}).get(table) != fingerprints[table]]
        if mismatches:
            raise RuntimeError(f"Restore differs for: {', '.join(mismatches)}")
    return {"version": 1, "fixtures": fixtures, "sha256": fingerprints}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("capture", "verify"))
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--payment-id", required=True)
    parser.add_argument("--class-id", required=True)
    parser.add_argument("--profile-user-id", required=True)
    args = parser.parse_args()
    if not args.manifest.name.endswith(".restore-manifest.json"):
        parser.error("Use a *.restore-manifest.json path, which the repository ignores")
    if os.getenv("CLASSIO_RESTORE_CONFIRM_SYNTHETIC") != "1":
        parser.error("Set CLASSIO_RESTORE_CONFIRM_SYNTHETIC=1 for synthetic records only")
    base, key = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not base or not key:
        parser.error("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
    fixtures = {"payments": args.payment_id, "classes": args.class_id, "profiles": args.profile_user_id}
    if args.mode == "capture":
        if args.manifest.exists():
            parser.error("Baseline manifest already exists; choose a new path")
        manifest = compare(fixtures, base=base, key=key)
        args.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        args.manifest.chmod(0o600)
        print("Captured three synthetic row fingerprints; no row contents were written.")
    else:
        expected = json.loads(args.manifest.read_text(encoding="utf-8"))
        compare(fixtures, base=base, key=key, expected=expected)
        print("PASS: synthetic payments, classes, and profiles match the restored snapshot.")


if __name__ == "__main__":
    main()
