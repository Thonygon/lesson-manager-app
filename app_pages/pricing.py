from __future__ import annotations

import html as _html

import streamlit as st

from core.i18n import t
from core.state import get_current_user_id
from helpers.currency import CURRENCIES, CURRENCY_CODES, get_exchange_rate, get_preferred_currency
from services.payment_service import create_checkout_session, payments_configured
from services.subscription_service import list_active_plans


def _money(plan: dict, currency_code: str | None = None) -> str:
    currency_code = str(currency_code or get_preferred_currency() or "USD")
    price = plan.get("price")
    if price is None:
        return "Custom"
    try:
        cents = int(price)
    except Exception:
        cents = 0
    if cents == 0:
        return "Free"
    base_amount = cents / 100
    converted_amount = base_amount * get_exchange_rate("USD", currency_code)
    symbol = CURRENCIES.get(currency_code, {}).get("symbol", currency_code)
    return f"{symbol}{converted_amount:,.0f}/{plan.get('billing_interval') or 'month'}"


def _limit(plan: dict, key: str) -> str:
    value = (plan.get("limits_json") or {}).get(key)
    return "Unlimited" if value is None else str(value)


def _plan_tagline(plan: dict) -> str:
    plan_id = str(plan.get("id") or "")
    if plan_id == "teacher_pro":
        return "For independent teachers ready to run Classio daily."
    if plan_id == "school":
        return "For teams, institutions, and multi-teacher administration."
    if plan_id == "beta_lifetime":
        return "Granted manually by Classio admins for beta and lifetime access."
    return "Start with Classio essentials and upgrade only when you need more power."


def _plan_cta(plan: dict) -> str:
    plan_id = str(plan.get("id") or "")
    if plan_id == "free":
        return "Current starter plan"
    if plan_id == "school":
        return "Contact / request school checkout"
    if plan_id == "beta_lifetime":
        return "Admin-assigned only"
    return "Start Pro checkout"


def _plan_feature_bullets(plan: dict) -> list[str]:
    features = dict(plan.get("features_json") or {})
    bullets: list[str] = []
    if features.get("ai_tools"):
        bullets.append(f"{_limit(plan, 'ai_generations')} AI generations")
    if features.get("pdf_export"):
        bullets.append(f"{_limit(plan, 'pdf_exports')} PDF exports")
    if features.get("word_export"):
        bullets.append(f"{_limit(plan, 'word_exports')} {t('pricing_word_exports_label').lower()}")
    bullets.append(f"{_limit(plan, 'students_count')} students")
    bullets.append(f"{_limit(plan, 'classes_count')} classes")
    if features.get("premium_tools"):
        bullets.append(t("pricing_premium_tools_included"))
    if features.get("school_admin"):
        bullets.append(t("pricing_school_admin_controls"))
    if str(plan.get("id") or "") == "beta_lifetime":
        bullets.append(t("pricing_lifetime_access"))
    return bullets[:5]


