import streamlit as st
import datetime
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from core.i18n import t
from core.state import get_current_user_id
from core.timezone import now_local, today_local
from core.navigation import go_to, page_header
from core.database import load_table, load_students
import matplotlib.pyplot as plt
from helpers.analytics import build_income_analytics, money_fmt
from helpers.ui_components import ts_today_naive, to_dt_naive, pretty_df, translate_df_headers, chart_series
from helpers.language import translate_language_value, translate_modality_value
from helpers.dashboard import rebuild_dashboard
from helpers.forecast import build_forecast_table
from helpers.year_goals import get_year_goal, set_year_goal
from helpers.goals import YEAR_GOAL_SCOPE
from helpers.currency import CURRENCIES, INFLATION_COUNTRIES, get_exchange_rate, fetch_cpi_data, inflate, get_preferred_currency

# 12.6) PAGE: ANALYTICS
# =========================
def render_analytics():
    page_header(t("analytics"))
    st.caption(t("view_your_income_and_business_indicators"))

    kpis, income_table, by_student, sold_by_subject, sold_by_modality = build_income_analytics(group="monthly")
    today = ts_today_naive()

    # ── Currency & inflation settings (persisted in session_state) ──
    _pref_cur = get_preferred_currency()
    base_cur = st.session_state.get("analytics_base_currency", _pref_cur)
    display_cur = st.session_state.get("analytics_display_currency", _pref_cur)
    inflation_on = st.session_state.get("analytics_inflation_on", False)
    inflation_country = st.session_state.get("analytics_inflation_country", "Turkey")

    fx_rate = get_exchange_rate(base_cur, display_cur) if base_cur != display_cur else 1.0
    cpi_data = fetch_cpi_data(INFLATION_COUNTRIES.get(inflation_country, "TUR")) if inflation_on else {}
    _sym = CURRENCIES.get(display_cur, {}).get("symbol", "")

    def cfmt(x):
        """money_fmt with the selected currency symbol."""
        return money_fmt(x, symbol=_sym)

    def _apply_fx(df):
        """Apply fx_rate to income columns of a DataFrame (in-place safe on copies)."""
        if df is None or df.empty or fx_rate == 1.0:
            return df
        d = df.copy()
        for c in ("income", "Income", "paid_amount", "total_paid", "Total_Paid"):
            if c in d.columns:
                d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0.0) * fx_rate
        return d

    # Apply fx conversion to loaded data
    if fx_rate != 1.0:
        for k in ("income_all_time", "income_this_year", "income_this_month", "income_this_week"):
            kpis[k] = float(kpis.get(k, 0.0) or 0.0) * fx_rate
        income_table = _apply_fx(income_table)
        by_student = _apply_fx(by_student)
        sold_by_subject = _apply_fx(sold_by_subject)
        sold_by_modality = _apply_fx(sold_by_modality)

    # --- Income section ---
    st.markdown(f"### {t('income')}")

    tab_all, tab_year, tab_month, tab_week = st.tabs(
        [
            f"{t('all_time_income')} · {cfmt(kpis.get('income_all_time', 0.0))}",
            f"{t('yearly_income')} · {cfmt(kpis.get('income_this_year', 0.0))}",
            f"{t('monthly_income')} · {cfmt(kpis.get('income_this_month', 0.0))}",
            f"{t('weekly_income')} · {cfmt(kpis.get('income_this_week', 0.0))}",
        ]
    )

    # ---------------------------------------
    # Chart helpers
    # ---------------------------------------
    def _monthly_line_chart_plotly(df: pd.DataFrame, title: str):

        if df is None or df.empty or "Key" not in df.columns:
            st.info(t("no_data"))
            return

        tmp = df.copy()
        ycol = "income" if "income" in tmp.columns else ("Income" if "Income" in tmp.columns else None)
        if ycol is None:
            st.info(t("no_data"))
            return

        tmp["date"] = pd.to_datetime(tmp["Key"].astype(str).str[:7] + "-01", errors="coerce")
        tmp = tmp.dropna(subset=["date"])
        if tmp.empty:
            st.info(t("no_data"))
            return

        tmp["income_val"] = pd.to_numeric(tmp[ycol], errors="coerce").fillna(0.0).astype(float)
        tmp = tmp.sort_values("date")

        fig = px.line(
            tmp,
            x="date",
            y="income_val",
            title=title,
            markers=True,
            labels={"date": t("month"), "income_val": t("income")},
        )

        fig.update_layout(
            margin=dict(l=10, r=10, t=48, b=10),
            height=360 if st.session_state.get("compact_mode", False) else 440,
            xaxis=dict(
                rangeslider=dict(visible=True),
                type="date",
                tickformat="%b %Y",
            ),
        )

        st.plotly_chart(fig, use_container_width=True)

    def _bar_chart_with_highlight(labels, values, highlight_label, base_color, highlight_color, title, xlabel, ylabel):

        colors = [highlight_color if l == highlight_label else base_color for l in labels]
        fig, ax = plt.subplots()
        ax.bar(labels, values, color=colors)
        ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)

        if len(labels) > 12:
            step = max(1, len(labels) // 8)
            keep = set(range(0, len(labels), step))
            ax.set_xticks([i for i in range(len(labels)) if i in keep])
            ax.set_xticklabels([labels[i] for i in range(len(labels)) if i in keep], rotation=45, ha="right")
        else:
            ax.tick_params(axis="x", labelrotation=45)

        ax.margins(x=0.01)
        st.pyplot(fig, clear_figure=True)

    BLUE = "#2563EB"
    GREEN = "#10B981"
    YELLOW = "#F59E0B"
    PURPLE = "#8B5CF6"

    with tab_all:
        st.subheader(t("all_time_monthly_income"))
        _monthly_line_chart_plotly(income_table, t("all_time_monthly_income"))

    with tab_year:
        st.subheader(t("yearly_income"))
        _, yearly_table, *_ = build_income_analytics(group="yearly")
        yearly_table = _apply_fx(yearly_table)

        if yearly_table is None or yearly_table.empty:
            st.info(t("no_data"))
        else:
            yt = yearly_table.copy()
            yt["Year"] = yt["Key"].astype(str).str[:4]

            if "income" in yt.columns:
                yt["Income"] = pd.to_numeric(yt["income"], errors="coerce").fillna(0.0).astype(float)
            else:
                yt["Income"] = pd.to_numeric(yt.get("Income"), errors="coerce").fillna(0.0).astype(float)

            yt = yt.sort_values("Year")

            current_year = str(today.year)
            years = yt["Year"].tolist()
            incomes = yt["Income"].tolist()

            _bar_chart_with_highlight(
                labels=years,
                values=incomes,
                highlight_label=current_year,
                base_color=BLUE,
                highlight_color=GREEN,
                title=t("yearly_totals"),
                xlabel=t("year"),
                ylabel=t("income"),
            )

    with tab_month:
        st.subheader(t("monthly_income"))

        if income_table is None or income_table.empty:
            st.info(t("no_data"))
        else:
            year_options = sorted(
                income_table["Key"].astype(str).str[:4].dropna().unique().tolist(),
                reverse=True,
            )
            current_year = str(today.year)
            default_idx = year_options.index(current_year) if current_year in year_options else 0

            selected_year = st.selectbox(
                t("select_year"),
                year_options,
                index=default_idx,
                key="analytics_year_pick",
            )

            monthly = income_table[income_table["Key"].astype(str).str.startswith(selected_year)].copy()

            if monthly.empty:
                st.info(t("no_data"))
            else:
                monthly["MonthKey"] = monthly["Key"].astype(str).str[:7]

                if "income" in monthly.columns:
                    monthly["Income"] = pd.to_numeric(monthly["income"], errors="coerce").fillna(0.0).astype(float)
                else:
                    monthly["Income"] = pd.to_numeric(monthly.get("Income"), errors="coerce").fillna(0.0).astype(float)

                monthly = monthly.sort_values("MonthKey")

                labels = monthly["MonthKey"].tolist()
                values = monthly["Income"].tolist()

                highlight_month = today.strftime("%Y-%m") if selected_year == str(today.year) else "__none__"

                _bar_chart_with_highlight(
                    labels=labels,
                    values=values,
                    highlight_label=highlight_month,
                    base_color=BLUE,
                    highlight_color=YELLOW,
                    title=f"{t('monthly_income')} ({selected_year})",
                    xlabel=t("month"),
                    ylabel=t("income"),
                )

    with tab_week:
        st.subheader(t("weekly_income"))

        payments_week = load_table("payments")
        if payments_week is None or payments_week.empty:
            st.info(t("no_data"))
        else:
            pw = payments_week.copy()

            if "payment_date" not in pw.columns:
                pw["payment_date"] = None
            if "paid_amount" not in pw.columns:
                pw["paid_amount"] = 0.0

            pw["payment_date"] = to_dt_naive(pw["payment_date"], utc=True)
            pw["paid_amount"] = pd.to_numeric(pw["paid_amount"], errors="coerce").fillna(0.0).astype(float) * fx_rate
            pw = pw.dropna(subset=["payment_date"])

            week_start = today - pd.Timedelta(days=int(today.weekday()))
            week_end = week_start + pd.Timedelta(days=6)

            pw = pw[(pw["payment_date"] >= week_start) & (pw["payment_date"] <= week_end)].copy()

            if pw.empty:
                st.info(t("no_data"))
            else:
                pw["Day"] = pw["payment_date"].dt.strftime("%a %d")
                weekly = pw.groupby("Day", as_index=False)["paid_amount"].sum().rename(columns={"paid_amount": "Income"})

                _bar_chart_with_highlight(
                    labels=weekly["Day"].tolist(),
                    values=weekly["Income"].tolist(),
                    highlight_label=today.strftime("%a %d"),
                    base_color=BLUE,
                    highlight_color=PURPLE,
                    title=t("last_7_days"),
                    xlabel=t("day"),
                    ylabel=t("income"),
                )
    # ============================================
    # INSIGHTS-FIRST SECTION
    # ============================================
    # ---------- safe helpers ----------
    def _first_existing_col(df: pd.DataFrame, candidates):
        if df is None or df.empty:
            return None
        norm = {str(c).strip().casefold(): c for c in df.columns}
        for cand in candidates:
            k = str(cand).strip().casefold()
            if k in norm:
                return norm[k]
        return None

    def _safe_sum(df: pd.DataFrame, col: str) -> float:
        if df is None or df.empty or col is None or col not in df.columns:
            return 0.0
        return float(pd.to_numeric(df[col], errors="coerce").fillna(0.0).sum())

    def _pct(a: float, b: float) -> float:
        b = float(b or 0.0)
        if b == 0:
            return 0.0
        return float(a) / b * 100.0

    def _fmt_pct(x: float) -> str:
        try:
            return f"{float(x):.1f}%"
        except Exception:
            return "0.0%"

    def _callout(title: str, body: str):
        st.markdown(
            f"""
            <div style="padding:10px 12px;border:1px solid rgba(15,23,42,.10);
                        background:rgba(37,99,235,.04);border-radius:12px;">
              <div style="font-weight:900;color:#0f172a;margin-bottom:4px;">{title}</div>
              <div style="font-weight:600;color:#0f172a;opacity:.95;">{body}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    def _show_raw_toggle(df: pd.DataFrame, toggle_key: str):
        show_raw = st.toggle(t("show_raw_data"), value=False, key=toggle_key)
        if show_raw:
            st.dataframe(
                translate_df_headers(pretty_df(df)),
                use_container_width=True,
                hide_index=True,
            )

    # ---------- NEW: YTD + renewal pipeline projection (no more this_month*12) ----------
    def _ytd_income(payments_df: pd.DataFrame, year: int) -> float:
        if payments_df is None or payments_df.empty:
            return 0.0
        p = payments_df.copy()
        if "payment_date" not in p.columns:
            return 0.0
        if "paid_amount" not in p.columns:
            return 0.0
        p["payment_date"] = to_dt_naive(p["payment_date"], utc=True)
        p["paid_amount"] = pd.to_numeric(p["paid_amount"], errors="coerce").fillna(0.0).astype(float)
        p = p.dropna(subset=["payment_date"])
        p = p[p["payment_date"].dt.year == int(year)]
        return float(p["paid_amount"].sum())

    def _student_baseline_payment(payments_df: pd.DataFrame, student: str) -> float:
        """
        Student baseline renewal value = median of last up to 3 payments (safer than mean).
        """
        if payments_df is None or payments_df.empty:
            return 0.0
        if "student" not in payments_df.columns or "paid_amount" not in payments_df.columns:
            return 0.0

        p = payments_df.copy()
        p["student"] = p["student"].fillna("").astype(str).str.strip()
        p = p[p["student"] == str(student).strip()]
        if p.empty:
            return 0.0

        if "payment_date" in p.columns:
            p["payment_date"] = to_dt_naive(p["payment_date"], utc=True)
            p = p.dropna(subset=["payment_date"]).sort_values("payment_date")
        p["paid_amount"] = pd.to_numeric(p["paid_amount"], errors="coerce").fillna(0.0).astype(float)

        tail = p["paid_amount"].tail(3)
        if len(tail) == 0:
            return 0.0
        return float(tail.median())

    def _estimate_typical_units_from_dashboard(student_name: str) -> float:
        """
        If dashboard has a total-paid-units column, we use it as package-size proxy.
        Otherwise returns 0 (caller will fallback).
        """
        try:
            dash = rebuild_dashboard(active_window_days=183, expiry_days=365, grace_days=0)
            if dash is None or dash.empty:
                return 0.0
            if "Student" not in dash.columns:
                return 0.0
            d = dash.copy()
            d["Student"] = d["Student"].fillna("").astype(str).str.strip()
            row = d[d["Student"] == str(student_name).strip()]
            if row.empty:
                return 0.0

            # Common candidates across your app versions:
            cand = _first_existing_col(row, ["Lessons_Paid_Total", "Lessons_Paid", "Paid_Units", "Package_Units"])
            if not cand:
                return 0.0
            v = row.iloc[0].get(cand, 0)
            v = float(pd.to_numeric(v, errors="coerce") or 0.0)
            return max(0.0, v)
        except Exception:
            return 0.0

    def estimate_year_projection_current_students(
        today_ts: pd.Timestamp,
        forecast_df: pd.DataFrame,
        payments_df: pd.DataFrame,
    ) -> dict:
        """
        Base projection (student-based):
          projected = YTD cash + expected renewals (prob=1.0 baseline, refined later)

        Renewals are simulated using:
          - student's baseline payment value (median last 3 payments)
          - next renewal = finish date
          - renewal cycle length = max(typical_units, 10) / units_per_day
        """
        year = int(today_ts.year)
        year_end = pd.Timestamp(year=year, month=12, day=31)

        ytd = _ytd_income(payments_df, year=year)
        if forecast_df is None or forecast_df.empty:
            return {"ytd": ytd, "expected_future": 0.0, "projected": ytd, "counted": 0, "missing_baseline": 0}

        # identify cols (from Section 12 output)
        student_col = _first_existing_col(forecast_df, ["Student", "student"])
        upd_col = _first_existing_col(forecast_df, ["Units_Per_Day", "units_per_day"])
        left_col = _first_existing_col(forecast_df, ["Lessons_Left_Units", "lessons_left_units"])
        finish_col = _first_existing_col(forecast_df, ["Estimated_Finish_Date", "estimated_finish_date"])

        if not student_col or not upd_col:
            return {"ytd": ytd, "expected_future": 0.0, "projected": ytd, "counted": 0, "missing_baseline": 0}

        f = forecast_df.copy()
        f[student_col] = f[student_col].fillna("").astype(str).str.strip()
        f[upd_col] = pd.to_numeric(f[upd_col], errors="coerce").fillna(0.0).astype(float)
        f.loc[f[upd_col] <= 0, upd_col] = 0.10

        if left_col and left_col in f.columns:
            f[left_col] = pd.to_numeric(f[left_col], errors="coerce").fillna(0.0).astype(float)
        else:
            f[left_col] = 0.0

        f["_finish_dt"] = pd.to_datetime(f.get(finish_col), errors="coerce") if finish_col else pd.NaT

        expected_future = 0.0
        counted = 0
        missing = 0

        for _, r in f.iterrows():
            s = str(r.get(student_col, "")).strip()
            if not s:
                continue

            baseline_value = _student_baseline_payment(payments_df, s)
            if baseline_value <= 0:
                missing += 1
                continue

            units_per_day = float(r.get(upd_col, 0.10) or 0.10)
            finish_dt = r.get("_finish_dt", pd.NaT)
            if pd.isna(finish_dt):
                continue

            # typical units: prefer dashboard (if available), else fallback to current remaining, clamped
            typical_units = _estimate_typical_units_from_dashboard(s)
            if typical_units <= 0:
                typical_units = float(r.get(left_col, 0.0) or 0.0)
            typical_units = max(10.0, typical_units)

            cycle_days = max(7, int(round(typical_units / max(0.01, units_per_day))))
            next_dt = pd.Timestamp(finish_dt)

            # simulate renewals until year end
            while next_dt <= year_end:
                expected_future += baseline_value
                next_dt = next_dt + pd.Timedelta(days=cycle_days)

            counted += 1

        projected = ytd + expected_future
        return {"ytd": float(ytd), "expected_future": float(expected_future), "projected": float(projected), "counted": int(counted), "missing_baseline": int(missing)}

    # ---------- metrics (capsules already show totals; summary will show averages) ----------
    total_all_time = float(kpis.get("income_all_time", 0.0) or 0.0)
    total_month = float(kpis.get("income_this_month", 0.0) or 0.0)
    total_week = float(kpis.get("income_this_week", 0.0) or 0.0)

    # Effective rate (income per lesson unit) — uses all-time totals
    classes_for_rate = load_table("classes")
    total_units = 0.0
    if classes_for_rate is not None and not classes_for_rate.empty and "number_of_lesson" in classes_for_rate.columns:
        total_units = float(pd.to_numeric(classes_for_rate["number_of_lesson"], errors="coerce").fillna(0).sum())
    eff_rate = (total_all_time / total_units) if (total_units and total_all_time) else 0.0

    # --- Average monthly income (last 12 months) ---
    avg_monthly_12m = 0.0
    try:
        if income_table is not None and not income_table.empty and "Key" in income_table.columns:
            tmpm = income_table.copy()
            ycol_m = "income" if "income" in tmpm.columns else ("Income" if "Income" in tmpm.columns else None)
            if ycol_m:
                tmpm["date"] = pd.to_datetime(tmpm["Key"].astype(str).str[:7] + "-01", errors="coerce")
                tmpm = tmpm.dropna(subset=["date"])
                tmpm["val"] = pd.to_numeric(tmpm[ycol_m], errors="coerce").fillna(0.0).astype(float)
                tmpm = tmpm.sort_values("date")
                cutoff = today - pd.Timedelta(days=365)
                last12 = tmpm[tmpm["date"] >= cutoff]
                if len(last12) >= 3:
                    avg_monthly_12m = float(last12["val"].mean())
                elif len(tmpm) >= 1:
                    avg_monthly_12m = float(tmpm["val"].mean())
    except Exception:
        avg_monthly_12m = 0.0

    # --- Average yearly income (average across available years) ---
    avg_yearly = 0.0
    try:
        _, yearly_table_avg, *_ = build_income_analytics(group="yearly")
        yearly_table_avg = _apply_fx(yearly_table_avg)
        if yearly_table_avg is not None and not yearly_table_avg.empty and "Key" in yearly_table_avg.columns:
            ytmp = yearly_table_avg.copy()
            ycol_y = "income" if "income" in ytmp.columns else ("Income" if "Income" in ytmp.columns else None)
            if ycol_y:
                ytmp["val"] = pd.to_numeric(ytmp[ycol_y], errors="coerce").fillna(0.0).astype(float)
                if inflation_on and cpi_data:
                    ytmp["year_int"] = ytmp["Key"].astype(str).str[:4].astype(int)
                    ytmp["val"] = ytmp.apply(
                        lambda r: inflate(r["val"], int(r["year_int"]), int(today.year), cpi_data), axis=1
                    )
                if len(ytmp) >= 1:
                    avg_yearly = float(ytmp["val"].mean())
    except Exception:
        avg_yearly = 0.0

    # Inflation-adjusted avg monthly (if inflation is on, adjust each month by its year)
    if inflation_on and cpi_data and avg_monthly_12m > 0:
        try:
            if income_table is not None and not income_table.empty and "Key" in income_table.columns:
                tmpm2 = income_table.copy()
                mc2 = "income" if "income" in tmpm2.columns else ("Income" if "Income" in tmpm2.columns else None)
                if mc2:
                    tmpm2["date"] = pd.to_datetime(tmpm2["Key"].astype(str).str[:7] + "-01", errors="coerce")
                    tmpm2 = tmpm2.dropna(subset=["date"])
                    tmpm2["val"] = pd.to_numeric(tmpm2[mc2], errors="coerce").fillna(0.0).astype(float)
                    tmpm2["year_int"] = tmpm2["date"].dt.year
                    tmpm2["val"] = tmpm2.apply(
                        lambda r: inflate(r["val"], int(r["year_int"]), int(today.year), cpi_data), axis=1
                    )
                    tmpm2 = tmpm2.sort_values("date")
                    cutoff2 = today - pd.Timedelta(days=365)
                    last12_2 = tmpm2[tmpm2["date"] >= cutoff2]
                    if len(last12_2) >= 3:
                        avg_monthly_12m = float(last12_2["val"].mean())
                    elif len(tmpm2) >= 1:
                        avg_monthly_12m = float(tmpm2["val"].mean())
        except Exception:
            pass

    # Income concentration (top student / top 3)
    top_income_col = _first_existing_col(by_student, ["total_paid", "Total_Paid", "income", "paid_amount", "Income"])
    student_col = _first_existing_col(by_student, ["student", "Student"])
    lastpay_col = _first_existing_col(by_student, ["last_payment", "Last_Payment"])

    by_student_total = _safe_sum(by_student, top_income_col)
    top1_share = 0.0
    top3_share = 0.0
    top1_name = None

    if by_student is not None and not by_student.empty and top_income_col and student_col:
        bs = by_student.copy()
        bs[top_income_col] = pd.to_numeric(bs[top_income_col], errors="coerce").fillna(0.0).astype(float)
        bs = bs.sort_values(top_income_col, ascending=False).reset_index(drop=True)

        if len(bs) >= 1:
            top1_name = str(bs.loc[0, student_col])
            top1_share = _pct(float(bs.loc[0, top_income_col]), float(by_student_total))
        if len(bs) >= 3:
            top3_share = _pct(float(bs.loc[:2, top_income_col].sum()), float(by_student_total))
        elif len(bs) >= 1:
            top3_share = _pct(float(bs.loc[:, top_income_col].sum()), float(by_student_total))

    # ---------- NEW: compute projection inputs once (used in Summary + Goal) ----------
    payments_all = load_table("payments")
    forecast_for_projection = build_forecast_table(payment_buffer_days=0)

    proj = estimate_year_projection_current_students(
        today_ts=today,
        forecast_df=forecast_for_projection,
        payments_df=payments_all,
    )
    projected_year = float(proj.get("projected", 0.0) or 0.0) * fx_rate
    ytd_cash = float(proj.get("ytd", 0.0) or 0.0) * fx_rate
    expected_future = float(proj.get("expected_future", 0.0) or 0.0) * fx_rate

    # ── Insights & Actions ──────────────────────────────────────
    st.markdown(f"### {t('insights_and_actions')}")

    # Display-settings expander (currency + inflation)
    with st.expander(f"⚙️ {t('display_settings')}"):
        ds1, ds2 = st.columns(2)
        _cur_options = list(CURRENCIES.keys())
        with ds1:
            st.selectbox(
                t("base_currency"),
                _cur_options,
                index=_cur_options.index(base_cur) if base_cur in _cur_options else 0,
                key="analytics_base_currency",
                format_func=lambda c: f"{CURRENCIES[c]['symbol']}  {c} — {CURRENCIES[c]['name']}",
            )
        with ds2:
            st.selectbox(
                t("display_currency"),
                _cur_options,
                index=_cur_options.index(display_cur) if display_cur in _cur_options else 0,
                key="analytics_display_currency",
                format_func=lambda c: f"{CURRENCIES[c]['symbol']}  {c} — {CURRENCIES[c]['name']}",
            )
        inf1, inf2 = st.columns(2)
        with inf1:
            st.toggle(t("adjust_inflation"), key="analytics_inflation_on")
        with inf2:
            if st.session_state.get("analytics_inflation_on", False):
                _country_options = sorted(INFLATION_COUNTRIES.keys())
                st.selectbox(
                    t("inflation_country"),
                    _country_options,
                    index=_country_options.index(inflation_country) if inflation_country in _country_options else 0,
                    key="analytics_inflation_country",
                )
        # Status captions
        _captions = []
        if fx_rate != 1.0:
            _captions.append(f"{t('fx_rate_caption')}: 1 {base_cur} = {fx_rate:.4f} {display_cur}")
        if inflation_on:
            if cpi_data:
                _latest_yr = max(cpi_data.keys())
                _captions.append(f"{t('inflation_data_up_to')} {_latest_yr}")
            else:
                _captions.append(t("cpi_no_data"))
        if _captions:
            st.caption(" · ".join(_captions))

    tab_summary, tab_rev, tab_delivery, tab_risk = st.tabs(
        [t("summary"), t("revenue_drivers"), t("teaching_activity"), t("risk_and_forecast")]
    )

    # ======================
    # TAB 1 — Summary (per-year or all-time)
    # ======================
    with tab_summary:
        # Year selector
        _available_years = []
        if income_table is not None and not income_table.empty and "Key" in income_table.columns:
            _available_years = sorted(
                income_table["Key"].astype(str).str[:4].dropna().unique().tolist(),
                reverse=True,
            )
        _year_opts = [t("all_time")] + _available_years
        summary_year = st.selectbox(
            t("select_year"),
            _year_opts,
            key="summary_year_select",
        )

        _is_all_time = (summary_year == t("all_time"))
        _sel_year = int(summary_year) if not _is_all_time else None
        _current_year = int(today.year)

        if _is_all_time:
            # ── All-time metrics ──
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric(t("avg_yearly_income"), cfmt(avg_yearly))
            with c2:
                st.metric(t("avg_monthly_income"), cfmt(avg_monthly_12m))
            with c3:
                st.metric(t("run_rate_annual"), cfmt(projected_year))
            with c4:
                st.metric(t("effective_rate_unit"), cfmt(eff_rate))
            st.caption(
                f"{t('ytd_income')}: {cfmt(ytd_cash)} — "
                f"{t('expected_renewals')}: {cfmt(expected_future)}"
            )
            if inflation_on and cpi_data:
                st.caption(f"📊 {t('values_adjusted_to')} {_current_year}")
        else:
            # ── Per-year metrics ──
            _yr_income = 0.0
            _yr_avg_monthly = 0.0
            _yr_eff_rate = 0.0
            _yr_total_lessons = 0.0

            # Total income for the selected year
            _pay_yr = load_table("payments")
            if _pay_yr is not None and not _pay_yr.empty:
                _pyc = _pay_yr.copy()
                _pyc["payment_date"] = to_dt_naive(_pyc["payment_date"], utc=True)
                _pyc["paid_amount"] = pd.to_numeric(_pyc.get("paid_amount"), errors="coerce").fillna(0.0) * fx_rate
                _pyc = _pyc.dropna(subset=["payment_date"])
                _pyc = _pyc[_pyc["payment_date"].dt.year == _sel_year]
                _yr_income = float(_pyc["paid_amount"].sum())

            # Avg monthly for the year
            if income_table is not None and not income_table.empty:
                _ym = income_table[income_table["Key"].astype(str).str.startswith(str(_sel_year))].copy()
                _mc = "income" if "income" in _ym.columns else ("Income" if "Income" in _ym.columns else None)
                if _mc and not _ym.empty:
                    _yr_avg_monthly = float(pd.to_numeric(_ym[_mc], errors="coerce").fillna(0.0).mean())

            # Lessons & effective rate for the year
            _cls_yr = load_table("classes")
            if _cls_yr is not None and not _cls_yr.empty:
                _cyc = _cls_yr.copy()
                if "lesson_date" in _cyc.columns and "number_of_lesson" in _cyc.columns:
                    _cyc["lesson_date"] = to_dt_naive(_cyc["lesson_date"], utc=True)
                    _cyc["number_of_lesson"] = pd.to_numeric(_cyc["number_of_lesson"], errors="coerce").fillna(0)
                    _cyc = _cyc.dropna(subset=["lesson_date"])
                    _cyc = _cyc[_cyc["lesson_date"].dt.year == _sel_year]
                    _yr_total_lessons = float(_cyc["number_of_lesson"].sum())
                    _yr_eff_rate = (_yr_income / _yr_total_lessons) if _yr_total_lessons > 0 else 0.0

            # Apply inflation for past years
            if inflation_on and cpi_data and _sel_year != _current_year:
                _c_from = cpi_data.get(_sel_year)
                _c_to = cpi_data.get(_current_year)
                if _c_from and _c_to and _c_from > 0:
                    _infl = _c_to / _c_from
                    _yr_income *= _infl
                    _yr_avg_monthly *= _infl
                    _yr_eff_rate *= _infl

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric(t("total_year_income"), cfmt(_yr_income))
            with c2:
                st.metric(t("avg_monthly_income"), cfmt(_yr_avg_monthly))
            with c3:
                if _sel_year == _current_year:
                    st.metric(t("run_rate_annual"), cfmt(projected_year))
                else:
                    st.metric(t("total_lessons"), f"{int(_yr_total_lessons)}")
            with c4:
                st.metric(t("effective_rate_unit"), cfmt(_yr_eff_rate))

            if _sel_year == _current_year:
                st.caption(
                    f"{t('ytd_income')}: {cfmt(ytd_cash)} — "
                    f"{t('expected_renewals')}: {cfmt(expected_future)}"
                )
            if inflation_on and cpi_data and _sel_year != _current_year:
                st.caption(f"📊 {t('values_adjusted_to')} {_current_year}")

        # -------------------------
        # Yearly goal (persistent across devices)
        # -------------------------
        if _is_all_time or _sel_year == _current_year:
            st.markdown(f"#### {t('goal')}")
            scope = YEAR_GOAL_SCOPE
            current_year = _current_year

            goal_state_key = f"year_goal_{current_year}_{scope}"
            goal_loaded_key = f"{current_year}_{scope}"

            if "year_goal_loaded" not in st.session_state:
                st.session_state.year_goal_loaded = {}

            if goal_loaded_key not in st.session_state.year_goal_loaded:
                st.session_state[goal_state_key] = get_year_goal(current_year, scope=scope, default=0.0)
                st.session_state.year_goal_loaded[goal_loaded_key] = True

            gcol1, gcol2 = st.columns([2, 1])
            with gcol1:
                new_goal = st.number_input(
                    f"{t('yearly_income_goal')} ({current_year})",
                    min_value=0.0,
                    value=float(st.session_state.get(goal_state_key, 0.0) or 0.0),
                    step=1000.0,
                    key=f"year_goal_input_{current_year}_{scope}",
                )
            with gcol2:
                if st.button("Save", key=f"save_goal_{current_year}_{scope}", use_container_width=True):
                    ok = set_year_goal(current_year, float(new_goal), scope=scope)
                    if ok:
                        st.session_state[goal_state_key] = float(new_goal)
                        try:
                            st.cache_data.clear()
                        except Exception:
                            pass

                        st.toast("Saved", icon="✅")
                        st.rerun()
                    else:
                        st.toast("Could not save goal", icon="⚠️")

            goal_val = float(st.session_state.get(goal_state_key, 0.0) or 0.0)
            if goal_val > 0:
                prog = max(0.0, min(1.0, ytd_cash / goal_val))
                st.progress(prog)
                st.write(f"**{prog*100.0:.1f}%** — {t('goal_progress')}")

                remaining = max(0.0, goal_val - ytd_cash)
                months_left = max(0, 12 - int(today.month))
                avg_needed = (remaining / months_left) if months_left > 0 else remaining

                g1, g2, g3 = st.columns(3)
                with g1:
                    st.metric(t("ytd_income"), cfmt(ytd_cash))
                with g2:
                    st.metric(t("remaining_to_goal"), cfmt(remaining))
                with g3:
                    st.metric(t("avg_needed_month"), cfmt(avg_needed))
            else:
                st.info("Set a yearly goal to see your progress bar.")
        # -------------------------
        # Summary callout + actions (unchanged)
        # -------------------------
        if top1_name:
            _callout(
                t("important"),
                t("takeaway_concentration", p1=_fmt_pct(top1_share), p3=_fmt_pct(top3_share)),
            )
        else:
            _callout(
                t("what_this_means"),
                "This section explains your teaching business in simple numbers: income, stability, and what to do next.",
            )

        st.markdown(f"#### {t('next_steps')}")
        actions = []
        if total_week == 0 and total_month > 0:
            actions.append(t("action_check_week"))
        if top3_share >= 60:
            actions.append(t("action_reduce_risk"))
        if not actions:
            actions = [t("action_review_top"), t("action_compare_mix"), t("action_check_forecast")]

        for a in actions[:5]:
            st.write(f"• {a}")

    # ======================
    # TAB 2 — Revenue drivers
    # ======================
    with tab_rev:
        # (UNCHANGED from your current code)
        st.markdown(f"#### {t('most_profitable_students')}")
        if by_student is None or by_student.empty or not top_income_col or not student_col:
            st.info(t("no_data"))
        else:
            bs = by_student.copy()
            bs[top_income_col] = pd.to_numeric(bs[top_income_col], errors="coerce").fillna(0.0).astype(float)
            bs = bs.sort_values(top_income_col, ascending=False).reset_index(drop=True)
            top = bs.head(10).copy()

            top_total = float(top[top_income_col].sum())
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric(t("top10_revenue"), cfmt(top_total))
            with c2:
                st.metric(t("top1_share"), _fmt_pct(top1_share))
            with c3:
                st.metric(t("top3_share"), _fmt_pct(top3_share))

            if top1_name:
                _callout(t("important"), t("takeaway_profitable", name=top1_name))

            ser = chart_series(top.rename(columns={student_col: "student"}), "student", top_income_col, "student", "income")
            if ser is None:
                st.info(t("no_data"))
            else:
                st.bar_chart(ser)

            st.markdown(f"##### {t('top5_quick_view')}")
            top5 = top.head(5).copy()
            cols = st.columns(5)
            for i in range(min(5, len(top5))):
                name = str(top5.loc[i, student_col])
                val = float(top5.loc[i, top_income_col])
                share = _fmt_pct(_pct(val, by_student_total))
                with cols[i]:
                    st.metric(name, cfmt(val), share)

            top_show = top.copy()
            top_show[top_income_col] = top_show[top_income_col].apply(cfmt)
            if lastpay_col and lastpay_col in top_show.columns:
                top_show[lastpay_col] = pd.to_datetime(top_show[lastpay_col], errors="coerce").dt.strftime("%Y-%m-%d")
            _show_raw_toggle(top_show, "raw_top_students")

        st.markdown(f"#### {t('packages_by_subject')}")
        if sold_by_subject is None or sold_by_subject.empty:
            st.info(t("no_data"))
        else:
            lang_df = sold_by_subject.copy()
            lang_col = _first_existing_col(lang_df, ["subject", "languages", "Language"])
            inc_col = _first_existing_col(lang_df, ["income", "Income", "paid_amount", "total_paid"])
            if not lang_col or not inc_col:
                st.info(t("no_data"))
            else:
                lang_df[inc_col] = pd.to_numeric(lang_df[inc_col], errors="coerce").fillna(0.0).astype(float)
                lang_df = lang_df.sort_values(inc_col, ascending=False).reset_index(drop=True)

                total_lang = float(lang_df[inc_col].sum())
                top_lang = str(lang_df.loc[0, lang_col]) if len(lang_df) else ""
                top_lang_share = _fmt_pct(_pct(float(lang_df.loc[0, inc_col]) if len(lang_df) else 0.0, total_lang))

                c1, c2 = st.columns(2)
                with c1:
                    st.metric(t("total_revenue_language"), cfmt(total_lang))
                with c2:
                    st.metric(t("top_segment_share"), top_lang_share)

                if top_lang:
                    _callout(t("important"), t("takeaway_language", name=top_lang, share=top_lang_share))

                ser = chart_series(lang_df.rename(columns={lang_col: "subject"}), "subject", inc_col, "subject", "income")
                if ser is None:
                    st.info(t("no_data"))
                else:
                    st.bar_chart(ser)

                lang_show = lang_df.copy()
                lang_show[inc_col] = lang_show[inc_col].apply(cfmt)
                _show_raw_toggle(lang_show, "raw_lang")

        st.markdown(f"#### {t('packages_by_modality')}")
        if sold_by_modality is None or sold_by_modality.empty:
            st.info(t("no_data"))
        else:
            mod_df = sold_by_modality.copy()
            mod_col = _first_existing_col(mod_df, ["modality", "Modality"])
            inc_col = _first_existing_col(mod_df, ["income", "Income", "paid_amount", "total_paid"])
            if not mod_col or not inc_col:
                st.info(t("no_data"))
            else:
                mod_df[mod_col] = mod_df[mod_col].astype(str).apply(translate_modality_value)
                mod_df[inc_col] = pd.to_numeric(mod_df[inc_col], errors="coerce").fillna(0.0).astype(float)
                mod_df = mod_df.sort_values(inc_col, ascending=False).reset_index(drop=True)

                total_mod = float(mod_df[inc_col].sum())
                top_mod = str(mod_df.loc[0, mod_col]) if len(mod_df) else ""
                top_mod_share = _fmt_pct(_pct(float(mod_df.loc[0, inc_col]) if len(mod_df) else 0.0, total_mod))

                c1, c2 = st.columns(2)
                with c1:
                    st.metric(t("total_revenue_modality"), cfmt(total_mod))
                with c2:
                    st.metric(t("top_segment_share"), top_mod_share)

                if top_mod:
                    _callout(t("important"), t("takeaway_modality", name=top_mod, share=top_mod_share))

                ser = chart_series(mod_df.rename(columns={mod_col: "modality"}), "modality", inc_col, "modality", "income")
                if ser is None:
                    st.info(t("no_data"))
                else:
                    st.bar_chart(ser)

                mod_show = mod_df.copy()
                mod_show[inc_col] = mod_show[inc_col].apply(cfmt)
                _show_raw_toggle(mod_show, "raw_mod")

    # ======================
    # TAB 3 — Teaching activity
    # ======================
    with tab_delivery:
        # (UNCHANGED from your current code)
        st.markdown(f"#### {t('lessons_by_subject')}")
        classes = load_table("classes")
        if classes is None or classes.empty:
            st.info(t("no_data"))
        else:
            for c in ["student", "subject", "modality", "number_of_lesson", "lesson_date", "note"]:
                if c not in classes.columns:
                    classes[c] = None

            classes["student"] = classes["student"].fillna("").astype(str).str.strip()
            classes["subject"] = classes["subject"].fillna("").astype(str).str.strip()
            classes["number_of_lesson"] = pd.to_numeric(classes["number_of_lesson"], errors="coerce").fillna(0).astype(int)
            classes = classes[classes["student"].astype(str).str.len() > 0].copy()

            teach_lang = (
                classes.assign(subject=classes["subject"].replace({"": t("unknown")}))
                .groupby("subject", as_index=False)["number_of_lesson"].sum()
                .rename(columns={"number_of_lesson": "units"})
                .sort_values("units", ascending=False)
                .reset_index(drop=True)
            )

            total_u = float(pd.to_numeric(teach_lang["units"], errors="coerce").fillna(0.0).sum())
            top_lang = str(teach_lang.loc[0, "subject"]) if len(teach_lang) else ""
            top_lang_units = float(teach_lang.loc[0, "units"]) if len(teach_lang) else 0.0
            top_lang_share = _fmt_pct(_pct(top_lang_units, total_u))

            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric(t("total_units"), f"{int(total_u)}")
            with c2:
                st.metric(t("top_subject"), top_lang if top_lang else "-")
            with c3:
                st.metric(t("top_segment_share"), top_lang_share)

            if top_lang:
                _callout(t("important"), t("takeaway_activity_language", name=top_lang, share=top_lang_share))

            ser = chart_series(teach_lang, "subject", "units", "subject", "units")
            if ser is None:
                st.info(t("no_data"))
            else:
                st.bar_chart(ser)

            _show_raw_toggle(teach_lang, "raw_lessons_lang")

        st.markdown(f"#### {t('lessons_by_modality')}")
        classes = load_table("classes")
        if classes is None or classes.empty:
            st.info(t("no_data"))
        else:
            for c in ["student", "subject", "modality", "number_of_lesson", "lesson_date", "note"]:
                if c not in classes.columns:
                    classes[c] = None

            classes["student"] = classes["student"].fillna("").astype(str).str.strip()
            classes["modality"] = classes["modality"].fillna("Online").astype(str).str.strip()
            classes["number_of_lesson"] = pd.to_numeric(classes["number_of_lesson"], errors="coerce").fillna(0).astype(int)
            classes = classes[classes["student"].astype(str).str.len() > 0].copy()

            teach_mod = (
                classes.groupby("modality", as_index=False)["number_of_lesson"].sum()
                .rename(columns={"number_of_lesson": "units"})
                .sort_values("units", ascending=False)
                .reset_index(drop=True)
            )

            teach_mod["modality"] = teach_mod["modality"].astype(str).apply(translate_modality_value)

            total_u = float(pd.to_numeric(teach_mod["units"], errors="coerce").fillna(0.0).sum())
            top_mod = str(teach_mod.loc[0, "modality"]) if len(teach_mod) else ""
            top_mod_units = float(teach_mod.loc[0, "units"]) if len(teach_mod) else 0.0
            top_mod_share = _fmt_pct(_pct(top_mod_units, total_u))

            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric(t("total_units"), f"{int(total_u)}")
            with c2:
                st.metric(t("top_modality"), top_mod if top_mod else "-")
            with c3:
                st.metric(t("top_segment_share"), top_mod_share)

            if top_mod:
                _callout(t("important"), t("takeaway_activity_modality", name=top_mod, share=top_mod_share))

            ser = chart_series(teach_mod, "modality", "units", "modality", "units")
            if ser is None:
                st.info(t("no_data"))
            else:
                st.bar_chart(ser)

            _show_raw_toggle(teach_mod, "raw_lessons_mod")

    # ======================
    # TAB 4 — Risk & forecast (UPGRADED)
    # ======================
    with tab_risk:
        st.markdown(f"#### {t('forecast')}")

        buffer_days = st.selectbox(
            t("payment_buffer"),
            [0, 7, 14],
            index=0,
            format_func=lambda x: t("on_finish") if x == 0 else f"{x} {t('days_before')}",
            key="forecast_buffer_analytics",
        )

        forecast_df = build_forecast_table(payment_buffer_days=int(buffer_days))
        if forecast_df is None or forecast_df.empty:
            st.info(t("no_data"))
        else:
            # Column picks (Section 12 output)
            student_like = _first_existing_col(forecast_df, ["Student", "student", "name"])
            left_like = _first_existing_col(forecast_df, ["Lessons_Left_Units", "lessons_left_units", "lessons_left", "units_left"])
            remind_like = _first_existing_col(forecast_df, ["Reminder_Date", "reminder_date"])
            finish_like = _first_existing_col(forecast_df, ["Estimated_Finish_Date", "estimated_finish_date"])
            due_like = _first_existing_col(forecast_df, ["Due_Now", "due_now"])

            ftmp = forecast_df.copy()

            if left_like and left_like in ftmp.columns:
                ftmp[left_like] = pd.to_numeric(ftmp[left_like], errors="coerce").fillna(0.0).astype(float)
            else:
                ftmp[left_like or "_left_tmp"] = 0.0
                left_like = left_like or "_left_tmp"

            # Parse dates
            ftmp["_rem_dt"] = pd.to_datetime(ftmp.get(remind_like), errors="coerce") if remind_like else pd.NaT
            ftmp["_fin_dt"] = pd.to_datetime(ftmp.get(finish_like), errors="coerce") if finish_like else pd.NaT

            # Due logic: prefer Due_Now column from Forecast; else compute from reminder date
            if due_like and due_like in ftmp.columns:
                ftmp["_due_now"] = ftmp[due_like].astype(bool)
            else:
                ftmp["_due_now"] = ftmp["_rem_dt"].notna() & (ftmp["_rem_dt"] <= today)

            # Count metrics
            due_now_df = ftmp[ftmp["_due_now"]].copy()
            finishing_14d_df = ftmp[ftmp["_fin_dt"].notna() & (ftmp["_fin_dt"] <= (today + pd.Timedelta(days=14)))].copy()
            at_risk_count = int((ftmp[left_like] <= 2).sum())

            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric(t("students_in_forecast"), f"{len(ftmp)}")
            with c2:
                st.metric(t("due_now"), f"{len(due_now_df)}")
            with c3:
                st.metric(t("finishing_14d"), f"{len(finishing_14d_df)}")

            # Smaller second row metric (still useful)
            st.caption(f"{t('at_risk')} (≤2 {t('units_left')}): **{at_risk_count}**")

            _callout(t("important"), t("takeaway_pipeline"))

            st.markdown(f"##### {t('students_to_contact')}")

            # Show due now; if none, show next up (soonest reminders)
            if not due_now_df.empty:
                show_df = due_now_df.sort_values(["_rem_dt", left_like, student_like if student_like else "Student"]).head(10)
                st.caption("Due now based on your reminder buffer.")
            else:
                upcoming = ftmp[ftmp["_rem_dt"].notna() & (ftmp["_rem_dt"] > today)].copy()
                show_df = upcoming.sort_values(["_rem_dt", left_like, student_like if student_like else "Student"]).head(10)
                if not show_df.empty:
                    soonest = show_df["_rem_dt"].min()
                    st.caption(f"{t('next_up')}: {soonest.strftime('%Y-%m-%d')}")
                else:
                    st.info("No upcoming reminders found.")
                    show_df = pd.DataFrame()

            if not show_df.empty and student_like and student_like in show_df.columns:
                for _, row in show_df.iterrows():
                    sname = str(row.get(student_like, "")).strip() or "(student)"
                    units_left = row.get(left_like, None)
                    rem = row.get("_rem_dt", None)
                    fin = row.get("_fin_dt", None)

                    parts = [sname]
                    if units_left is not None and str(units_left) != "nan":
                        try:
                            parts.append(f"{t('units_left')}: {int(float(units_left))}")
                        except Exception:
                            pass
                    if rem is not None and pd.notna(rem):
                        parts.append(f"{t('remind')}: {pd.Timestamp(rem).strftime('%Y-%m-%d')}")
                    if fin is not None and pd.notna(fin):
                        parts.append(f"{t('finish')}: {pd.Timestamp(fin).strftime('%Y-%m-%d')}")
                    st.write("• " + " — ".join(parts))
            else:
                st.write("• " + t("no_data"))

            # Raw toggle (keeps your pattern)
            _show_raw_toggle(ftmp.drop(columns=["_rem_dt", "_fin_dt", "_due_now"], errors="ignore"), "raw_forecast")

