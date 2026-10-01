from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from helpers.student_recommendation_open_7d_eval import generate_student_recommendation_open_7d_evaluation  # noqa: E402
from helpers.student_recommendation_open_7d_review import review_student_recommendation_open_7d  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    result = generate_student_recommendation_open_7d_evaluation(output_dir, run_id=str(args.run_id))
    review_result = review_student_recommendation_open_7d(output_dir)
    print(json.dumps({"result": result, "review_result": review_result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
