# CLASSIO — Pre-login Goal Explorer
# ============================================================
import math
import streamlit as st
from core.i18n import t
from helpers.currency import CURRENCIES, currency_symbol
from helpers.planner_storage import load_public_lesson_plans,render_plan_library_cards,render_quick_lesson_plan_result
from helpers.worksheet_storage import load_public_worksheets, render_worksheet_library_cards, render_worksheet_result
from styles.theme import load_css_home
import re
import pandas as pd

# ── Hourly rate ranges by subject and modality (USD) ──
# (min, default, max) — based on current private-tutoring market data.
# Base rates assume adult learners (most common / highest rate segment).
_RATE_RANGES_USD: dict[str, dict[str, tuple[int, int, int]]] = {
    "english":      {"online": (25, 40, 80), "offline": (30, 50, 90)},
    "spanish":      {"online": (25, 40, 80), "offline": (30, 50, 90)},
    "mathematics":  {"online": (30, 50, 100), "offline": (35, 55, 110)},
    "science":      {"online": (30, 50, 100), "offline": (35, 55, 110)},
    "music":        {"online": (25, 45, 90), "offline": (30, 50, 100)},
    "study_skills": {"online": (20, 35, 70), "offline": (25, 40, 80)},
}

# ── Audience multipliers (market research) ──
# Adults pay the highest → 1.0 baseline.
# Teens: parents typically pay ~15-20 % less than adult-rate tutoring.
# Kids: sessions shorter / lower complexity → ~20-30 % less.
_AUDIENCE_MULTIPLIER: dict[str, float] = {
    "kids":   0.75,
    "teens":  0.85,
    "adults": 1.00,
}

# ── Education-level multipliers ──
# Higher qualifications command higher rates.
_EDUCATION_MULTIPLIER: dict[str, float] = {
    "student":   0.70,
    "bachelors": 0.90,
    "masters":   1.00,
    "doctorate": 1.15,
}

# Rough USD → local multipliers for quick estimation.
_CURRENCY_RATE_FROM_USD: dict[str, float] = {
    "USD": 1.0,
    "EUR": 0.92,
    "GBP": 0.79,
    "TRY": 38.0,
    "ARS": 1060.0,
    "BRL": 5.1,
    "MXN": 17.2,
    "JPY": 155.0,
    "CAD": 1.37,
    "AUD": 1.55,
    "CHF": 0.88,
    "COP": 3950.0,
    "CLP": 950.0,
    "INR": 83.5,
    "KRW": 1340.0,
    "SEK": 10.8,
    "NOK": 10.9,
    "DKK": 6.9,
    "PLN": 4.0,
    "CNY": 7.25,
}

# Planning constants
_TEACHING_WEEKS_PER_YEAR = 44        # ~8 weeks of holidays / breaks
_LESSONS_PER_STUDENT_PER_WEEK = 1.5  # avg mix of weekly and biweekly


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().casefold())

def _tokens(query: str) -> list[str]:
    return [t for t in re.split(r"[^a-zA-Z0-9]+", _normalize(query)) if t]

def _prepare_searchable_resources(df: pd.DataFrame, kind: str) -> pd.DataFrame:
    out = df.copy()

    def _safe_t(value: str) -> str:
        try:
            return t(value) if value else ""
        except Exception:
            return str(value or "")

    if "subject" in out.columns:
        out["_search_subject"] = out["subject"].fillna("").astype(str)

    if "learner_stage" in out.columns:
        out["_search_stage"] = out["learner_stage"].fillna("").astype(str).apply(_safe_t)

    if "level_or_band" in out.columns:
        def _level_label(v: str) -> str:
            v = str(v or "")
            if v in ["A1", "A2", "B1", "B2", "C1", "C2"]:
                return v
            return _safe_t(v)
        out["_search_level"] = out["level_or_band"].fillna("").astype(str).apply(_level_label)

    if kind == "plan" and "lesson_purpose" in out.columns:
        out["_search_type"] = out["lesson_purpose"].fillna("").astype(str).apply(_safe_t)

    if kind == "worksheet" and "worksheet_type" in out.columns:
        out["_search_type"] = out["worksheet_type"].fillna("").astype(str).apply(_safe_t)

    return out

def _rank_search(df: pd.DataFrame, query: str, weights: dict) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    q = _normalize(query)
    toks = _tokens(query)

    if not q or not toks:
        if "created_at" in df.columns:
            return df.sort_values("created_at", ascending=False)
        return df.copy()

    def score(row):
        s = 0.0
        matched = False

        for field, w in weights.items():
            text = _normalize(row.get(field, ""))

            if not text:
                continue

            # strong full-phrase match
            if q in text:
                s += w * 4
                matched = True

            # token matches
            for tok in toks:
                if tok in text:
                    s += w
                    matched = True

        # only give recency boost if there was at least one text match
        if matched and pd.notna(row.get("created_at")):
            s += 0.2

        return s

    ranked = df.copy()
    ranked["_score"] = ranked.apply(score, axis=1)
    ranked = ranked[ranked["_score"] > 0]

    if ranked.empty:
        return ranked

    if "created_at" in ranked.columns:
        ranked = ranked.sort_values(["_score", "created_at"], ascending=[False, False])
    else:
        ranked = ranked.sort_values(["_score"], ascending=[False])

    return ranked

def _range_in_currency(
    subject: str, modality: str, currency: str,
    audience: str = "adults", education: str = "bachelors",
) -> tuple[int, int, int]:
    """Return (min, default, max) hourly rate in the chosen currency."""
    rng = _RATE_RANGES_USD.get(subject, {"online": (25, 40, 80), "offline": (30, 50, 90)}).get(modality, (25, 40, 80))
    fx = _CURRENCY_RATE_FROM_USD.get(currency, 1.0)
    aud = _AUDIENCE_MULTIPLIER.get(audience, 1.0)
    edu = _EDUCATION_MULTIPLIER.get(education, 0.90)
    m = aud * edu
    return (round(rng[0] * fx * m), round(rng[1] * fx * m), round(rng[2] * fx * m))


