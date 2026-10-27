"""Read-only RLS and Storage probe using two synthetic beta identities.

Required environment: SUPABASE_URL, SUPABASE_ANON_KEY,
CLASSIO_PRIVACY_OWNER_JWT, CLASSIO_PRIVACY_OTHER_JWT,
CLASSIO_PRIVACY_PRIVATE_WORKSHEET_ID, CLASSIO_PRIVACY_EXPOSURE_ID,
CLASSIO_PRIVACY_STORAGE_BUCKET, CLASSIO_PRIVACY_STORAGE_PATH.

Use fixtures owned by the owner token. No token, row or object content is printed.
"""

from __future__ import annotations

import json
import os
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


REQUIRED = (
    "SUPABASE_URL", "SUPABASE_ANON_KEY", "CLASSIO_PRIVACY_OWNER_JWT",
    "CLASSIO_PRIVACY_OTHER_JWT", "CLASSIO_PRIVACY_PRIVATE_WORKSHEET_ID",
    "CLASSIO_PRIVACY_EXPOSURE_ID", "CLASSIO_PRIVACY_STORAGE_BUCKET",
    "CLASSIO_PRIVACY_STORAGE_PATH",
)


def _read(url: str, token: str, key: str) -> tuple[int, bytes]:
    request = Request(url, headers={"apikey": key, "Authorization": f"Bearer {token}", "Accept": "application/json"})
    try:
        with urlopen(request, timeout=15) as response:
            return response.status, response.read(65536)
    except HTTPError as error:
        return error.code, error.read(1024)


def _rows(base: str, key: str, token: str, table: str, filters: dict[str, str]) -> tuple[int, int]:
    query = urlencode({"select": "id" if table == "worksheets" else "exposure_id", "limit": "2", **filters})
    status, payload = _read(f"{base}/rest/v1/{table}?{query}", token, key)
    if status != 200:
        return status, -1
    data = json.loads(payload)
    return status, len(data) if isinstance(data, list) else -1


def run() -> None:
    missing = [name for name in REQUIRED if not os.environ.get(name)]
    if missing:
        raise SystemExit(f"Missing environment variables: {', '.join(missing)}")
    env = os.environ
    base = env["SUPABASE_URL"].rstrip("/")
    key = env["SUPABASE_ANON_KEY"]
    owner = env["CLASSIO_PRIVACY_OWNER_JWT"]
    other = env["CLASSIO_PRIVACY_OTHER_JWT"]
    private_id = env["CLASSIO_PRIVACY_PRIVATE_WORKSHEET_ID"]
    exposure_id = env["CLASSIO_PRIVACY_EXPOSURE_ID"]
    checks: list[tuple[str, bool]] = []

    for label, table, filters in (
        ("private worksheet", "worksheets", {"id": f"eq.{private_id}", "is_public": "eq.false"}),
        ("recommendation exposure", "resource_exposures", {"exposure_id": f"eq.{exposure_id}"}),
    ):
        owner_status, owner_count = _rows(base, key, owner, table, filters)
        other_status, other_count = _rows(base, key, other, table, filters)
        anonymous_status, anonymous_count = _rows(base, key, key, table, filters)
        checks.append((f"{label}: owner can read", owner_status == 200 and owner_count == 1))
        checks.append((f"{label}: other cannot read", (other_status == 200 and other_count == 0) or other_status in (401, 403)))
        checks.append((f"{label}: anonymous cannot read", (anonymous_status == 200 and anonymous_count == 0) or anonymous_status in (401, 403)))

    for table in (
        "classio_generation_intent_feedback",
        "classio_generation_intent_feedback_events",
        "classio_teacher_relevance_feedback",
        "classio_teacher_relevance_feedback_events",
        "classio_document_export_events",
        "classio_privacy_retention_policies",
        "classio_privacy_retention_runs",
    ):
        for label, token in (("owner", owner), ("other", other)):
            status, _ = _read(f"{base}/rest/v1/{table}?select=*&limit=1", token, key)
            checks.append((f"{table}: {label} cannot read service-only rows", status in (401, 403)))

    bucket = quote(env["CLASSIO_PRIVACY_STORAGE_BUCKET"], safe="")
    object_path = quote(env["CLASSIO_PRIVACY_STORAGE_PATH"].lstrip("/"), safe="/")
    storage_url = f"{base}/storage/v1/object/authenticated/{bucket}/{object_path}"
    owner_status, _ = _read(storage_url, owner, key)
    other_status, _ = _read(storage_url, other, key)
    anonymous_status, _ = _read(storage_url, key, key)
    checks.extend((
        ("private Storage: owner can read", owner_status == 200),
        ("private Storage: other cannot read", other_status in (401, 403, 404)),
        ("private Storage: anonymous cannot read", anonymous_status in (401, 403, 404)),
    ))

    for label, passed in checks:
        print(f"{'PASS' if passed else 'FAIL'} {label}")
    if not all(passed for _, passed in checks):
        raise SystemExit(1)


if __name__ == "__main__":
    run()
