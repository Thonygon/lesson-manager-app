from __future__ import annotations

from typing import Any

import pandas as pd

from helpers.ui_components import to_dt_naive


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
    norm = {str(col).strip().casefold(): col for col in df.columns}
    for candidate in candidates:
        key = str(candidate).strip().casefold()
        if key in norm:
            return norm[key]
    return None


def _pct_change(current: float, previous: float) -> float | None:
    previous = float(previous or 0.0)
    if previous <= 0:
        return None
    return (float(current or 0.0) - previous) / previous * 100.0


def _payments_with_dates(payments_df: pd.DataFrame | None, fx_rate: float) -> pd.DataFrame:
    if payments_df is None or payments_df.empty:
        return pd.DataFrame(columns=["payment_date", "paid_amount"])
    if "payment_date" not in payments_df.columns or "paid_amount" not in payments_df.columns:
        return pd.DataFrame(columns=["payment_date", "paid_amount"])

    payments = payments_df.copy()
    payments["payment_date"] = to_dt_naive(payments["payment_date"], utc=True)
    payments["paid_amount"] = pd.to_numeric(payments["paid_amount"], errors="coerce").fillna(0.0).astype(float)
    payments["paid_amount"] = payments["paid_amount"] * float(fx_rate or 1.0)
    payments = payments.dropna(subset=["payment_date"])
    return payments


def _same_period_yoy(payments_df: pd.DataFrame | None, today: pd.Timestamp, fx_rate: float) -> dict[str, Any]:
    payments = _payments_with_dates(payments_df, fx_rate)
    if payments.empty:
        return {"current": 0.0, "previous": 0.0, "change_pct": None}

    year = int(today.year)
    previous_year = year - 1
    month = int(today.month)
    day = int(today.day)
    current = payments[
        (payments["payment_date"].dt.year == year)
        & (
            (payments["payment_date"].dt.month < month)
            | ((payments["payment_date"].dt.month == month) & (payments["payment_date"].dt.day <= day))
        )
    ]
    previous = payments[
        (payments["payment_date"].dt.year == previous_year)
        & (
            (payments["payment_date"].dt.month < month)
            | ((payments["payment_date"].dt.month == month) & (payments["payment_date"].dt.day <= day))
        )
    ]

    current_total = float(current["paid_amount"].sum())
    previous_total = float(previous["paid_amount"].sum())
    return {
        "current": current_total,
        "previous": previous_total,
        "change_pct": _pct_change(current_total, previous_total),
    }


def _recent_month_trend(payments_df: pd.DataFrame | None, today: pd.Timestamp, fx_rate: float) -> dict[str, Any]:
    payments = _payments_with_dates(payments_df, fx_rate)
    if payments.empty:
        return {"latest": 0.0, "previous_avg": 0.0, "change_pct": None}

    monthly = payments.copy()
    monthly["month"] = monthly["payment_date"].dt.to_period("M").astype(str)
    grouped = monthly.groupby("month", as_index=False)["paid_amount"].sum().sort_values("month")
    current_month = str(today.to_period("M"))
    complete_months = grouped[grouped["month"] < current_month].tail(4).copy()
    if len(complete_months) < 2:
        return {"latest": 0.0, "previous_avg": 0.0, "change_pct": None}

    latest = float(complete_months.iloc[-1]["paid_amount"])
    previous_avg = float(complete_months.iloc[:-1]["paid_amount"].tail(3).mean())
    return {
        "latest": latest,
        "previous_avg": previous_avg,
        "change_pct": _pct_change(latest, previous_avg),
    }


def _seasonality_signal(payments_df: pd.DataFrame | None, today: pd.Timestamp, fx_rate: float) -> dict[str, Any]:
    payments = _payments_with_dates(payments_df, fx_rate)
    if payments.empty:
        return {"next_month": "", "change_pct": None}

    history = payments[payments["payment_date"].dt.year < int(today.year)].copy()
    if history.empty:
        return {"next_month": "", "change_pct": None}

    next_month_ts = today + pd.DateOffset(months=1)
    next_month = int(next_month_ts.month)
    history["month"] = history["payment_date"].dt.month
    monthly = history.groupby("month", as_index=False)["paid_amount"].sum()
    if monthly.empty or next_month not in monthly["month"].tolist():
        return {"next_month": "", "change_pct": None}

    next_value = float(monthly.loc[monthly["month"] == next_month, "paid_amount"].mean())
    avg_value = float(monthly["paid_amount"].mean())
    return {
        "next_month": next_month_ts.strftime("%B"),
        "change_pct": _pct_change(next_value, avg_value),
    }


def _top_segment(df: pd.DataFrame | None, value_candidates: list[str], label_candidates: list[str]) -> dict[str, Any]:
    if df is None or df.empty:
        return {"name": "", "share": 0.0, "value": 0.0}
    value_col = _first_existing_col(df, value_candidates)
    label_col = _first_existing_col(df, label_candidates)
    if not value_col or not label_col:
        return {"name": "", "share": 0.0, "value": 0.0}

    data = df.copy()
    data[value_col] = pd.to_numeric(data[value_col], errors="coerce").fillna(0.0).astype(float)
    total = float(data[value_col].sum())
    if total <= 0:
        return {"name": "", "share": 0.0, "value": 0.0}
    data = data.sort_values(value_col, ascending=False).reset_index(drop=True)
    top = data.iloc[0]
    return {
        "name": str(top.get(label_col) or "").strip(),
        "share": float(top.get(value_col) or 0.0) / total * 100.0,
        "value": float(top.get(value_col) or 0.0),
    }


def _add_recommendation(
    recommendations: list[dict[str, Any]],
    *,
    kind: str,
    priority: float,
    title_key: str,
    body_key: str,
    params: dict[str, Any] | None = None,
    impact_value: float = 0.0,
    confidence: str = "medium",
) -> None:
    recommendations.append(
        {
            "kind": kind,
            "priority": float(priority),
            "title_key": title_key,
            "body_key": body_key,
            "params": params or {},
            "impact_value": float(impact_value or 0.0),
            "confidence": confidence,
        }
    )