def _premium_tool_items(plan: dict) -> list[str]:
    features = dict(plan.get("features_json") or {})
    highlight_keys = list(features.get("premium_tool_highlights") or [])
    label_map = {
        "dashboard_insights": t("pricing_premium_tool_analytics"),
        "dashboard_reports": t("pricing_premium_tool_exports"),
        "students_progress_tools": t("pricing_premium_tool_recommendations"),
        "students_recommendations": t("pricing_premium_tool_recommendations"),
        "analytics_access": t("pricing_premium_tool_analytics"),
        "smart_tools_access": t("pricing_premium_tool_generic_1"),
        "smart_tools_worksheets": t("pricing_premium_tool_generic_1"),
        "smart_tools_exams": t("pricing_premium_tool_generic_1"),
        "smart_tools_lesson_plans": t("pricing_premium_tool_generic_2"),
        "smart_tools_learning_programs": t("pricing_premium_tool_learning_programs"),
        "smart_tools_goal_explorer": t("pricing_premium_tool_goal_explorer"),
        "smart_tools_student_personalization": t("pricing_premium_tool_personalization"),
        "pdf_export": t("pricing_premium_tool_exports"),
        "word_export": t("pricing_word_exports_included"),
    }
    if highlight_keys:
        ordered = []
        seen = set()
        for key in highlight_keys:
            label = label_map.get(str(key), "")
            if label and label not in seen:
                ordered.append(label)
                seen.add(label)
        return ordered
    items: list[str] = []
    if features.get("analytics_access"):
        items.append(t("pricing_premium_tool_analytics"))
    if features.get("students_recommendations"):
        items.append(t("pricing_premium_tool_recommendations"))
    if features.get("smart_tools_learning_programs"):
        items.append(t("pricing_premium_tool_learning_programs"))
    if features.get("smart_tools_goal_explorer"):
        items.append(t("pricing_premium_tool_goal_explorer"))
    if features.get("smart_tools_student_personalization"):
        items.append(t("pricing_premium_tool_personalization"))
    if features.get("dashboard_reports") or features.get("pdf_export"):
        items.append(t("pricing_premium_tool_exports"))
    if not items:
        items = [
            t("pricing_premium_tool_generic_1"),
            t("pricing_premium_tool_generic_2"),
            t("pricing_premium_tool_generic_3"),
        ]
    return items


def _premium_tools_help_text(plans: list[dict] | dict) -> str:
    plan_list = [plans] if isinstance(plans, dict) else list(plans or [])
    blocks: list[str] = [t("pricing_premium_tools_helper_caption")]
    for plan in plan_list:
        features = dict(plan.get("features_json") or {})
        if not features.get("premium_tools"):
            continue
        items = _premium_tool_items(plan)
        if not items:
            continue
        blocks.append(f"**{plan.get('name') or plan.get('id') or ''}**")
        blocks.extend([f"- {item}" for item in items])
    return "\n\n".join(blocks)