def _blended_range(
    subject: str, currency: str,
    audience: str = "adults", education: str = "bachelors",
) -> tuple[int, int, int]:
    """Average the online and offline ranges for 'both' modality."""
    on = _range_in_currency(subject, "online", currency, audience, education)
    off = _range_in_currency(subject, "offline", currency, audience, education)
    return (min(on[0], off[0]), round((on[1] + off[1]) / 2), max(on[2], off[2]))

def _render_explore_teaching_resources() -> None:
    st.markdown(
        f"""
        <div style="text-align:center; padding:12px 0 8px 0;">
            <h3 style="margin:0 0 4px 0; font-size:1.2rem; font-weight:800; color:var(--text);">
                📚 {t("teaching_resources")}
            </h3>
            <p style="margin:0; color:var(--muted); font-size:0.9rem;">
                {t("explore_teaching_resources_subtitle")}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab1, tab2 = st.tabs([
        f"📝 {t('community_plans')}",
        f"📋 {t('community_worksheets')}",
    ])

    # ---------------------------
    # LESSON PLANS
    # ---------------------------
    with tab1:
        public_plans = load_public_lesson_plans()

        if public_plans.empty:
            st.info(t("community_library_empty"))
        else:
            plan_q = st.text_input(
                t("explore_resource_search"),
                key="explore_public_plans_q",
                placeholder=t("explore_resource_search_placeholder"),
            ).strip()

            searchable_plans = _prepare_searchable_resources(public_plans, kind="plan")

            if plan_q:
                filtered_plans = _rank_search(
                    searchable_plans,
                    plan_q,
                    weights={
                        "title": 5,
                        "topic": 4,
                        "_search_subject": 3,
                        "_search_type": 3,
                        "_search_stage": 2,
                        "_search_level": 2,
                        "author_name": 1,
                    },
                )
            else:
                filtered_plans = searchable_plans.copy()

            if "created_at" in filtered_plans.columns:
                filtered_plans = filtered_plans.sort_values("created_at", ascending=False)

            # clean temporary search columns
            filtered_plans = filtered_plans.drop(
                columns=[c for c in filtered_plans.columns if c.startswith("_search")],
                errors="ignore"
            )
            
            plans_to_show = filtered_plans if plan_q else filtered_plans.head(6)

            if plans_to_show.empty:
                st.info(t("be_the_first_to_share"))
            else:
                if plan_q:
                    st.caption(f"{len(plans_to_show)} {t('community_plans').lower()}")
                else:
                    st.caption(t("explore_latest_resources_note").format(count=6))

                render_plan_library_cards(
                    plans_to_show,
                    prefix="explore_public_plans",
                    show_author=True,
                    open_in_files=False,
                    require_signup=True,
                )

    # ---------------------------
    # WORKSHEETS
    # ---------------------------
    with tab2:
        public_ws = load_public_worksheets()

        if public_ws.empty:
            st.info(t("community_library_empty"))
        else:
            ws_q = st.text_input(
                t("explore_resource_search"),
                key="explore_public_ws_q",
                placeholder=t("explore_resource_search_placeholder"),
            ).strip()

            searchable_ws = _prepare_searchable_resources(public_ws, kind="worksheet")

            if ws_q:
                filtered_ws = _rank_search(
                    searchable_ws,
                    ws_q,
                    weights={
                        "title": 5,
                        "topic": 4,
                        "_search_subject": 3,
                        "_search_type": 3,
                        "_search_stage": 2,
                        "_search_level": 2,
                        "author_name": 1,
                    },
                )
            else:
                filtered_ws = searchable_ws.copy()

            if "created_at" in filtered_ws.columns:
                filtered_ws = filtered_ws.sort_values("created_at", ascending=False)

            # clean temporary search columns
            filtered_ws = filtered_ws.drop(
                columns=[c for c in filtered_ws.columns if c.startswith("_search")],
                errors="ignore"
            )
            
            ws_to_show = filtered_ws if ws_q else filtered_ws.head(6)

            if ws_to_show.empty:
                st.info(t("be_the_first_to_share"))
            else:
                if ws_q:
                    st.caption(f"{len(ws_to_show)} {t('community_worksheets').lower()}")
                else:
                    st.caption(t("explore_latest_resources_note").format(count=6))

                render_worksheet_library_cards(
                    ws_to_show,
                    prefix="explore_public_ws",
                    show_author=True,
                    open_in_files=False,
                    require_signup=True,
                )
  

    # ── Teaching Income Goal ──
def render_goal_explorer() -> bool:
    """
    Render the pre-login goal-setting card.
    Returns True when the user clicks the CTA to find students (triggers sign-up).
    """
    load_css_home()

    # ── Work Smart Tools ── 
    _render_explore_ai_tools()  

    # ── Teaching Resources preview ──
    st.markdown("---")
    _render_explore_teaching_resources()

    st.markdown("---")
    st.markdown(
        f"""
        <div style="
            text-align:center; padding:18px 10px 6px 10px;
        ">
            <h3 style="margin:0 0 2px 0; font-size:1.35rem; font-weight:800; color:var(--text);">
                {t('explore_goal_title')}
            </h3>
            <p style="margin:0; color:var(--muted); font-size:0.95rem;">
                {t('explore_goal_subtitle')}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Subject ──
    subject_labels = {
        "english": t("subject_english"),
        "spanish": t("subject_spanish"),
        "mathematics": t("subject_mathematics"),
        "science": t("subject_science"),
        "music": t("subject_music"),
        "study_skills": t("subject_study_skills"),
        "other": t("explore_other"),
    }
    subject_keys = list(subject_labels.keys())
    subject = st.selectbox(
        t("explore_subject"),
        options=subject_keys,
        format_func=lambda k: subject_labels[k],
        key="explore_subject",
    )

    custom_subject = ""
    if subject == "other":
        custom_subject = st.text_input(
            t("explore_other_subject_input"),
            key="explore_custom_subject",
        ).strip()

    # --- Achievability scale ---
    # (Move this logic to where hours_per_week is defined and used, not here)

    # ── Modality ──
    modality_labels = {
        "online": t("explore_online"),
        "offline": t("explore_offline"),
        "both": t("explore_both"),
    }
    modality = st.radio(
        t("explore_modality"),
        options=list(modality_labels.keys()),
        format_func=lambda k: modality_labels[k],
        horizontal=True,
        key="explore_modality",
    )

    # ── Target audience ──
    audience_labels = {
        "kids": t("audience_kids"),
        "teens": t("audience_teens"),
        "adults": t("audience_adults"),
    }
    audience = st.radio(
        t("target_audience"),
        options=list(audience_labels.keys()),
        format_func=lambda k: audience_labels[k],
        horizontal=True,
        key="explore_audience",
    )

    # ── Education level ──
    education_labels = {
        "student": t("edu_student"),
        "bachelors": t("edu_bachelors"),
        "masters": t("edu_masters"),
        "doctorate": t("edu_doctorate"),
    }
    education = st.selectbox(
        t("education_level"),
        options=list(education_labels.keys()),
        format_func=lambda k: education_labels[k],
        key="explore_education",
    )

    # ── Currency ──
    currency_options = list(CURRENCIES.keys())
    currency = st.selectbox(
        t("explore_currency"),
        options=currency_options,
        format_func=lambda c: f"{CURRENCIES[c]['symbol']}  {c} — {CURRENCIES[c]['name']}",
        key="explore_currency",
    )

    # ── Fee range slider ──
    sym = currency_symbol(currency)
    rate_subject = subject if subject != "other" else "english"  # fallback range
    if modality == "both":
        rate_min, rate_default, rate_max = _blended_range(rate_subject, currency, audience=audience, education=education)
    else:
        rate_min, rate_default, rate_max = _range_in_currency(rate_subject, modality, currency, audience=audience, education=education)

    # Ensure step is sensible for the currency
    step = max(1, round((rate_max - rate_min) / 40))
    hourly_rate = st.slider(
        t("explore_select_fee", sym=sym),
        min_value=rate_min,
        max_value=rate_max,
        value=rate_default,
        step=step,
        key="explore_fee_slider",
    )
    st.caption(t("explore_fee_hint"))

    # ── Yearly income goal ──
    goal_amount = st.number_input(
        t("explore_goal_amount", sym=sym),
        min_value=0,
        step=500,
        value=0,
        key="explore_goal_amount",
    )

    # ── Calculate button ──
    if st.button(t("explore_see_plan"), type="primary", use_container_width=True):
        if goal_amount <= 0:
            st.warning(t("explore_enter_amount"))
            return False
        st.session_state["explore_plan_ready"] = True

    # ── Show plan ──
    if st.session_state.get("explore_plan_ready") and goal_amount > 0:
        total_hours = math.ceil(goal_amount / hourly_rate) if hourly_rate else 0
        hours_per_week = math.ceil(total_hours / _TEACHING_WEEKS_PER_YEAR) if _TEACHING_WEEKS_PER_YEAR else 0
        students_needed = math.ceil(hours_per_week / _LESSONS_PER_STUDENT_PER_WEEK) if _LESSONS_PER_STUDENT_PER_WEEK else 0

        # --- Achievability scale and advice ---
        if hours_per_week <= 24:
            achievability = f"<span style='color:#16a34a;font-weight:700;'>{t('explore_achievability_green')}</span>"
            advice = t('explore_advice_green')
        elif 25 <= hours_per_week <= 31:
            achievability = f"<span style='color:#eab308;font-weight:700;'>{t('explore_achievability_yellow')}</span>"
            advice = t('explore_advice_yellow')
        elif 32 <= hours_per_week <= 42:
            achievability = f"<span style='color:#f97316;font-weight:700;'>{t('explore_achievability_orange')}</span>"
            advice = t('explore_advice_orange')
        else:
            achievability = f"<span style='color:#dc2626;font-weight:700;'>{t('explore_achievability_red')}</span>"
            advice = t('explore_advice_red')

        formatted_rate = f"{sym} {hourly_rate:,}"
        formatted_goal = f"{sym} {goal_amount:,}"

        st.markdown("---")
        st.markdown(
            f"""
            <div style="
                background:linear-gradient(180deg,var(--panel),var(--panel-2));
                border-radius:16px;
                padding:22px 20px;
                border:1px solid var(--border);
                box-shadow:var(--shadow-md);
            ">
                <h4 style="margin:0 0 10px 0; color:var(--primary); font-size:1.15rem;">
                    📋 {t('explore_your_plan')}
                </h4>
                <table style="width:100%; border-collapse:collapse; font-size:0.97rem;">
                    <tr>
                        <td style="padding:6px 0; color:var(--muted);">{t('explore_plan_goal')}</td>
                        <td style="padding:6px 0; font-weight:700; text-align:right; color:var(--text);">{formatted_goal}</td>
                    </tr>
                    <tr>
                        <td style="padding:6px 0; color:var(--muted);">{t('explore_plan_rate')}</td>
                        <td style="padding:6px 0; font-weight:700; text-align:right; color:var(--text);">{formatted_rate} <span style="font-weight:400;color:var(--muted);font-size:0.85rem;">({t('explore_your_choice')})</span></td>
                    </tr>
                    <tr>
                        <td style="padding:6px 0; color:var(--muted);">{t('explore_plan_hours_year')}</td>
                        <td style="padding:6px 0; font-weight:700; text-align:right; color:var(--text);">{total_hours:,}</td>
                    </tr>
                    <tr>
                        <td style="padding:6px 0; color:var(--muted);">{t('explore_plan_hours_week')}</td>
                        <td style="padding:6px 0; font-weight:700; text-align:right; color:var(--text);">{hours_per_week}</td>
                    </tr>
                    <tr>
                        <td style="padding:6px 0; color:var(--muted);">{t('explore_achievability_label')}</td>
                        <td style="padding:6px 0; font-weight:700; text-align:right; color:var(--text);">{achievability}</td>
                    </tr>
                    <tr style="border-top:2px solid rgba(37,99,235,0.18);">
                        <td style="padding:10px 0 4px 0; color:var(--primary); font-weight:700; font-size:1.05rem;">
                            {t('explore_plan_students')}
                        </td>
                        <td style="padding:10px 0 4px 0; font-weight:800; text-align:right; color:var(--primary); font-size:1.15rem;">
                            {students_needed}
                        </td>
                    </tr>
                </table>
                <div style="margin:10px 0 0 0; color:var(--muted); font-size:0.92rem;">
                    <b>{t('explore_advice_label')}</b> {advice}
                </div>
                <p style="margin:12px 0 0 0; color:var(--muted); font-size:0.82rem;">
                    {t('explore_plan_note')}
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )        

        st.markdown("")

        # CTA: find students → triggers sign-up
        if st.button(
            t("explore_find_students_cta"),
            type="primary",
            use_container_width=True,
            key="explore_cta_signup",
        ):
            return True

    # ── Manage Your Students — feature showcase ──
    st.markdown("---")
    _render_feature_showcase()

    st.markdown(
        """
        <div class="home-section-line"> 
          <span>🤖</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    return False


# ─────────────────────────────────────────────────────────────
# App feature showcase — shows what users can do after signup
# ─────────────────────────────────────────────────────────────
_FEATURE_ITEMS = [
    ("dashboard", "📊", "rgba(59,130,246,0.55)"),
    ("students",  "👩‍🎓", "rgba(16,185,129,0.55)"),
    ("add_lesson", "📝", "rgba(245,158,11,0.55)"),
    ("add_payment", "💳", "rgba(239,68,68,0.55)"),
    ("calendar",  "📅", "rgba(6,182,212,0.55)"),
    ("analytics", "📈", "rgba(168,85,247,0.55)"),
]

_FEATURE_DESCRIPTIONS = {
    "dashboard":   "explore_feat_dashboard",
    "students":    "explore_feat_students",
    "add_lesson":  "explore_feat_lesson",
    "add_payment": "explore_feat_payment",
    "calendar":    "explore_feat_calendar",
    "analytics":   "explore_feat_analytics",
}


def _render_feature_showcase() -> None:
    st.markdown(
        f"""
        <div style="text-align:center; padding:12px 0 8px 0;">
            <h3 style="margin:0 0 4px 0; font-size:1.2rem; font-weight:800; color:var(--text, #0f172a);">
                {t('explore_features_title')}
            </h3>
            <p style="margin:0; color:var(--muted, #475569); font-size:0.9rem;">
                {t('explore_features_subtitle')}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    rows = [_FEATURE_ITEMS[0:2], _FEATURE_ITEMS[2:4], _FEATURE_ITEMS[4:6]]

    for row in rows:
        cols = st.columns(len(row), gap="medium")
        for col, (key, icon, glow) in zip(cols, row):
            with col:
                label = t(key) if key in ("dashboard", "students", "calendar", "analytics") else t(key.replace("add_", ""))
                desc = t(_FEATURE_DESCRIPTIONS[key])
                st.markdown(
                    f"""
                    <div style="
                        background: linear-gradient(180deg, var(--panel, rgba(255,255,255,0.92)), var(--panel-2, rgba(248,250,255,0.85)));
                        border: 1px solid var(--border-strong, rgba(17,24,39,0.08));
                        border-radius: 16px;
                        padding: 16px 12px 10px 12px;
                        text-align: center;
                        box-shadow: 0 4px 18px {glow};
                        min-height: 90px;
                    ">
                        <div style="font-size:1.6rem; margin-bottom:4px;">{icon}</div>
                        <div style="font-weight:700; font-size:0.95rem; color:var(--text, #0f172a);">{label}</div>
                        <div style="font-size:0.78rem; color:var(--muted, #64748b); margin-top:2px;">{desc}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button(
                    t("explore_try_feature"),
                    key=f"explore_feat_{key}",
                    use_container_width=True,
                ):
                    st.session_state["_explore_go_signup"] = True
                    st.session_state["_after_signup_page"] = key
                    st.rerun()
        st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# Explore-page CV builder (AI-powered, 1-use limit for anon)
# ─────────────────────────────────────────────────────────────

_EXPLORE_CV_SUBJECTS = ["english", "spanish", "mathematics", "science", "music", "study_skills", "other"]
_EXPLORE_CV_STAGES = [
    "early_primary",
    "upper_primary",
    "lower_secondary",
    "upper_secondary",
    "adult_stage",
]
_EXPLORE_CV_STAGE_LABELS = {
    "early_primary": "Early Primary (6–8)",
    "upper_primary": "Upper Primary (9–11)",
    "lower_secondary": "Lower Secondary (12–14)",
    "upper_secondary": "Upper Secondary (15–18)",
    "adult_stage": "Adult",
}


def _render_explore_cv_builder() -> None:
    """Quick CV builder for anonymous users. AI with 1-use limit. Save requires signup."""
    import helpers.lesson_planner as lp
    from helpers.cv_builder import build_ai_cv
    from helpers.cv_storage import render_cv_result

    with st.expander(t("quick_cv_builder"), expanded=False):
        st.caption(t("quick_cv_caption"))

        ai_used = st.session_state.get("_explore_cv_ai_used", 0)
        ai_remaining = max(0, _EXPLORE_AI_LIMIT - ai_used)

        if ai_remaining > 0:
            st.caption(t("explore_ai_remaining", remaining=ai_remaining))
        else:
            st.warning(t("explore_ai_limit_reached"))

        # Personal info
        st.markdown(f"**{t('cv_personal_info')}**")
        full_name = st.text_input(t("cv_full_name_label"), key="explore_cv_name").strip()

        # Teaching info
        st.markdown(f"**{t('cv_teaching_info')}**")
        subjects = st.multiselect(
            t("subject_label"),
            options=_EXPLORE_CV_SUBJECTS,
            format_func=lp.subject_label,
            key="explore_cv_subjects",
        )
        other_cv_subject = ""
        if "other" in subjects:
            other_cv_subject = st.text_input(
                t("other_subject_label"),
                key="explore_cv_other_subject",
            ).strip()
        
        teaching_stages = st.multiselect(
            t("learner_stage"),
            options=_EXPLORE_CV_STAGES,
            format_func=lambda s: _EXPLORE_CV_STAGE_LABELS.get(s, s),
            key="explore_cv_stages",
        )

        # Professional details
        st.markdown(f"**{t('cv_professional_summary')}**")
        summary = st.text_area(t("cv_professional_summary"), key="explore_cv_summary", label_visibility="collapsed")

        st.markdown(f"**{t('cv_education')}**")
        education_text = st.text_area(t("cv_education"), key="explore_cv_education", label_visibility="collapsed")

        st.markdown(f"**{t('cv_experience')}**")
        experience_text = st.text_area(t("cv_experience"), key="explore_cv_experience", label_visibility="collapsed")

        ai_prompt = st.text_input(
            t("cv_ai_prompt"),
            key="explore_cv_ai_prompt",
        )

        effective_subjects = [s for s in subjects if s != "other"]
        if "other" in subjects and other_cv_subject:
            effective_subjects.append(other_cv_subject)

        if st.button(t("generate_cv"), key="btn_explore_gen_cv", use_container_width=True):
            if not full_name:
                st.error(t("cv_name_required"))
            elif ai_remaining <= 0:
                st.warning(t("explore_ai_limit_reached")) 
            else:
                with st.spinner(t("generating_cv")):
                    try:
                        cv = build_ai_cv(
                            full_name=full_name,
                            email="",
                            phone="",
                            location="",
                            date_of_birth="",
                            sex="",
                            subjects=effective_subjects,
                            teaching_stages=teaching_stages,
                            teaching_languages=[],
                            professional_summary=summary,
                            education_text=education_text,
                            certifications_text="",
                            experience_text=experience_text,
                            skills_text="",
                            availability="",
                            rate="",
                            role=f"{t('teacher_role')} / {t('tutor_role')}",
                            user_prompt=ai_prompt,
                        )
                        st.session_state["explore_generated_cv"] = cv
                        st.session_state["explore_generated_cv_meta"] = {
                            "full_name": full_name,
                            "subjects": subjects,
                            "teaching_stages": teaching_stages,
                        }
                        st.session_state["_explore_cv_ai_used"] = ai_used + 1
                    except Exception as e:
                        st.error(f"{t('ai_unavailable_fallback')} ({e})")

        # Display generated CV
        cv = st.session_state.get("explore_generated_cv")
        cv_meta = st.session_state.get("explore_generated_cv_meta", {})
        if cv:
            render_cv_result(cv, read_only=True, source_type="ai", ai_prompt=ai_prompt)

            if st.button(
                t("explore_save_cv_cta"),
                type="primary",
                use_container_width=True,
                key="btn_explore_save_cv",
            ):
                st.session_state["_pending_cv_after_signup"] = {
                    "cv": cv,
                    "meta": cv_meta,
                }
                st.session_state["_explore_go_signup"] = True
                st.rerun()


# ─────────────────────────────────────────────────────────────
# Explore-page AI Tools (functional for anonymous users)
# ─────────────────────────────────────────────────────────────
_EXPLORE_AI_LIMIT = 1  # anonymous users: 1 AI use per tool


def _render_explore_ai_tools() -> None:
    """AI Tools section for the explore page: Lesson Planner + Worksheet Maker."""
    st.markdown(
        f"""
        <div style="text-align:center; padding:0px 0 8px 0;">
            <h3 style="margin:0 0 4px 0; font-size:1.2rem; font-weight:800; color:var(--text);">
                🤖 {t('explore_ai_tools_title')}
            </h3>
            <p style="margin:0; color:var(--muted); font-size:0.9rem;">
                {t('explore_ai_tools_subtitle')}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    selected = st.session_state.get("explore_ai_tool_selected", "")

    cols = st.columns(2, gap="medium")

    cards = [
        {
            "key": "planner",
            "icon": "📝",
            "title": t("quick_lesson_planner"),
            "glow": "rgba(59,130,246,0.55)",
            "desc": t("explore_planner_caption_one"),
        },
        {
            "key": "worksheet",
            "icon": "📋",
            "title": t("worksheet_maker"),
            "glow": "rgba(16,185,129,0.55)",
            "desc": t("worksheet_maker_caption_one"),
        },
    ]

    for col, card in zip(cols, cards):
        with col:
            is_active = selected == card["key"]
            border_style = (
                "2px solid var(--primary)"
                if is_active
                else "1px solid var(--border-strong, rgba(17,24,39,0.08))"
            )

            st.markdown(
                f"""
                <div style="
                    background: linear-gradient(180deg, var(--panel, rgba(255,255,255,0.92)), var(--panel-2, rgba(248,250,255,0.85)));
                    border: {border_style};
                    border-radius: 16px;
                    padding: 18px 14px 12px 14px;
                    text-align: center;
                    box-shadow: 0 4px 18px {card["glow"]};
                    min-height: 120px;
                ">
                    <div style="font-size:1.8rem; margin-bottom:6px;">{card["icon"]}</div>
                    <div style="font-weight:700; font-size:1rem; color:var(--text, #0f172a);">
                        {card["title"]}
                    </div>
                    <div style="font-size:0.82rem; color:var(--muted, #64748b); margin-top:6px; line-height:1.35;">
                        {card["desc"]}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            button_label = t("close") if is_active else t("try_now")
            if st.button(button_label, key=f"explore_ai_card_{card['key']}", use_container_width=True):
                if is_active:
                    st.session_state["explore_ai_tool_selected"] = ""
                else:
                    st.session_state["explore_ai_tool_selected"] = card["key"]
                st.rerun()

            if is_active:
                st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
                if card["key"] == "planner":
                    _render_explore_lesson_planner()
                elif card["key"] == "worksheet":
                    _render_explore_worksheet_maker()

# ─────────────────────────────────────────────────────────────
# Explore-page worksheet maker (AI-powered, 1-use limit for anon)
# ─────────────────────────────────────────────────────────────

def _render_explore_worksheet_maker() -> None:
    """Worksheet maker for anonymous users. AI with limit. Save requires signup."""
    import helpers.lesson_planner as lp
    from helpers.worksheet_builder import (
        WORKSHEET_TYPES,
        generate_ai_worksheet,
        normalize_worksheet_output,
        get_plan_language,
        get_student_material_language,
    )

    st.markdown(f"### 📋 {t('worksheet_maker')}")
    st.caption(t("worksheet_maker_caption"))

    ai_used = st.session_state.get("_explore_ws_ai_used", 0)
    ai_remaining = max(0, _EXPLORE_AI_LIMIT - ai_used)

    if ai_remaining > 0:
        st.caption(t("explore_ai_remaining", remaining=ai_remaining))
    else:
        st.warning(t("explore_ai_limit_reached"))

    subject = st.selectbox(
        t("subject_label"),
        lp.QUICK_SUBJECTS,
        format_func=lp.subject_label,
        key="explore_ws_subject",
    )

    other_subject_name = ""
    if subject == "other":
        other_subject_name = st.text_input(
            t("other_subject_label"),
            key="explore_ws_other_subject",
        ).strip()

    learner_stage = st.selectbox(
        t("learner_stage"),
        lp.LEARNER_STAGES,
        format_func=lp._stage_label,
        key="explore_ws_stage",
    )

    default_level = lp.recommend_default_level(subject, learner_stage)
    level_options = lp.get_level_options(subject)
    if st.session_state.get("explore_ws_level") not in level_options:
        st.session_state["explore_ws_level"] = default_level

    c1, c2 = st.columns(2)
    with c1:
        level_or_band = st.selectbox(
            t("level_or_band"),
            level_options,
            format_func=lp._level_label,
            key="explore_ws_level",
        )
    with c2:
        worksheet_type = st.selectbox(
            t("worksheet_type_label"),
            WORKSHEET_TYPES,
            format_func=lambda x: t(x),
            key="explore_ws_type",
        )

    topic = st.text_input(t("topic_label"), key="explore_ws_topic")

    if st.button(t("generate_worksheet"), key="btn_explore_gen_ws", use_container_width=True):
        if not topic.strip():
            st.error(t("enter_topic"))
        elif subject == "other" and not other_subject_name:
            st.error(t("enter_subject_name"))
        elif ai_remaining <= 0:
            st.warning(t("explore_ai_limit_reached"))
        else:
            effective_subject = other_subject_name if subject == "other" else subject
            with st.spinner(t("generating")):
                try:
                    ws = generate_ai_worksheet(
                        subject=effective_subject,
                        learner_stage=learner_stage,
                        level_or_band=level_or_band,
                        worksheet_type=worksheet_type,
                        topic=topic.strip(),
                        plan_language=get_plan_language(),
                        student_material_language=get_student_material_language(effective_subject),
                    )
                    ws = normalize_worksheet_output(ws)
                    st.session_state["explore_generated_worksheet"] = ws
                    st.session_state["explore_generated_worksheet_meta"] = {
                        "subject": effective_subject,
                        "learner_stage": learner_stage,
                        "level_or_band": level_or_band,
                        "worksheet_type": worksheet_type,
                        "topic": topic.strip(),
                    }
                    st.session_state["_explore_ws_ai_used"] = ai_used + 1
                except Exception as e:
                    st.error(f"{t('ai_unavailable_fallback')} ({e})")

    ws = st.session_state.get("explore_generated_worksheet")
    ws_meta = st.session_state.get("explore_generated_worksheet_meta", {})
    if ws:
        render_worksheet_result(
            ws,
            read_only=True,
            subject=ws_meta.get("subject", ""),
            learner_stage=ws_meta.get("learner_stage", ""),
            level_or_band=ws_meta.get("level_or_band", ""),
            worksheet_type=ws_meta.get("worksheet_type", ""),
            topic=ws_meta.get("topic", ""),
        )

        if st.button(
            t("explore_save_worksheet_cta"),
            type="primary",
            use_container_width=True,
            key="btn_explore_save_ws",
        ):
            st.session_state["_pending_worksheet_after_signup"] = {
                "worksheet": ws,
                "meta": ws_meta,
            }
            st.session_state["_explore_go_signup"] = True
            st.rerun()
# ─────────────────────────────────────────────────────────────
# Explore-page lesson planner (AI-powered, 1-use limit for anon)
# ─────────────────────────────────────────────────────────────


def _render_explore_lesson_planner() -> None:
    """Lesson planner for anonymous users. AI with limit. Save requires signup."""
    import helpers.lesson_planner as lp

    st.markdown(f"### 📝 {t('quick_lesson_planner')}")
    st.caption(t("explore_planner_caption"))

    ai_used = st.session_state.get("_explore_ai_used", 0)
    ai_remaining = max(0, _EXPLORE_AI_LIMIT - ai_used)

    if ai_remaining > 0:
        st.caption(t("explore_ai_remaining", remaining=ai_remaining))
    else:
        st.warning(t("explore_ai_limit_reached"))

    plan_subject = st.selectbox(
        t("subject_label"),
        lp.QUICK_SUBJECTS,
        format_func=lp.subject_label,
        key="explore_plan_subject",
    )

    other_subject_name = ""
    if plan_subject == "other":
        other_subject_name = st.text_input(
            t("other_subject_label"),
            key="explore_plan_other_subject",
        ).strip()

    learner_stage = st.selectbox(
        t("learner_stage"),
        lp.LEARNER_STAGES,
        format_func=lp._stage_label,
        key="explore_plan_stage",
    )

    default_level = lp.recommend_default_level(plan_subject, learner_stage)
    level_options = lp.get_level_options(plan_subject)

    if st.session_state.get("explore_plan_level") not in level_options:
        st.session_state["explore_plan_level"] = default_level

    c1, c2 = st.columns(2)
    with c1:
        level_or_band = st.selectbox(
            t("level_or_band"),
            level_options,
            format_func=lp._level_label,
            key="explore_plan_level",
        )
    with c2:
        lesson_purpose = st.selectbox(
            t("lesson_purpose"),
            lp.LESSON_PURPOSES,
            format_func=lp._purpose_label,
            key="explore_plan_purpose",
        )

    topic = st.text_input(t("topic_label"), key="explore_plan_topic")

    rec_level = lp.recommend_default_level(plan_subject, learner_stage)
    rec_label = rec_level if rec_level in lp.LANGUAGE_LEVELS else t(rec_level)
    st.caption(f"{t('recommended_level')}: {rec_label}")

    if st.button(t("generate_plan"), key="btn_explore_generate_plan", use_container_width=True):
        if not topic.strip():
            st.error(t("enter_topic"))
        elif plan_subject == "other" and not other_subject_name:
            st.error(t("enter_subject_name"))
        elif ai_remaining <= 0:
            st.warning(t("explore_ai_limit_reached"))
        else:
            effective_subject = other_subject_name if plan_subject == "other" else plan_subject
            with st.spinner(t("generating")):
                try:
                    ai_plan = lp.generate_ai_lesson_plan(
                        subject=effective_subject,
                        learner_stage=learner_stage,
                        level_or_band=level_or_band,
                        lesson_purpose=lesson_purpose,
                        topic=topic.strip(),
                        plan_language=lp.get_plan_language(),
                        student_material_language=lp.get_student_material_language(effective_subject),
                    )
                    plan = lp.normalize_planner_output(ai_plan)
                    st.session_state["_explore_ai_used"] = ai_used + 1
                    st.session_state["explore_generated_plan"] = plan
                    st.session_state["explore_generated_plan_meta"] = {
                        "subject": effective_subject,
                        "learner_stage": learner_stage,
                        "level_or_band": level_or_band,
                        "lesson_purpose": lesson_purpose,
                        "topic": topic.strip(),
                        "mode": "ai",
                    }
                    st.session_state["explore_plan_warning"] = None
                except Exception as e:
                    st.error(f"{t('ai_unavailable_fallback')} ({e})")

    plan = st.session_state.get("explore_generated_plan")
    meta = st.session_state.get("explore_generated_plan_meta", {})
    if plan:
        resolved_mode = meta.get("mode", "template")
        warning_msg = st.session_state.get("explore_plan_warning")

        st.session_state["quick_lesson_plan_mode_used"] = resolved_mode
        st.session_state["quick_lesson_plan_warning"] = warning_msg

        render_quick_lesson_plan_result(
            plan,
            subject=meta.get("subject", ""),
            learner_stage=meta.get("learner_stage", ""),
            level_or_band=meta.get("level_or_band", ""),
            lesson_purpose=meta.get("lesson_purpose", ""),
            topic=meta.get("topic", ""),
            read_only=True,
            action_key_prefix="explore_plan",
        )

        if st.button(
            t("explore_save_plan_cta"),
            type="primary",
            use_container_width=True,
            key="btn_explore_save_plan",
        ):
            st.session_state["_pending_plan_after_signup"] = {
                "plan": plan,
                "meta": meta,
            }
            st.session_state["_explore_go_signup"] = True
            st.rerun()

def _render_plan_preview(plan: dict, meta: dict) -> None:
    """Renders a simplified read-only lesson plan preview."""
    import helpers.lesson_planner as lp

    st.markdown(f"### {t('plan_title')}: {plan.get('title', '')}")

    rec_level = plan.get("recommended_level", "")
    if rec_level:
        show_level = rec_level if rec_level in lp.LANGUAGE_LEVELS else t(rec_level)
        st.caption(f"{t('recommended_level')}: {show_level}")

    st.markdown(f"**{t('lesson_objective')}**")
    st.write(plan.get("objective", ""))

    st.markdown(f"**{t('success_criteria')}**")
    for item in plan.get("success_criteria", []):
        st.write(f"- {item}")

    st.markdown(f"**1. {t('warm_up')}**")
    for item in plan.get("warm_up", []):
        st.write(f"- {item}")

    st.markdown(f"**2. {t('main_activity')}**")
    for item in plan.get("main_activity", []):
        st.write(f"- {item}")

    st.markdown(f"**3. {t('guided_practice')}**")
    for item in plan.get("guided_practice", []):
        st.write(f"- {item}")

    st.markdown(f"**4. {t('freer_task')}**")
    for item in plan.get("freer_task", []):
        st.write(f"- {item}")

    st.markdown(f"**5. {t('wrap_up')}**")
    for item in plan.get("wrap_up", []):
        st.write(f"- {item}")

    st.markdown(f"**{t('teacher_moves')}**")
    for item in plan.get("teacher_moves", []):
        st.write(f"- {item}")


# ─────────────────────────────────────────────────────────────
# Income Goal Calculator — logged-in version (no CTA / signup)
# ─────────────────────────────────────────────────────────────
def render_income_goal_calculator() -> None:
    """Render the income goal calculator for logged-in users (expander)."""
    with st.expander(f"🎯 {t('income_goal_calculator')}", expanded=False):
        st.markdown(
            f"<p style='color:#475569;font-size:0.93rem;margin:0 0 8px 0;'>{t('explore_goal_subtitle')}</p>",
            unsafe_allow_html=True,
        )

        subject_labels = {
            "english": t("subject_english"),
            "spanish": t("subject_spanish"),
            "mathematics": t("subject_mathematics"),
            "science": t("subject_science"),
            "music": t("subject_music"),
            "study_skills": t("subject_study_skills"),
            "other": t("explore_other"),
        }
        subject = st.selectbox(
            t("explore_subject"),
            options=list(subject_labels.keys()),
            format_func=lambda k: subject_labels[k],
            key="ait_goal_subject",
        )

        if subject == "other":
            st.text_input(t("explore_other_subject_input"), key="ait_goal_custom_subject")

        modality_labels = {
            "online": t("explore_online"),
            "offline": t("explore_offline"),
            "both": t("explore_both"),
        }
        modality = st.radio(
            t("explore_modality"),
            options=list(modality_labels.keys()),
            format_func=lambda k: modality_labels[k],
            horizontal=True,
            key="ait_goal_modality",
        )

        # ── Target audience ──
        audience_labels = {
            "kids": t("audience_kids"),
            "teens": t("audience_teens"),
            "adults": t("audience_adults"),
        }
        audience = st.radio(
            t("target_audience"),
            options=list(audience_labels.keys()),
            format_func=lambda k: audience_labels[k],
            horizontal=True,
            key="ait_goal_audience",
        )

        # ── Education level ──
        education_labels = {
            "student": t("edu_student"),
            "bachelors": t("edu_bachelors"),
            "masters": t("edu_masters"),
            "doctorate": t("edu_doctorate"),
        }
        education = st.selectbox(
            t("education_level"),
            options=list(education_labels.keys()),
            format_func=lambda k: education_labels[k],
            key="ait_goal_education",
        )

        currency_options = list(CURRENCIES.keys())
        currency = st.selectbox(
            t("explore_currency"),
            options=currency_options,
            format_func=lambda c: f"{CURRENCIES[c]['symbol']}  {c} — {CURRENCIES[c]['name']}",
            key="ait_goal_currency",
        )

        sym = currency_symbol(currency)
        rate_subject = subject if subject != "other" else "english"
        if modality == "both":
            rate_min, rate_default, rate_max = _blended_range(rate_subject, currency, audience=audience, education=education)
        else:
            rate_min, rate_default, rate_max = _range_in_currency(rate_subject, modality, currency, audience=audience, education=education)

        step = max(1, round((rate_max - rate_min) / 40))
        hourly_rate = st.slider(
            t("explore_select_fee", sym=sym),
            min_value=rate_min, max_value=rate_max, value=rate_default,
            step=step, key="ait_goal_fee",
        )
        st.caption(t("explore_fee_hint"))

        goal_amount = st.number_input(
            t("explore_goal_amount", sym=sym),
            min_value=0, step=500, value=0,
            key="ait_goal_amount",
        )

        if st.button(t("explore_see_plan"), type="primary", use_container_width=True, key="ait_goal_btn"):
            if goal_amount <= 0:
                st.warning(t("explore_enter_amount"))
            else:
                st.session_state["ait_goal_ready"] = True

        if st.session_state.get("ait_goal_ready") and goal_amount > 0:
            total_hours = math.ceil(goal_amount / hourly_rate) if hourly_rate else 0
            hours_per_week = math.ceil(total_hours / _TEACHING_WEEKS_PER_YEAR) if _TEACHING_WEEKS_PER_YEAR else 0
            students_needed = math.ceil(hours_per_week / _LESSONS_PER_STUDENT_PER_WEEK) if _LESSONS_PER_STUDENT_PER_WEEK else 0

            formatted_rate = f"{sym} {hourly_rate:,}"
            formatted_goal = f"{sym} {goal_amount:,}"

            # --- Achievability scale ---
            if hours_per_week <= 24:
                achievability = f"<span style='color:#16a34a;font-weight:700;'>{t('explore_achievability_green')}</span>"
                advice = t('explore_advice_green')
            elif 25 <= hours_per_week <= 31:
                achievability = f"<span style='color:#eab308;font-weight:700;'>{t('explore_achievability_yellow')}</span>"
                advice = t('explore_advice_yellow')
            elif 32 <= hours_per_week <= 42:
                achievability = f"<span style='color:#f97316;font-weight:700;'>{t('explore_achievability_orange')}</span>"
                advice = t('explore_advice_orange')
            else:
                achievability = f"<span style='color:#dc2626;font-weight:700;'>{t('explore_achievability_red')}</span>"
                advice = t('explore_advice_red')
            st.markdown(
                f"""
                <div style="
                    background:linear-gradient(180deg,var(--panel),var(--panel-2));
                    border-radius:16px; padding:22px 20px;
                    border:1px solid var(--border);
                    box-shadow:var(--shadow-md);
                ">
                    <h4 style="margin:0 0 10px 0; color:var(--primary); font-size:1.15rem;">
                        📋 {t('explore_your_plan')}
                    </h4>
                    <table style="width:100%; border-collapse:collapse; font-size:0.97rem;">
                        <tr><td style="padding:6px 0; color:var(--muted);">{t('explore_plan_goal')}</td>
                            <td style="padding:6px 0; font-weight:700; text-align:right; color:var(--text);">{formatted_goal}</td></tr>
                        <tr><td style="padding:6px 0; color:var(--muted);">{t('explore_plan_rate')}</td>
                            <td style="padding:6px 0; font-weight:700; text-align:right; color:var(--text);">{formatted_rate}</td></tr>
                        <tr><td style="padding:6px 0; color:var(--muted);">{t('explore_plan_hours_year')}</td>
                            <td style="padding:6px 0; font-weight:700; text-align:right; color:var(--text);">{total_hours:,}</td></tr>
                        <tr><td style="padding:6px 0; color:var(--muted);">{t('explore_plan_hours_week')}</td>
                            <td style="padding:6px 0; font-weight:700; text-align:right; color:var(--text);">{hours_per_week}</td></tr>
                        <tr><td style="padding:6px 0; color:var(--muted);">{t('explore_achievability_label')}</td>
                            <td style="padding:6px 0; font-weight:700; text-align:right; color:var(--text);">{achievability}</td></tr>
                        <tr style="border-top:2px solid rgba(37,99,235,0.18);">
                            <td style="padding:10px 0 4px 0; color:var(--primary); font-weight:700; font-size:1.05rem;">{t('explore_plan_students')}</td>
                            <td style="padding:10px 0 4px 0; font-weight:800; text-align:right; color:var(--primary); font-size:1.15rem;">{students_needed}</td></tr>
                    </table>
                    <div style="margin:10px 0 0 0; color:var(--muted); font-size:0.92rem;"><b>{t('explore_advice_label')}</b> {advice}</div>
                    <p style="margin:12px 0 0 0; color:var(--muted); font-size:0.82rem;">{t('explore_plan_note')}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )