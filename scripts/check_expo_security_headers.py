"""Check the Expo Router web security header baseline."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def check() -> None:
    app = json.loads((ROOT / "expo/app.json").read_text())
    router = next(plugin[1] for plugin in app["expo"]["plugins"] if isinstance(plugin, list) and plugin[0] == "expo-router")
    app_headers = router["headers"]
    for name in ("Content-Security-Policy", "X-Content-Type-Options", "Referrer-Policy", "Permissions-Policy"):
        assert name in app_headers, f"Expo Router is missing {name}"
    assert "frame-ancestors 'none'" in app_headers["Content-Security-Policy"]


if __name__ == "__main__":
    check()
    print("Expo security header baseline passed.")