def build_business_recommendations(
    *,
    payments_df: pd.DataFrame | None,
    by_student: pd.DataFrame | None,
    sold_by_subject: pd.DataFrame | None,
    sold_by_modality: pd.DataFrame | None,
    optimizer: Any | None,
    today: pd.Timestamp,
    total_week: float,
    total_month: float,
    top1_name: str | None,
    top1_share: float,
    top3_share: float,
    projected_year: float,
    ytd_cash: float,
    expected_future: float,
    effective_rate: float,
    fx_rate: float = 1.0,
    limit: int = 5,
) -> list[dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []
    today_ts = pd.Timestamp(today).normalize()
    yoy = _same_period_yoy(payments_df, today_ts, fx_rate)
    recent = _recent_month_trend(payments_df, today_ts, fx_rate)
    seasonality = _seasonality_signal(payments_df, today_ts, fx_rate)
    top_subject = _top_segment(sold_by_subject, ["income", "Income", "paid_amount"], ["subject", "Subject", "Language"])
    top_modality = _top_segment(sold_by_modality, ["income", "Income", "paid_amount"], ["modality", "Modality"])

    goal_gap = _as_float(getattr(optimizer, "gap", 0.0)) if optimizer is not None else 0.0
    remaining_gap = _as_float(getattr(optimizer, "remaining_gap", 0.0)) if optimizer is not None else 0.0
    optimized_projection = _as_float(getattr(optimizer, "optimized_projection", 0.0)) if optimizer is not None else 0.0

    action_students = list(getattr(optimizer, "action_students", []) or []) if optimizer is not None else []
    renewal_impact = _as_float(getattr(optimizer, "renewal_impact", 0.0)) if optimizer is not None else 0.0
    if action_students:
        names = ", ".join(str(item.get("student") or "").strip() for item in action_students[:3] if str(item.get("student") or "").strip())
        renewal_value = sum(_as_float(item.get("value")) for item in action_students[:5])
        _add_recommendation(
            recommendations,
            kind="renewal",
            priority=115 + min(30, renewal_value / max(1.0, max(expected_future, renewal_value)) * 30),
            title_key="strategy_title_renewals",
            body_key="strategy_body_renewals",
            params={"students": names, "amount_value": renewal_value},
            impact_value=max(renewal_impact, renewal_value),
            confidence="high",
        )

    if optimizer is not None and _as_float(getattr(optimizer, "price_pct", 0.0)) >= 0.005:
        pct = _as_float(getattr(optimizer, "price_pct", 0.0)) * 100.0
        impact = _as_float(getattr(optimizer, "price_impact", 0.0))
        segment = top_subject.get("name") or top_modality.get("name") or ""
        _add_recommendation(
            recommendations,
            kind="pricing",
            priority=100 + min(25, impact / max(1.0, goal_gap) * 60),
            title_key="strategy_title_pricing",
            body_key="strategy_body_pricing",
            params={"pct": f"{pct:.0f}%", "segment": segment, "impact_value": impact},
            impact_value=impact,
            confidence="medium",
        )

    if optimizer is not None and _as_float(getattr(optimizer, "extra_units_week", 0.0)) >= 0.15:
        units = _as_float(getattr(optimizer, "extra_units_week", 0.0))
        impact = _as_float(getattr(optimizer, "capacity_impact", 0.0))
        _add_recommendation(
            recommendations,
            kind="capacity",
            priority=96 + min(24, impact / max(1.0, goal_gap) * 55),
            title_key="strategy_title_capacity",
            body_key="strategy_body_capacity",
            params={"units": f"{units:.1f}", "impact_value": impact},
            impact_value=impact,
            confidence="medium",
        )

    if optimizer is not None and _as_float(getattr(optimizer, "new_students", 0.0)) >= 0.15:
        new_students = max(1, int(round(_as_float(getattr(optimizer, "new_students", 0.0)))))
        impact = _as_float(getattr(optimizer, "growth_impact", 0.0))
        _add_recommendation(
            recommendations,
            kind="growth",
            priority=92 + min(24, impact / max(1.0, goal_gap) * 55),
            title_key="strategy_title_growth",
            body_key="strategy_body_growth",
            params={"count": new_students, "impact_value": impact},
            impact_value=impact,
            confidence="medium",
        )

    yoy_change = yoy.get("change_pct")
    if yoy_change is not None:
        if yoy_change <= -8:
            _add_recommendation(
                recommendations,
                kind="trend",
                priority=108 + min(20, abs(yoy_change)),
                title_key="strategy_title_yoy_decline",
                body_key="strategy_body_yoy_decline",
                params={"pct": f"{abs(yoy_change):.0f}%", "amount_value": yoy.get("previous", 0.0)},
                impact_value=max(0.0, _as_float(yoy.get("previous")) - _as_float(yoy.get("current"))),
                confidence="high",
            )
        elif yoy_change >= 12:
            _add_recommendation(
                recommendations,
                kind="trend",
                priority=78 + min(18, yoy_change / 2),
                title_key="strategy_title_yoy_growth",
                body_key="strategy_body_yoy_growth",
                params={"pct": f"{yoy_change:.0f}%"},
                confidence="high",
            )

    recent_change = recent.get("change_pct")
    if recent_change is not None and recent_change <= -12:
        _add_recommendation(
            recommendations,
            kind="trend",
            priority=105 + min(20, abs(recent_change)),
            title_key="strategy_title_monthly_drop",
            body_key="strategy_body_monthly_drop",
            params={"pct": f"{abs(recent_change):.0f}%"},
            impact_value=max(0.0, _as_float(recent.get("previous_avg")) - _as_float(recent.get("latest"))),
            confidence="medium",
        )

    if top3_share >= 60:
        _add_recommendation(
            recommendations,
            kind="risk",
            priority=102 + min(22, top3_share - 60),
            title_key="strategy_title_concentration",
            body_key="strategy_body_concentration",
            params={"pct": f"{top3_share:.0f}%", "student": top1_name or ""},
            confidence="high",
        )

    seasonality_change = seasonality.get("change_pct")
    if seasonality_change is not None and seasonality_change <= -10:
        _add_recommendation(
            recommendations,
            kind="seasonality",
            priority=82 + min(16, abs(seasonality_change) / 2),
            title_key="strategy_title_seasonality",
            body_key="strategy_body_seasonality",
            params={"month": seasonality.get("next_month", ""), "pct": f"{abs(seasonality_change):.0f}%"},
            confidence="medium",
        )

    if top_subject.get("name") and top_subject.get("share", 0.0) >= 45:
        _add_recommendation(
            recommendations,
            kind="segment",
            priority=72 + min(15, top_subject.get("share", 0.0) / 5),
            title_key="strategy_title_segment",
            body_key="strategy_body_segment",
            params={"segment": top_subject.get("name"), "pct": f"{top_subject.get('share', 0.0):.0f}%"},
            confidence="medium",
        )

    if total_week <= 0 and total_month > 0:
        _add_recommendation(
            recommendations,
            kind="cashflow",
            priority=90,
            title_key="strategy_title_cashflow",
            body_key="strategy_body_cashflow",
            confidence="medium",
        )

    if optimizer is not None and remaining_gap <= max(1.0, goal_gap * 0.12) and optimized_projection > 0:
        _add_recommendation(
            recommendations,
            kind="protect",
            priority=76,
            title_key="strategy_title_protect_plan",
            body_key="strategy_body_protect_plan",
            params={"projection_value": projected_year, "renewals_value": expected_future},
            confidence="high",
        )

    if not recommendations:
        _add_recommendation(
            recommendations,
            kind="baseline",
            priority=50,
            title_key="strategy_title_baseline",
            body_key="strategy_body_baseline",
            params={"rate_value": effective_rate, "renewals_value": expected_future},
            confidence="medium",
        )

    recommendations = sorted(recommendations, key=lambda item: float(item.get("priority") or 0.0), reverse=True)
    return recommendations[: max(1, int(limit or 5))]
