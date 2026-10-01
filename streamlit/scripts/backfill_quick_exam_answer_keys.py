#!/usr/bin/env python3
"""Repair saved quick exams whose multiple-choice answers were stored only on question objects."""

from __future__ import annotations

import argparse

from core.database import get_sb
from helpers.quick_exam_builder import repair_exam_answer_key


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write repaired answer keys back to Supabase.")
    args = parser.parse_args()

    sb = get_sb()
    rows = (
        sb.table("quick_exams")
        .select("id, exam_data, answer_key")
        .execute()
    )

    repaired = 0
    unchanged = 0

    for row in rows.data or []:
        exam_data = row.get("exam_data") or {}
        answer_key = row.get("answer_key") or {}
        _, fixed_answer_key = repair_exam_answer_key(exam_data, answer_key)

        if fixed_answer_key == answer_key:
            unchanged += 1
            continue

        repaired += 1
        print(f"repairable exam id={row.get('id')}")

        if args.apply:
            (
                sb.table("quick_exams")
                .update({"answer_key": fixed_answer_key})
                .eq("id", row.get("id"))
                .execute()
            )

    mode = "applied" if args.apply else "dry-run"
    print(f"{mode}: repaired={repaired} unchanged={unchanged}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
