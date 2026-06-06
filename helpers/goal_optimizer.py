from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd

from helpers.ui_components import to_dt_naive


@dataclass
class OptimizationResult:
    goal: float
    baseline_projection: float
    optimized_projection: float
    gap: float
    remaining_gap: float
    goal_probability: float
    optimized_probability: float
    price_pct: float
    new_students: float
    extra_units_week: float
    renewal_focus: float
    price_impact: float
    growth_impact: float
    capacity_impact: float
    renewal_impact: float
    avg_package_value: float
    effective_rate: float
    weeks_left: float
    renewal_pool: float
    risk_rate: float
    action_students: list[dict[str, Any]]
    scenarios: list[dict[str, Any]]


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        value = float(value)
        if pd.isna(value):
            return default
        return value
    except Exception:
        return default


def _first_existing_col(df: pd.DataFrame | None, candidates: list[str]) -> str | None:
    if df is None or df.empty:
        return None
    norm = {str(c).strip().casefold(): c for c in df.columns}
    for candidate in candidates:
        key = str(candidate).strip().casefold()
        if key in norm:
            return norm[key]
    return None


def _student_baseline_payments(payments_df: pd.DataFrame | None, fx_rate: float) -> dict[str, float]:
    if payments_df is None or payments_df.empty:
        return {}
    if "student" not in payments_df.columns or "paid_amount" not in payments_df.columns:
        return {}

    payments = payments_df.copy()
    payments["student"] = payments["student"].fillna("").astype(str).str.strip()
    payments = payments[payments["student"].str.len() > 0].copy()
    payments["paid_amount"] = pd.to_numeric(payments["paid_amount"], errors="coerce").fillna(0.0).astype(float) * float(fx_rate or 1.0)
    if "payment_date" in payments.columns:
        payments["payment_date"] = to_dt_naive(payments["payment_date"], utc=True)
        payments = payments.sort_values(["student", "payment_date"])

    baselines: dict[str, float] = {}
    for student, group in payments.groupby("student"):
        recent = pd.to_numeric(group["paid_amount"], errors="coerce").fillna(0.0).tail(3)
        value = float(recent.median()) if len(recent) else 0.0
        if value > 0:
            baselines[str(student)] = value
    return baselines


def _weeks_until_year_end(today: pd.Timestamp) -> float:
    year_end = pd.Timestamp(year=int(today.year), month=12, day=31)
    return max(1.0, float((year_end - today).days) / 7.0)


def _build_action_students(
    forecast_df: pd.DataFrame | None,
    baselines: dict[str, float],
    today: pd.Timestamp,
    limit: int = 6,
) -> list[dict[str, Any]]:
    if forecast_df is None or forecast_df.empty:
        return []
    student_col = _first_existing_col(forecast_df, ["Student", "student"])
    left_col = _first_existing_col(forecast_df, ["Lessons_Left_Units", "lessons_left_units", "units_left"])
    remind_col = _first_existing_col(forecast_df, ["Reminder_Date", "reminder_date"])
    finish_col = _first_existing_col(forecast_df, ["Estimated_Finish_Date", "estimated_finish_date"])
    due_col = _first_existing_col(forecast_df, ["Due_Now", "due_now"])
    if not student_col:
        return []

    rows = forecast_df.copy()
    rows["_student"] = rows[student_col].fillna("").astype(str).str.strip()
    rows["_baseline"] = rows["_student"].map(baselines).fillna(0.0).astype(float)
    rows["_left"] = pd.to_numeric(rows[left_col], errors="coerce").fillna(0.0).astype(float) if left_col else 0.0
    rows["_rem_dt"] = pd.to_datetime(rows[remind_col], errors="coerce") if remind_col else pd.NaT
    rows["_fin_dt"] = pd.to_datetime(rows[finish_col], errors="coerce") if finish_col else pd.NaT
    if due_col:
        rows["_due"] = rows[due_col].astype(bool)
    else:
        rows["_due"] = rows["_rem_dt"].notna() & (rows["_rem_dt"] <= today)

    rows["_soon"] = rows["_fin_dt"].notna() & (rows["_fin_dt"] <= today + pd.Timedelta(days=30))
    rows["_priority"] = rows["_baseline"] + rows["_due"].astype(int) * rows["_baseline"] * 0.45
    rows["_priority"] += rows["_soon"].astype(int) * rows["_baseline"] * 0.25
    rows["_priority"] += (rows["_left"] <= 2).astype(int) * rows["_baseline"] * 0.20
    rows = rows[(rows["_student"].str.len() > 0) & (rows["_baseline"] > 0)].copy()
    rows = rows.sort_values(["_priority", "_baseline"], ascending=False).head(limit)

    out: list[dict[str, Any]] = []
    for _, row in rows.iterrows():
        rem_dt = row.get("_rem_dt")
        fin_dt = row.get("_fin_dt")
        out.append(
            {
                "student": str(row.get("_student") or ""),
                "value": float(row.get("_baseline") or 0.0),
                "units_left": float(row.get("_left") or 0.0),
                "reminder_date": pd.Timestamp(rem_dt).strftime("%Y-%m-%d") if pd.notna(rem_dt) else "",
                "finish_date": pd.Timestamp(fin_dt).strftime("%Y-%m-%d") if pd.notna(fin_dt) else "",
                "due_now": bool(row.get("_due", False)),
            }
        )
    return out


def _goal_probability(projection: float, goal: float, risk_rate: float) -> float:
    if goal <= 0:
        return 0.0
    progress = max(0.0, min(1.25, float(projection) / float(goal)))
    risk_drag = max(0.55, 1.0 - max(0.0, min(0.45, risk_rate)))
    return max(0.0, min(0.99, progress * risk_drag))