def _render_comparison_matrix(plans: list[dict], preview_currency: str) -> None:
    def _cell(text: str, kind: str = "value") -> str:
        return f"<div class='pricing-compare-cell pricing-compare-{kind}'>{_html.escape(text)}</div>"

    rows_html: list[str] = []
    header_cells = [_cell(t("pricing_compare_feature"), "label")]
    for plan in plans:
        header_cells.append(_cell(str(plan.get("name") or ""), "header"))
    rows_html.append(f"<div class='pricing-compare-row pricing-compare-header'>{''.join(header_cells)}</div>")

    metric_rows = [
        (t("pricing_compare_price"), lambda p: _money(p, preview_currency)),
        (t("pricing_ai_tools_label"), lambda p: t("pricing_yes") if (p.get("features_json") or {}).get("ai_tools") else t("pricing_no")),
        (t("pricing_ai_limit_label"), lambda p: _limit(p, "ai_generations")),
        (t("pricing_pdf_limit_label"), lambda p: _limit(p, "pdf_exports")),
        (t("pricing_word_export_limit_label"), lambda p: _limit(p, "word_exports")),
        (t("pricing_students_label"), lambda p: _limit(p, "students_count")),
        (t("pricing_classes_label"), lambda p: _limit(p, "classes_count")),
        (t("pricing_premium_tools_label"), lambda p: t("pricing_included_count", count=len(_premium_tool_items(p))) if (p.get("features_json") or {}).get("premium_tools") else t("pricing_no")),
        (t("pricing_school_admin_label"), lambda p: t("pricing_yes") if (p.get("features_json") or {}).get("school_admin") else t("pricing_no")),
    ]

    for label, getter in metric_rows:
        cells = [_cell(label, "label")]
        for plan in plans:
            cells.append(_cell(str(getter(plan))))
        rows_html.append(f"<div class='pricing-compare-row'>{''.join(cells)}</div>")

    st.markdown(
        """
        <style>
        .pricing-compare-wrap{
          border:1px solid rgba(15,23,42,.08);
          border-radius:20px;
          overflow:hidden;
          background:linear-gradient(180deg, rgba(255,255,255,.96), rgba(248,250,252,.98));
          box-shadow:0 20px 60px rgba(15,23,42,.06);
        }
        .pricing-compare-row{
          display:grid;
          grid-template-columns:minmax(180px,1.05fr) repeat(3, minmax(140px,1fr));
          border-top:1px solid rgba(15,23,42,.06);
        }
        .pricing-compare-header{
          border-top:none;
          background:linear-gradient(180deg, rgba(241,245,249,.92), rgba(248,250,252,.92));
        }
        .pricing-compare-cell{
          padding:14px 16px;
          font-size:14px;
          color:#334155;
        }
        .pricing-compare-label{
          font-weight:700;
          color:#0f172a;
        }
        .pricing-compare-header .pricing-compare-cell{
          font-weight:800;
          color:#0f172a;
          font-size:15px;
        }
        .pricing-compare-value{
          font-weight:600;
        }
        @media (max-width: 900px){
          .pricing-compare-row{
            grid-template-columns:minmax(130px,1fr) repeat(3, minmax(110px,1fr));
          }
          .pricing-compare-cell{
            padding:12px 10px;
            font-size:13px;
          }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(f"<div class='pricing-compare-wrap'>{''.join(rows_html)}</div>", unsafe_allow_html=True)


def render_plan_preview_cards(
    plans: list[dict],
    *,
    preview_currency: str | None = None,
    interactive: bool = True,
    key_prefix: str = "pricing",
    user_id: str | None = None,
    email: str = "",
    show_comparison: bool = True,
) -> None:
    preview_currency = str(preview_currency or get_preferred_currency() or "USD")
    cols = st.columns(len(plans) or 1)
    for idx, (col, plan) in enumerate(zip(cols, plans)):
        plan_id = str(plan.get("id") or "free")
        with col:
            st.markdown(f"### {plan.get('name', plan_id)}")
            st.markdown(f"## {_money(plan, preview_currency)}")
            st.write(_plan_tagline(plan))
            for feature in _plan_feature_bullets(plan):
                st.write(f"✓ {feature}")
            if (plan.get("features_json") or {}).get("premium_tools"):
                st.caption(
                    t("pricing_premium_tools_short_label"),
                    help=_premium_tools_help_text(plan),
                )

            if not interactive:
                st.button(_plan_cta(plan), key=f"{key_prefix}_preview_{plan_id}_{idx}", disabled=True, use_container_width=True)
                continue

            if plan_id == "free":
                st.info(t("pricing_free_plan_info"))
            elif plan_id == "school":
                st.info(t("pricing_school_plan_info"))
                if st.button(_plan_cta(plan), key=f"{key_prefix}_upgrade_{plan_id}_{idx}"):
                    st.session_state["school_plan_interest"] = True
                    st.success(t("pricing_school_interest_success"))
            else:
                if st.button(_plan_cta(plan), key=f"{key_prefix}_upgrade_{plan_id}_{idx}", type="primary"):
                    if not payments_configured():
                        st.warning(t("pricing_checkout_not_configured"))
                    else:
                        try:
                            url = create_checkout_session(user_id, email, plan_id)
                            st.link_button(t("pricing_continue_checkout"), url)
                        except Exception as exc:
                            st.error(str(exc))

    if not show_comparison:
        return

    st.divider()
    st.subheader(
        t("pricing_plan_comparison_title"),
        help=_premium_tools_help_text(plans),
    )
    _render_comparison_matrix(plans, preview_currency)


def render_pricing() -> None:
    st.title(t("pricing_title"))
    st.caption(t("pricing_caption"))

    if st.query_params.get("checkout") == "cancelled":
        st.warning(t("pricing_checkout_cancelled"))

    plans = [plan for plan in list_active_plans() if str(plan.get("id")) != "beta_lifetime"]
    user_id = get_current_user_id()
    email = str(st.session_state.get("user_email") or "")
    render_plan_preview_cards(
        plans,
        preview_currency=get_preferred_currency(),
        interactive=True,
        key_prefix="pricing",
        user_id=user_id,
        email=email,
        show_comparison=True,
    )

    st.info(t("pricing_admin_control_note"))
