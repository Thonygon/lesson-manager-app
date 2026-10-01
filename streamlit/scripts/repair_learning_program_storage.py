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
from helpers.learning_programs import repair_learning_program_storage  # noqa: E402


def _program_ids_for_all() -> list[int]:
    rows = (
        get_sb()
        .table("learning_programs")
        .select("id")
        .order("id")
        .execute()
        .data
        or []
    )
    return [int(row.get("id") or 0) for row in rows if int(row.get("id") or 0) > 0]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Repair learning_programs.program_data IDs against relational unit/topic rows."
    )
    parser.add_argument("--program-id", type=int, action="append", default=[])
    parser.add_argument("--all", action="store_true", help="Inspect or repair every learning program.")
    parser.add_argument("--apply", action="store_true", help="Write changes. Omit for a dry run.")
    args = parser.parse_args()

    program_ids = list(dict.fromkeys(args.program_id or []))
    if args.all:
        program_ids = _program_ids_for_all()
    if not program_ids:
        parser.error("Pass --program-id ID or --all.")

    failures = 0
    for program_id in program_ids:
        result = repair_learning_program_storage(program_id, apply=args.apply)
        if not result.get("ok"):
            failures += 1
        print(result)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
