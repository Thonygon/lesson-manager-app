#!/usr/bin/env python3
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
    if tomllib is None:
        return
    for candidate in (
        ROOT / ".streamlit" / "secrets.toml",
        ROOT / ".streamlit" / "secrets.toml.save",
    ):
        if not candidate.exists():
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

from core.database import get_sb  # noqa: E402
from helpers.quick_exam_builder import attach_exam_language_metadata  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair quick_exams language metadata.")
    parser.add_argument("--apply", action="store_true", help="Write changes back to Supabase.")
    args = parser.parse_args()

    sb = get_sb()
    rows = (
        sb.table("quick_exams")
        .select("id,subject,plan_language,student_material_language,exam_data,answer_key")
        .order("id")
        .execute()
        .data
        or []
    )

    repaired = 0
    unchanged = 0

    for row in rows:
        exam_data = row.get("exam_data") if isinstance(row.get("exam_data"), dict) else {}
        answer_key = row.get("answer_key") if isinstance(row.get("answer_key"), dict) else {}
        repaired_exam_data, resolved_plan, resolved_student = attach_exam_language_metadata(
            exam_data,
            answer_key=answer_key,
            subject=str(row.get("subject") or "").strip(),
            plan_language=str(row.get("plan_language") or "").strip(),
            student_material_language=str(row.get("student_material_language") or "").strip(),
        )
        changed = (
            repaired_exam_data != exam_data
            or resolved_plan != str(row.get("plan_language") or "").strip().lower()
            or resolved_student != str(row.get("student_material_language") or "").strip().lower()
        )
        if not changed:
            unchanged += 1
            continue

        repaired += 1
        print(
            f"repairable exam id={row.get('id')} subject={row.get('subject')} "
            f"plan_language={resolved_plan} student_material_language={resolved_student}"
        )
        if args.apply:
            (
                sb.table("quick_exams")
                .update(
                    {
                        "exam_data": repaired_exam_data,
                        "plan_language": resolved_plan,
                        "student_material_language": resolved_student,
                    }
                )
                .eq("id", row.get("id"))
                .execute()
            )

    mode = "applied" if args.apply else "dry-run"
    print(f"{mode}: repaired={repaired} unchanged={unchanged}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
