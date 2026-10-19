"""Compare the real Streamlit package dashboard using frozen, non-user data."""
import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "streamlit"))
from helpers import dashboard  # noqa: E402

dashboard.ts_today_naive = lambda: pd.Timestamp("2026-10-12")
fixture = json.loads((Path(__file__).parent / "fixtures" / "teacher-ledger.json").read_text())
result = dashboard._rebuild_dashboard_from_frames(pd.DataFrame(fixture["lessons"]), pd.DataFrame(fixture["payments"]))
payments_by_id = {row["id"]: row for row in fixture["payments"]}
print(json.dumps([{"student": row.Student, "purchased": int(payments_by_id[row.Payment_ID]["number_of_lesson"] + payments_by_id[row.Payment_ID]["lesson_adjustment_units"]), "delivered": int(row.Lessons_Taken_Units), "remaining": int(row.Lessons_Left_Units), "status": row.Status} for row in result.itertuples()], sort_keys=True))
