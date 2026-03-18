import streamlit as st
from streamlit_option_menu import option_menu

from core.i18n import t
from core.navigation import go_to, PAGE_KEYS, _set_query
from auth.auth import sign_out_user


def render_top_nav(active_page: str):
    current_lang = st.session_state.get("ui_lang", "en")
    if current_lang not in ("en", "es"):
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
                "margin": "0 !important",
                "background": "transparent",
            },
            "icon": {"font-size": "16px", "color": "#2563EB"},
            "nav-link": {
                "font-size": "13px",
                "font-weight": "700",
                "text-align": "center",
                "margin": "0 4px 0 0",
                "padding": "10px 12px",
                "border-radius": "14px",
                "color": "#475569",
                "--hover-color": "#EEF4FF",
            },
            "nav-link-selected": {
                "background": "linear-gradient(180deg, #eff6ff, #eaf2ff)",
                "color": "#1D4ED8",
                "border": "1px solid rgba(37,99,235,0.22)",
                "box-shadow": "0 0 0 4px rgba(37,99,235,0.08)",
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
    from styles.theme import load_css_home_dark, load_css_app_light

    if page == "home":
        load_css_home_dark()
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
