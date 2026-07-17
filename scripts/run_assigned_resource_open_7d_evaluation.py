from __future__ import annotations

import argparse
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

from helpers.assigned_resource_open_7d_eval import DEFAULT_OUTPUT_DIR, generate_assigned_resource_open_7d_evaluation  # noqa: E402


def generate_report(output_dir: Path | str = DEFAULT_OUTPUT_DIR) -> dict:
    return generate_assigned_resource_open_7d_evaluation(output_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the assigned-resource open-within-7-days offline evaluation.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()
    result = generate_report(Path(args.output_dir))
    print(result["evaluation"]["maturity_verdict"])
    print(result["artifacts"]["run_summary"])


if __name__ == "__main__":
    main()