def _optimize_actions(
    gap: float,
    baseline_projection: float,
    avg_package_value: float,
    effective_rate: float,
    weeks_left: float,
    renewal_pool: float,
) -> tuple[list[float], list[float]]:
    if gap <= 0:
        return [0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0]

    factors = [
        max(0.0, baseline_projection),
        max(0.0, avg_package_value),
        max(0.0, effective_rate * weeks_left),
        max(0.0, renewal_pool),
    ]
    bounds = [(0.0, 0.18), (0.0, 8.0), (0.0, 10.0), (0.0, 1.0)]
    effort_weights = [0.10, 0.45, 0.30, 0.18]
    x = [0.03, 0.75, 1.0, 0.35]

    def contribution(vals: list[float]) -> float:
        return sum(vals[i] * factors[i] for i in range(4))

    def loss(vals: list[float]) -> float:
        remaining = max(0.0, gap - contribution(vals))
        effort = 0.0
        for i, val in enumerate(vals):
            low, high = bounds[i]
            scale = max(0.0001, high - low)
            effort += effort_weights[i] * (val / scale) ** 2 * max(1.0, gap) ** 2
        return remaining**2 + effort

    for _ in range(220):
        current = loss(x)
        gradient: list[float] = []
        for i, (_, high) in enumerate(bounds):
            step = max(0.0005, high * 0.001)
            trial = x.copy()
            trial[i] = min(high, trial[i] + step)
            gradient.append((loss(trial) - current) / step)

        learning_rate = 0.00000008
        for i, grad in enumerate(gradient):
            low, high = bounds[i]
            x[i] = max(low, min(high, x[i] - learning_rate * grad))

    impacts = [x[i] * factors[i] for i in range(4)]
    return x, impacts


def build_goal_optimization(
    *,
    goal: float,
    baseline_projection: float,
    ytd_income: float,
    expected_future: float,
    effective_rate: float,
    payments_df: pd.DataFrame | None,
    forecast_df: pd.DataFrame | None,
    fx_rate: float = 1.0,
    today: pd.Timestamp | datetime | None = None,
) -> OptimizationResult:
    today_ts = pd.Timestamp(today or pd.Timestamp.today()).normalize()
    goal = max(0.0, _as_float(goal))
    baseline_projection = max(0.0, _as_float(baseline_projection))
    ytd_income = max(0.0, _as_float(ytd_income))
    expected_future = max(0.0, _as_float(expected_future))
    effective_rate = max(0.0, _as_float(effective_rate))
    weeks_left = _weeks_until_year_end(today_ts)

    baselines = _student_baseline_payments(payments_df, fx_rate=fx_rate)
    baseline_values = list(baselines.values())
    avg_package_value = float(pd.Series(baseline_values).median()) if baseline_values else max(0.0, expected_future / 4.0)
    avg_package_value = max(0.0, avg_package_value)

    action_students = _build_action_students(forecast_df, baselines, today_ts)
    renewal_pool = sum(float(item.get("value") or 0.0) for item in action_students)
    if renewal_pool <= 0:
        renewal_pool = expected_future * 0.18

    forecast_len = int(len(forecast_df)) if forecast_df is not None and not forecast_df.empty else 0
    risky = 0
    if forecast_df is not None and not forecast_df.empty:
        left_col = _first_existing_col(forecast_df, ["Lessons_Left_Units", "lessons_left_units", "units_left"])
        due_col = _first_existing_col(forecast_df, ["Due_Now", "due_now"])
        if left_col:
            risky += int((pd.to_numeric(forecast_df[left_col], errors="coerce").fillna(0.0) <= 2).sum())
        if due_col:
            risky += int(forecast_df[due_col].astype(bool).sum())
    risk_rate = min(0.42, 0.08 + (risky / max(1, forecast_len)) * 0.20)

    gap = max(0.0, goal - baseline_projection)
    x, impacts = _optimize_actions(
        gap,
        baseline_projection,
        avg_package_value,
        effective_rate,
        weeks_left,
        renewal_pool,
    )
    optimized_projection = baseline_projection + sum(impacts)
    remaining_gap = max(0.0, goal - optimized_projection)

    scenarios = [
        {"key": "price", "label_key": "optimizer_scenario_price", "impact": impacts[0], "value": x[0]},
        {"key": "growth", "label_key": "optimizer_scenario_growth", "impact": impacts[1], "value": x[1]},
        {"key": "capacity", "label_key": "optimizer_scenario_capacity", "impact": impacts[2], "value": x[2]},
        {"key": "renewal", "label_key": "optimizer_scenario_renewal", "impact": impacts[3], "value": x[3]},
    ]
    scenarios = sorted(scenarios, key=lambda item: float(item.get("impact") or 0.0), reverse=True)

    return OptimizationResult(
        goal=goal,
        baseline_projection=baseline_projection,
        optimized_projection=optimized_projection,
        gap=gap,
        remaining_gap=remaining_gap,
        goal_probability=_goal_probability(baseline_projection, goal, risk_rate),
        optimized_probability=_goal_probability(optimized_projection, goal, max(0.0, risk_rate - x[3] * 0.18)),
        price_pct=x[0],
        new_students=x[1],
        extra_units_week=x[2],
        renewal_focus=x[3],
        price_impact=impacts[0],
        growth_impact=impacts[1],
        capacity_impact=impacts[2],
        renewal_impact=impacts[3],
        avg_package_value=avg_package_value,
        effective_rate=effective_rate,
        weeks_left=weeks_left,
        renewal_pool=renewal_pool,
        risk_rate=risk_rate,
        action_students=action_students,
        scenarios=scenarios,
    )