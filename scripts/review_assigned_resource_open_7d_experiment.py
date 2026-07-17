from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from helpers.assigned_resource_open_7d_eval import DEFAULT_OUTPUT_DIR  # noqa: E402
from helpers.assigned_resource_open_7d_review import review_assigned_resource_open_7d  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Review the Classio assigned-resource open-within-7-days experiment.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()
    result = review_assigned_resource_open_7d(Path(args.output_dir))
    print(result["final_verdict"])
    print(result["overall_model_conclusion"])


if __name__ == "__main__":
    main()
