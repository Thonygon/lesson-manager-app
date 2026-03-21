import streamlit as st
from streamlit_option_menu import option_menu

from core.i18n import t
from core.navigation import go_to, PAGE_KEYS, _set_query
from auth.auth import sign_out_user
from styles.theme import _is_dark


def render_top_nav(active_page: str):
    current_lang = st.session_state.get("ui_lang", "en")
    if current_lang not in ("en", "es", "tr"):
        current_lang = "en"

    items = [
        ("home",        t("home"),      "house"),
        ("dashboard",   t("dashboard"), "bar-chart"),
        ("students",    t("students"),  "people"),
        ("add_lesson",  t("lesson"),    "calendar-event"),
        ("add_payment", t("payment"),   "credit-card"),
        ("calendar",    t("calendar"),  "calendar3"),
        ("analytics",   t("analytics"), "graph-up"),
        ("sign_out",    t("sign_out"),  "box-arrow-right"),
    ]

    keys   = [k for k, _, _ in items]
    labels = [label for _, label, _ in items]
    icons  = [icon for _, _, icon in items]

    try:
        default_index = keys.index(active_page)
    except ValueError:
        default_index = 0

    st.markdown(
        """
        <style>
        @media (max-width: 768px){
          .block-container{
            padding-left: 0.85rem !important;
            padding-right: 0.85rem !important;
          }
          .home-topbar{ padding: 8px 10px; }
          .home-hero{ padding: 18px 14px; }
          .home-menu-wrap{ padding: 12px; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    selected_label = option_menu(
        menu_title=None,
        options=labels,
        icons=icons,
        orientation="horizontal",
        default_index=default_index,
        key="top_nav_option_menu",
        styles={
            "container": {
                "padding": "0 !important",
                "margin": "0 0 1rem 0 !important",
                "background": "#0f172a" if _is_dark() else "transparent",
            },
            "icon": {
                "font-size": "16px",
                "color": "#60A5FA" if _is_dark() else "#2563EB",
                "transition": "all 200ms ease",
            },
            "nav-link": {
                "font-size": "0.875rem",
                "font-weight": "600",
                "text-align": "center",
                "margin": "0 6px 0 0",
                "padding": "0.65rem 1rem",
                "border-radius": "12px",
                "color": "#94a3b8" if _is_dark() else "#64748b",
                "background": "transparent" if _is_dark() else "rgba(255,255,255,0.5)",
                "border": "1px solid rgba(255,255,255,0.10)" if _is_dark() else "1px solid rgba(17,24,39,0.08)",
                "transition": "all 200ms cubic-bezier(0.4, 0, 0.2, 1)",
                "--hover-color": "rgba(96,165,250,0.18)" if _is_dark() else "#f1f5f9",
            },
            "nav-link-selected": {
                "background": "linear-gradient(180deg, #1e3a5f, #162844)" if _is_dark() else "linear-gradient(180deg, #eff6ff, #dbeafe)",
                "color": "#f1f5f9" if _is_dark() else "#1D4ED8",
                "border": "1px solid rgba(96,165,250,0.30)" if _is_dark() else "1px solid rgba(37,99,235,0.25)",
                "box-shadow": ("0 0 0 4px rgba(96,165,250,0.08)" if _is_dark() else "0 0 0 3px rgba(37,99,235,0.1), 0 4px 12px rgba(37,99,235,0.15)"),
                "transform": "translateY(-1px)",
            },
        },
    )

    selected_key = active_page
    for key, label, _ in items:
        if label == selected_label:
            selected_key = key
            break

    previous_key = st.session_state.get("top_nav_prev", active_page)

    if selected_key != previous_key:
        st.session_state["top_nav_prev"] = selected_key
        if selected_key == "sign_out":
            sign_out_user()
        elif selected_key != active_page:
            go_to(selected_key)
            st.rerun()


def route_pages(page: str):
    """Dispatch to the correct page renderer."""
    from pages.home import render_home
    from pages.page_dashboard import render_dashboard
    from pages.page_students import render_students
    from pages.page_add_lesson import render_add_lesson
    from pages.page_add_payment import render_add_payment
    from pages.page_calendar import render_calendar
    from pages.page_analytics import render_analytics
    from styles.theme import load_css_home, load_css_app_light

    if page == "home":
        load_css_home()
        render_home()
        st.stop()

    load_css_app_light(compact=bool(st.session_state.get("compact_mode", False)))
    render_top_nav(page)

    if page == "dashboard":
        render_dashboard()
    elif page == "students":
        render_students()
    elif page == "add_lesson":
        render_add_lesson()
    elif page == "add_payment":
        render_add_payment()
    elif page == "calendar":
        render_calendar()
    elif page == "analytics":
        render_analytics()
    else:
        go_to("home")
        st.rerun()
