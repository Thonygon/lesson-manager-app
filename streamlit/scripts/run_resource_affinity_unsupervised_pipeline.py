from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

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


_bootstrap_supabase_env()

from helpers.resource_affinity_unsupervised_eval import (  # noqa: E402
    DEFAULT_OUTPUT_DIR,
    generate_resource_affinity_unsupervised_evaluation,
    review_resource_affinity_unsupervised,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Classio Experiment 3: unsupervised resource-affinity discovery.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--run-id", default="")
    args = parser.parse_args()
    result = generate_resource_affinity_unsupervised_evaluation(Path(args.output_dir), run_id=args.run_id or None)
    review_result = review_resource_affinity_unsupervised(Path(args.output_dir))
    print(json.dumps({"result": result, "review_result": review_result}, default=str))


if __name__ == "__main__":
    main()

