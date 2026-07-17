from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    try:
        import tomli as tomllib
    except ModuleNotFoundError:  # pragma: no cover
        tomllib = None


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _bootstrap_supabase_env() -> None:
    candidates = [
        ROOT / ".streamlit" / "secrets.toml",
        ROOT / ".streamlit" / "secrets.toml.save",
    ]
    for candidate in candidates:
        if not candidate.exists() or tomllib is None:
            continue
        try:
            with candidate.open("rb") as fh:
                payload = tomllib.load(fh)
        except Exception:
            continue
        for key in ("SUPABASE_URL", "SUPABASE_KEY"):
            if not os.getenv(key) and payload.get(key):
                os.environ[key] = str(payload[key])


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return str(value)


_bootstrap_supabase_env()

from helpers.assigned_resource_open_7d_eval import generate_assigned_resource_open_7d_evaluation  # noqa: E402
from helpers.assigned_resource_open_7d_review import review_assigned_resource_open_7d  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full assigned-resource open-within-7-days evaluation pipeline.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    result = generate_assigned_resource_open_7d_evaluation(output_dir, run_id=str(args.run_id))
    review_result = review_assigned_resource_open_7d(output_dir)
    print(json.dumps({"result": _json_safe(result), "review_result": _json_safe(review_result)}, sort_keys=True))


if __name__ == "__main__":
    main()
