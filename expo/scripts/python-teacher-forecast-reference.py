"""Frozen Streamlit forecast reference; uses no database or user records."""
import ast
from pathlib import Path
import json
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "streamlit"))
from helpers import forecast  # noqa: E402
from helpers.goal_optimizer import build_goal_optimization  # noqa: E402

forecast.ts_today_naive = lambda: pd.Timestamp("2026-10-12")
dashboard = pd.DataFrame([
    {"Student": "Ana", "Status": "active", "Payment_Date": "2026-09-01", "Package_Start_Date": "2026-09-01", "Package_Expiry_Date": "", "Last_Lesson_Date": "2026-09-20", "Lessons_Left_Units": 4, "Lessons_Paid_Total": 10},
    {"Student": "Bob", "Status": "active", "Payment_Date": "2026-02-01", "Package_Start_Date": "2026-02-01", "Package_Expiry_Date": "2026-11-01", "Last_Lesson_Date": "", "Lessons_Left_Units": 2, "Lessons_Paid_Total": 20},
    {"Student": "Clara", "Status": "finished", "Payment_Date": "2026-10-01", "Package_Start_Date": "2026-10-01", "Package_Expiry_Date": "", "Last_Lesson_Date": "", "Lessons_Left_Units": -1, "Lessons_Paid_Total": 5},
])
classes = pd.DataFrame([
    {"student": "Ana", "lesson_date": "2026-09-20", "number_of_lesson": 4, "modality": "Online", "note": ""},
    {"student": "Zed", "lesson_date": "2026-09-21", "number_of_lesson": 8, "modality": "Online", "note": ""},
    {"student": "Bob", "lesson_date": "2026-09-19", "number_of_lesson": 2, "modality": "Online", "note": "[FREE]"},
])
rows = forecast.build_forecast_table(payment_buffer_days=7, dashboard_df=dashboard, classes_df=classes)
forecast_rows = [{
    "student": row["Student"],
    "rate": row["Units_Per_Day"],
    "days": row["Days_To_Finish"],
    "finish": row["Estimated_Finish_Date"],
    "reminder": row["Reminder_Date"],
    "due": bool(row["Due_Now"]),
} for _, row in rows.iterrows()]

# Compile the actual nested Streamlit projection helpers without importing its UI page.
page_source = (Path(__file__).resolve().parents[2] / "streamlit" / "app_pages" / "app_page_analytics.py").read_text()
render = next(node for node in ast.parse(page_source).body if isinstance(node, ast.FunctionDef) and node.name == "render_analytics")
names = {"_first_existing_col", "_ytd_income", "_student_baseline_payment", "_estimate_typical_units_from_dashboard", "estimate_year_projection_current_students"}
functions = [node for node in render.body if isinstance(node, ast.FunctionDef) and node.name in names]
environment = {"pd": pd, "to_dt_naive": forecast.to_dt_naive, "dashboard_student_units": {"Ana": 10, "Bob": 20, "Clara": 5}}
exec(compile(ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])), "app_page_analytics.py", "exec"), environment)
payments = pd.DataFrame([
    {"student": "Ana", "payment_date": "2026-01-01", "paid_amount": 100},
    {"student": "Ana", "payment_date": "2026-07-01", "paid_amount": 120},
    {"student": "Ana", "payment_date": "2026-09-01", "paid_amount": 140},
    {"student": "Bob", "payment_date": "2026-02-01", "paid_amount": 200},
    {"student": "Clara", "payment_date": "2026-10-01", "paid_amount": 50},
])
projection = environment["estimate_year_projection_current_students"](pd.Timestamp("2026-10-12"), rows, payments)
optimization = build_goal_optimization(
    goal=1500, baseline_projection=projection["projected"], ytd_income=projection["ytd"],
    expected_future=projection["expected_future"], effective_rate=610 / 14,
    payments_df=payments, forecast_df=rows, today=pd.Timestamp("2026-10-12"),
)
print(json.dumps({"forecast": forecast_rows, "projection": projection, "optimization": {
    "baselineProjection": optimization.baseline_projection,
    "optimizedProjection": optimization.optimized_projection,
    "gap": optimization.gap,
    "remainingGap": optimization.remaining_gap,
    "goalProbability": optimization.goal_probability,
    "optimizedProbability": optimization.optimized_probability,
    "pricePct": optimization.price_pct,
    "newStudents": optimization.new_students,
    "extraUnitsWeek": optimization.extra_units_week,
    "renewalFocus": optimization.renewal_focus,
    "avgPackageValue": optimization.avg_package_value,
    "effectiveRate": optimization.effective_rate,
    "weeksLeft": optimization.weeks_left,
    "renewalPool": optimization.renewal_pool,
    "riskRate": optimization.risk_rate,
    "actionStudents": [{"student": item["student"], "value": item["value"], "unitsLeft": item["units_left"], "reminderDate": item["reminder_date"], "finishDate": item["finish_date"], "dueNow": item["due_now"]} for item in optimization.action_students],
    "scenarios": [{"key": item["key"], "impact": item["impact"], "value": item["value"]} for item in optimization.scenarios],
}}))
