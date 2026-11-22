"""Delete expired or account-purged oral audio through Supabase Storage.

Requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in the server environment.
Run daily; this script never logs object paths or recording content.
"""

from __future__ import annotations

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

BUCKET = "classio-oral-audio"


def request(base: str, key: str, method: str, path: str, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = Request(base + path, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=20) as response:
            payload = response.read()
            return json.loads(payload) if payload else None
    except HTTPError as error:
        # An object already removed is an idempotent successful deletion.
        if method == "DELETE" and error.code == 404:
            return None
        raise RuntimeError(f"Supabase {method} returned HTTP {error.code}") from error
    except URLError as error:
        raise RuntimeError("Supabase connection failed") from error


def run() -> int:
    base = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not base.startswith("https://") or not key:
        print("Oral cleanup requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY", file=sys.stderr)
        return 2
    failed = 0
    processed = 0
    for _ in range(10):
        queue = request(base, key, "POST", "/rest/v1/rpc/classio_oral_cleanup_queue", {"p_limit": 100})
        if not isinstance(queue, list) or not queue:
            break
        for item in queue:
            identifier = item.get("id")
            path = item.get("object_path")
            if not isinstance(identifier, str) or not isinstance(path, str) or not path:
                failed += 1
                continue
            try:
                request(base, key, "DELETE", f"/storage/v1/object/{BUCKET}/{quote(path, safe='/')}")
                request(base, key, "POST", "/rest/v1/rpc/classio_oral_cleanup_result", {"p_id": identifier, "p_success": True})
                processed += 1
            except RuntimeError as error:
                failed += 1
                try:
                    request(base, key, "POST", "/rest/v1/rpc/classio_oral_cleanup_result", {"p_id": identifier, "p_success": False, "p_error": str(error)[:200]})
                except RuntimeError:
                    pass
        if len(queue) < 100 or failed:
            break
    print(f"Oral audio cleanup: {processed} removed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(run())
