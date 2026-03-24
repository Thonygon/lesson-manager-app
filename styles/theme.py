import streamlit as st

THEME_MODES = ("auto", "light", "dark")

def get_theme_mode() -> str:
    mode = str(st.session_state.get("ui_theme_mode", "auto")).strip().lower()
    if mode not in THEME_MODES:
        mode = "auto"
    st.session_state["ui_theme_mode"] = mode
    return mode

def set_theme_mode(mode: str) -> None:
    mode = str(mode or "auto").strip().lower()
    if mode not in THEME_MODES:
        mode = "auto"
    st.session_state["ui_theme_mode"] = mode

def _is_dark() -> bool:
    # Legacy compatibility only for places still importing it.
    # True only when the app is manually forced to dark.
    return get_theme_mode() == "dark"


def remove_streamlit_top_spacing():
    st.markdown(
        """
        <style>
        /* --- Remove Streamlit chrome --- */
        header, [data-testid="stHeader"] { display:none !important; height:0 !important; }
        [data-testid="stToolbar"] { display:none !important; height:0 !important; }
        div[data-testid="stDecoration"] { display:none !important; height:0 !important; }

        /* --- Kill top padding everywhere Streamlit may add it --- */
        html, body { margin:0 !important; padding:0 !important; }

        [data-testid="stAppViewContainer"] { padding-top:0 !important; margin-top:0 !important; }
        [data-testid="stMain"] { padding-top:0 !important; margin-top:0 !important; }

        /* Newer Streamlit main container */
        div[data-testid="stMainBlockContainer"]{
          padding-top: 0rem !important;
          margin-top: 0rem !important;
        }

        /* Some builds wrap it differently */
        section[data-testid="stMain"] > div {
          padding-top: 0rem !important;
          margin-top: 0rem !important;
        }

        /* Legacy */
        .block-container{
          padding-top: 0rem !important;
          margin-top: 0rem !important;
        }

        /* If Streamlit injects a top padding via inline style, force it off */
        div.block-container { padding-top: 0rem !important; }

        </style>
        """,
        unsafe_allow_html=True,
    )


def _root_vars() -> str:
    mode = st.session_state.get("ui_theme_mode", "auto")

    force_dark = mode == "dark"
    force_light = mode == "light"

    return f"""
      :root {{
        color-scheme: light dark;
      }}

      /* AUTO MODE */
      @media (prefers-color-scheme: dark) {{
        :root {{
          --bg-1:#0f172a; --bg-2:#1a2640; --bg-3:#162032;
          --bg:#0f172a;
          --text:#f1f5f9; --muted:#94a3b8;
          --panel:rgba(30,41,59,0.92); --panel-2:rgba(20,30,48,0.85);
          --panel-soft:#1e2d42;
          --border:rgba(255,255,255,0.08); --border-strong:rgba(255,255,255,0.14);
          --border2:rgba(255,255,255,0.10);
          --primary:#3B82F6; --primary-strong:#60A5FA; --primary-light:#60A5FA;
          --success:#34D399; --warning:#FBBF24; --danger:#F87171;
          --shadow:0 12px 28px rgba(0,0,0,0.30);
          --shadow-sm:0 2px 8px rgba(0,0,0,0.20);
          --shadow-md:0 12px 28px rgba(0,0,0,0.30);
          --shadow-lg:0 22px 55px rgba(0,0,0,0.40);
          --radius-xl:24px; --radius-lg:18px; --radius-md:14px;
          --platform-card-bg:#1e2b3f; --platform-card-border:rgba(96,165,250,0.22);
          --platform-card-hover-bg:#243450; --platform-card-hover-border:#60a5fa;
        }}

        html, body {{
          color-scheme: dark;
        }}
      }}

      @media (prefers-color-scheme: light) {{
        :root {{
          --bg-1:#f5f7fb; --bg-2:#f8faff; --bg-3:#eef4ff;
          --bg:#f5f7fb;
          --text:#0f172a; --muted:#475569;
          --panel:rgba(255,255,255,0.88); --panel-2:rgba(255,255,255,0.72);
          --panel-soft:#fbfcff;
          --border:rgba(17,24,39,0.08); --border-strong:rgba(17,24,39,0.12);
          --border2:rgba(17,24,39,0.10);
          --primary:#2563EB; --primary-strong:#1D4ED8; --primary-light:#3B82F6;
          --success:#10B981; --warning:#F59E0B; --danger:#EF4444;
          --shadow:0 12px 28px rgba(15,23,42,0.08);
          --shadow-sm:0 2px 8px rgba(15,23,42,0.04);
          --shadow-md:0 12px 28px rgba(15,23,42,0.08);
          --shadow-lg:0 22px 55px rgba(15,23,42,0.10);
          --radius-xl:24px; --radius-lg:18px; --radius-md:14px;
          --platform-card-bg:#eff6ff; --platform-card-border:rgba(59,130,246,0.25);
          --platform-card-hover-bg:#dbeafe; --platform-card-hover-border:#3b82f6;
        }}

        html, body {{
          color-scheme: light;
        }}
      }}

      /* MANUAL OVERRIDE: DARK */
      {"html, body, :root { color-scheme: dark !important; }" if force_dark else ""}
      {" :root { --bg-1:#0f172a; --bg-2:#1a2640; --bg-3:#162032; --bg:#0f172a; --text:#f1f5f9; --muted:#94a3b8; --panel:rgba(30,41,59,0.92); --panel-2:rgba(20,30,48,0.85); --panel-soft:#1e2d42; --border:rgba(255,255,255,0.08); --border-strong:rgba(255,255,255,0.14); --border2:rgba(255,255,255,0.10); --primary:#3B82F6; --primary-strong:#60A5FA; --primary-light:#60A5FA; --success:#34D399; --warning:#FBBF24; --danger:#F87171; --shadow:0 12px 28px rgba(0,0,0,0.30); --shadow-sm:0 2px 8px rgba(0,0,0,0.20); --shadow-md:0 12px 28px rgba(0,0,0,0.30); --shadow-lg:0 22px 55px rgba(0,0,0,0.40); --radius-xl:24px; --radius-lg:18px; --radius-md:14px; --platform-card-bg:#1e2b3f; --platform-card-border:rgba(96,165,250,0.22); --platform-card-hover-bg:#243450; --platform-card-hover-border:#60a5fa; }" if force_dark else ""}

      /* MANUAL OVERRIDE: LIGHT */
      {"html, body, :root { color-scheme: light !important; }" if force_light else ""}
      {" :root { --bg-1:#f5f7fb; --bg-2:#f8faff; --bg-3:#eef4ff; --bg:#f5f7fb; --text:#0f172a; --muted:#475569; --panel:rgba(255,255,255,0.88); --panel-2:rgba(255,255,255,0.72); --panel-soft:#fbfcff; --border:rgba(17,24,39,0.08); --border-strong:rgba(17,24,39,0.12); --border2:rgba(17,24,39,0.10); --primary:#2563EB; --primary-strong:#1D4ED8; --primary-light:#3B82F6; --success:#10B981; --warning:#F59E0B; --danger:#EF4444; --shadow:0 12px 28px rgba(15,23,42,0.08); --shadow-sm:0 2px 8px rgba(15,23,42,0.04); --shadow-md:0 12px 28px rgba(15,23,42,0.08); --shadow-lg:0 22px 55px rgba(15,23,42,0.10); --radius-xl:24px; --radius-lg:18px; --radius-md:14px; --platform-card-bg:#eff6ff; --platform-card-border:rgba(59,130,246,0.25); --platform-card-hover-bg:#dbeafe; --platform-card-hover-border:#3b82f6; }" if force_light else ""}
    """

def _dark_widget_css() -> str:
    mode = get_theme_mode()

    dark_rules = """
      /* ── Background ── */
      html, body,
      .stApp,
      [data-testid="stAppViewContainer"] {
        background-color: var(--bg-1) !important;
      }
      .stApp {
        background:
          radial-gradient(900px 420px at 0% 0%, rgba(59,130,246,0.10), transparent 55%),
          radial-gradient(700px 380px at 100% 0%, rgba(52,211,153,0.07), transparent 58%),
          linear-gradient(180deg, var(--bg-2) 0%, var(--bg-1) 100%) !important;
        color: var(--text) !important;
      }

      .stApp, .stApp * {
        color: var(--text);
        -webkit-text-fill-color: var(--text);
      }
      .stMarkdown p, .stMarkdown li, .stCaption, .stCaption * {
        color: var(--muted) !important;
        -webkit-text-fill-color: var(--muted) !important;
      }
      .stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4 {
        color: var(--text) !important;
        -webkit-text-fill-color: var(--text) !important;
      }
      label, label * {
        color: var(--text) !important;
        -webkit-text-fill-color: var(--text) !important;
      }

      div[data-testid="stVerticalBlockBorderWrapper"] {
        background: #1a2535 !important;
        border: 1px solid rgba(255,255,255,0.10) !important;
        border-radius: 18px !important;
        box-shadow: 0 4px 18px rgba(0,0,0,0.35) !important;
      }
      div[data-testid="stVerticalBlockBorderWrapper"] *,
      div[data-testid="stVerticalBlockBorderWrapper"] p,
      div[data-testid="stVerticalBlockBorderWrapper"] span,
      div[data-testid="stVerticalBlockBorderWrapper"] li {
        color: var(--text) !important;
        -webkit-text-fill-color: var(--text) !important;
      }

      div[data-testid="metric-container"] {
        background: #1a2535 !important;
        border: 1px solid rgba(255,255,255,0.10) !important;
        border-radius: 18px !important;
        box-shadow: 0 4px 18px rgba(0,0,0,0.30) !important;
      }
      div[data-testid="metric-container"] * {
        color: var(--text) !important;
        -webkit-text-fill-color: var(--text) !important;
      }

      div[data-testid="stButton"] button,
      div[data-testid="stLinkButton"] a,
      button[kind="primary"],
      button[kind="secondary"] {
        background: #253349 !important;
        color: #f1f5f9 !important;
        -webkit-text-fill-color: #f1f5f9 !important;
        border: 1px solid rgba(255,255,255,0.14) !important;
        border-radius: 14px !important;
        font-weight: 700 !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.25) !important;
      }
      div[data-testid="stButton"] button *,
      div[data-testid="stLinkButton"] a * {
        color: #f1f5f9 !important;
        -webkit-text-fill-color: #f1f5f9 !important;
      }
      div[data-testid="stButton"] button:hover,
      div[data-testid="stLinkButton"] a:hover {
        background: #2e3f58 !important;
        border-color: rgba(96,165,250,0.40) !important;
        transform: translateY(-1px);
      }

      div[data-testid="stFormSubmitButton"] button,
      div[data-testid="stDownloadButton"] button {
        background: #253349 !important;
        color: #f1f5f9 !important;
        -webkit-text-fill-color: #f1f5f9 !important;
        border: 1px solid rgba(255,255,255,0.14) !important;
      }

      div[data-testid="stTextInput"] input,
      div[data-testid="stTextArea"] textarea,
      div[data-testid="stNumberInput"] input,
      div[data-testid="stDateInput"] input {
        background: #1e293b !important;
        color: #f1f5f9 !important;
        -webkit-text-fill-color: #f1f5f9 !important;
        border-color: rgba(255,255,255,0.14) !important;
      }

      div[data-testid="stSelectbox"] [data-baseweb="select"] > div,
      div[data-testid="stMultiSelect"] [data-baseweb="select"] > div {
        background: #1e293b !important;
        color: #f1f5f9 !important;
        -webkit-text-fill-color: #f1f5f9 !important;
        border-color: rgba(255,255,255,0.14) !important;
      }
      [data-baseweb="popover"] [role="listbox"],
      [data-baseweb="menu"] { background: #1e293b !important; }
      [data-baseweb="option"] { background: #1e293b !important; color: #f1f5f9 !important; }
      [data-baseweb="option"]:hover,
      [data-baseweb="option"][aria-selected="true"] { background: #273549 !important; }

      [data-baseweb="tab-list"] {
        background: transparent !important;
        border-bottom-color: rgba(255,255,255,0.10) !important;
      }
      [data-baseweb="tab"] {
        color: #94a3b8 !important;
        -webkit-text-fill-color: #94a3b8 !important;
      }
      [data-baseweb="tab"][aria-selected="true"] {
        color: #f1f5f9 !important;
        -webkit-text-fill-color: #f1f5f9 !important;
      }

      [data-testid="stForm"] {
        background: #1a2535 !important;
        border-color: rgba(255,255,255,0.10) !important;
      }

      .kpi-stat-card {
        background: #1a2535 !important;
        border-color: transparent !important;
      }
      .kpi-stat-value { color: #f1f5f9 !important; }
      .kpi-stat-label { color: #94a3b8 !important; }

      .dark-card {
        background: #1a2535 !important;
        border-color: rgba(255,255,255,0.10) !important;
        color: var(--text) !important;
      }

      div[data-testid="stDataFrame"] {
        background: #1a2535 !important;
        border-color: rgba(255,255,255,0.10) !important;
      }

      div[data-testid="stPopover"] > div > div {
        background: #1a2535 !important;
        border-color: rgba(255,255,255,0.10) !important;
      }

      h1, h2, h3, h4, h5, h6,
      [data-testid="stHeadingWithActionElements"] * {
        color: #f1f5f9 !important;
        -webkit-text-fill-color: #f1f5f9 !important;
      }

      div[data-testid="stHorizontalBlock"] button,
      [data-testid="stNavLink"] {
        color: #94a3b8 !important;
        -webkit-text-fill-color: #94a3b8 !important;
      }

      div[role="dialog"],
      div[data-testid="stDialog"],
      div[data-testid="stModal"] > div {
        background: #1a2535 !important;
        border: 1px solid rgba(255,255,255,0.10) !important;
        color: #f1f5f9 !important;
      }
      div[role="dialog"] *,
      div[data-testid="stDialog"] *,
      div[data-testid="stModal"] * {
        color: #f1f5f9 !important;
        -webkit-text-fill-color: #f1f5f9 !important;
      }

      [data-testid="stFileUploader"],
      [data-testid="stFileUploaderDropzone"] {
        background: #1e293b !important;
        border-color: rgba(255,255,255,0.14) !important;
      }
      [data-testid="stFileUploaderDropzone"] *,
      [data-testid="stFileUploaderDropzone"] span,
      [data-testid="stFileUploaderDropzone"] small,
      [data-testid="stFileUploaderDropzone"] p {
        color: #f1f5f9 !important;
        -webkit-text-fill-color: #f1f5f9 !important;
      }
    """

    if mode == "light":
        return ""

    if mode == "dark":
        return f"<style>{dark_rules}</style>"

    return f"<style>@media (prefers-color-scheme: dark) {{{dark_rules}}}</style>"

def _resource_cards_css() -> str:
    return """
      /* ---------- Shared resource cards ---------- */
      .cm-resource-card{
        background: linear-gradient(180deg, var(--panel, rgba(255,255,255,0.96)), var(--panel-2, rgba(248,250,255,0.92)));
        border: 1px solid var(--border-strong, rgba(17,24,39,0.08));
        border-left: 5px solid #60A5FA;
        border-radius: 20px;
        padding: 16px;
        box-shadow: var(--shadow-md);
        margin-bottom: 0.45rem;
        min-height: 210px;
      }

      .cm-resource-plan{
        border-left-color: #60A5FA;
      }

      .cm-resource-worksheet{
        border-left-color: #A78BFA;
      }

      .cm-resource-card__title{
        font-size: 1.02rem;
        font-weight: 800;
        line-height: 1.3;
        color: var(--text);
        margin-bottom: 10px;
      }

      .cm-resource-chip-row{
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-bottom: 12px;
      }

      .cm-resource-chip{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        border-radius: 999px;
        padding: 5px 10px;
        font-size: 0.76rem;
        font-weight: 700;
        white-space: nowrap;
        color: var(--text);
        background: rgba(96,165,250,0.10);
        border: 1px solid rgba(96,165,250,0.18);
      }

      .cm-resource-worksheet .cm-resource-chip{
        background: rgba(167,139,250,0.10);
        border: 1px solid rgba(167,139,250,0.18);
      }

      .cm-resource-preview{
        background: rgba(148,163,184,0.08);
        border-radius: 14px;
        padding: 12px;
        font-size: 0.84rem;
        line-height: 1.45;
        color: var(--text);
        min-height: 72px;
        margin-bottom: 10px;
      }

      .cm-resource-meta{
        font-size: 0.78rem;
        color: var(--muted);
        margin-top: 4px;
      }

      @media (max-width: 768px){
        .cm-resource-card{
          min-height: auto;
          padding: 14px;
          border-radius: 18px;
        }

        .cm-resource-card__title{
          font-size: 0.96rem;
        }

        .cm-resource-preview{
          min-height: auto;
        }
      }
    """

def load_css_home():
    st.markdown(f"<style>{_root_vars()}</style>", unsafe_allow_html=True)
    st.markdown(
        """
        <style>

        * { box-sizing: border-box; }

        html, body, .stApp,
        [data-testid="stAppViewContainer"],
        section[data-testid="stMain"],
        section[data-testid="stMain"] > div,
        div.block-container{
          overflow-x:hidden !important;
          padding: 0.2rem !important;
          max-width:100% !important;
        }

        html, body, [class*="css"]{
          font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
        }

        .stApp{
          background:
            radial-gradient(900px 420px at 0% 0%, rgba(37,99,235,0.06), transparent 55%),
            radial-gradient(700px 380px at 100% 0%, rgba(16,185,129,0.05), transparent 58%),
            linear-gradient(180deg, var(--bg-2) 0%, var(--bg-1) 100%);
          color: var(--text);
          min-height:100vh;
        }

        html, body { background: var(--bg-1) !important; }
        [data-testid="stAppViewContainer"] { background: transparent !important; }

        header { display:none !important; }
        div[data-testid="stDecoration"] { display:none !important; }

        section[data-testid="stMain"] > div{
          max-width: 1120px;
          padding-top: 0rem !important;
          padding-bottom: 0rem !important;
        }

        .block-container{
          padding-top: 0rem !important;
          padding-bottom: 0rem !important;
          padding-left: 1rem !important;
          padding-right: 1rem !important;
          margin-top: 0rem !important;
        }

        section[data-testid="stMain"]{
          padding-top: 0rem !important;
        }

        [data-testid="stAppViewContainer"] > .main{
          padding-top: 0rem !important;
        }

        header[data-testid="stHeader"]{
          display:none;
        }

        a { text-decoration:none !important; }
        /* ---------- Shared layout shells ---------- */
        .home-shell{
          max-width: 760px;
          margin: 0px auto;
          padding:0px 0 0px 0;
        }

        .home-panel{
          background: linear-gradient(180deg, var(--panel), var(--panel-2));
          border: 1px solid var(--border);
          border-radius: var(--radius-xl);
          box-shadow: var(--shadow-md);
          backdrop-filter: blur(14px);
          -webkit-backdrop-filter: blur(14px);
        }

        .home-panel-soft{
          background: linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.035));
          border: 1px solid var(--border);
          border-radius: var(--radius-lg);
          box-shadow: var(--shadow-md);
          backdrop-filter: blur(12px);
          -webkit-backdrop-filter: blur(12px);
        }

        /* ---------- Top bar ---------- */
        .home-topbar{
          padding: 0px 0px;
          margin-bottom: 12px;
          border-radius: 18px;
          border: 1px solid var(--border);
          background: linear-gradient(180deg, rgba(255,255,255,0.07), rgba(255,255,255,0.04));
          box-shadow: var(--shadow-md);
        }

        .home-topbar-name{
          font-size: 1rem;
          font-weight: 800;
          color: var(--text);
          line-height: 1.15;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .home-topbar-sub{
          font-size: 0.78rem;
          font-weight: 700;
          color: var(--muted);
          text-transform: uppercase;
          letter-spacing: 0.05em;
          margin-bottom: 2px;
        }
        .home-topbar-main{
          display:flex;
          align-items:center;
          justify-content:space-between;
          gap:14px;
          padding: 14px 18px;
        }

        .home-topbar-left{
          display:flex;
          align-items:center;
          gap:12px;
          min-width:0;
          flex:1 1 auto;
        }

        .home-topbar-usertext{
          min-width:50%;
        }

        .home-topbar-brand{
          flex:0 0 auto;
          text-align:left;
          font-size: 1.25rem;
          font-weight: 800;
          letter-spacing: -0.03em;
          color: var(--primary-strong);
          white-space: nowrap;
        }

        /* ---------- Titles ---------- */
        .home-title{
          text-align:center;
          font-size: clamp(2.0rem, 3.2vw, 2.8rem);
          font-weight: 900;
          letter-spacing: -0.04em;
          color: var(--text);
          margin: 10px 0 12px 0;
        }

        .home-hero{
          padding: 22px 18px;
          margin: 12px 0 16px 0;
          border-radius: var(--radius-xl);
          background:
            radial-gradient(420px 180px at 10% 0%, rgba(59,130,246,0.18), transparent 60%),
            radial-gradient(420px 180px at 90% 0%, rgba(52,211,153,0.14), transparent 60%),
            linear-gradient(180deg, rgba(255,255,255,0.08), rgba(255,255,255,0.04));
          border: 1px solid var(--border);
          box-shadow: var(--shadow-md);
          text-align: center;
        }

        .home-slogan{
          font-size: clamp(1.45rem, 2.3vw, 2rem);
          font-weight: 900;
          letter-spacing: -0.03em;
          margin-bottom: 8px;
          color: var(--text);
        }

        .home-sub{
          color: var(--muted);
          font-size: 1rem;
          line-height: 1.45;
          margin: 0;
        }

        /* ---------- External links ---------- */
        .home-links{
          margin: 16px 0 10px 0;
        }

        .home-links-row{
          display:flex;
          gap:12px;
          overflow-x:auto;
          overflow-y:hidden;
          padding: 4px 2px 12px 2px;
          scrollbar-width:none;
          -webkit-overflow-scrolling: touch;
          overscroll-behavior-x: contain;
          touch-action: pan-x;
        }

        .home-links-row::-webkit-scrollbar{
          display:none;
        }

        .home-linkchip{
          flex: 0 0 210px;
          display:flex;
          align-items:center;
          justify-content:center;
          gap:10px;
          padding: 14px 14px;
          border-radius: 16px;
          color:var(--muted);
          font-weight:800;
          background: linear-gradient(180deg, rgba(255,255,255,0.08), rgba(255,255,255,0.04));
          border:1px solid var(--border);
          box-shadow: var(--shadow-md);
        }

        .home-linkchip .dot{
          width:10px;
          height:10px;
          border-radius:999px;
          background: var(--primary);
          box-shadow: 0 0 0 5px rgba(96,165,250,0.16);
          display:inline-block;
        }

        div[data-testid="stExpander"]{
          border-radius:16px;
          border:1px solid var(--border);
          background:linear-gradient(180deg,var(--panel),var(--panel-2));
          box-shadow:var(--shadow-md);
          transition: all 250ms ease;
        }}

        div[data-testid="stExpander"]:hover {{
          box-shadow:var(--shadow-lg);
          border-color:rgba(59,130,246,0.2);
        }}

        div[data-testid="stExpander"] summary {{
          font-weight: 600;
          font-size: 0.95rem;
          padding: 0.9rem 1.1rem;
        }}

        div[data-testid="stExpander"] details[open] {{
          padding-bottom: 0.5rem;
        }}

        /* ---------- Section divider ---------- */
        .home-section-line{
          display:flex;
          align-items:center;
          justify-content:center;
          gap:14px;
          margin: 20px 0 14px 0;
          width:100%;
        }

        .home-section-line::before,
        .home-section-line::after{
          content:"";
          flex:1 1 auto;
          height:1px;
          border-radius:999px;
        }

        .home-section-line::before{
          background: linear-gradient(
            90deg,
            rgba(255,255,255,0.00) 0%,
            rgba(255,255,255,0.16) 20%,
            rgba(96,165,250,0.30) 100%
          );
        }

        .home-section-line::after{
          background: linear-gradient(
            90deg,
            rgba(96,165,250,0.30) 0%,
            rgba(255,255,255,0.16) 80%,
            rgba(255,255,255,0.00) 100%
          );
        }

        .home-section-line span{
          flex:0 0 auto;
          text-align:center;
          font-size: 0.95rem;
          font-weight: 800;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          color: var(--muted);
          white-space: nowrap;
        }

        /* ---------- Labels ---------- */
        .home-menu-note{
          text-align:center;
          color: var(--muted);
          font-size: 0.95rem;
          margin-bottom: 10px;
        }

        /* ---------- Home menu container ---------- */
        .home-menu-wrap{
          padding: 16px;
          margin-top: 10px;
          border-radius: var(--radius-xl);
          background: linear-gradient(180deg, rgba(255,255,255,0.08), rgba(255,255,255,0.04));
          border: 1px solid var(--border);
          box-shadow: var(--shadow-md);
        }

        /* ---------- Small utility cards ---------- */
        .home-mini-card{
          padding: 14px;
          border-radius: 16px;
          background: linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.03));
          border: 1px solid var(--border);
          box-shadow: var(--shadow-md);
          text-align:center;
        }

        .home-mini-title{
          font-size: 0.82rem;
          color: var(--muted);
          font-weight: 800;
          text-transform: uppercase;
          letter-spacing: 0.06em;
          margin-bottom: 6px;
        }

        .home-mini-value{
          font-size: 1.08rem;
          font-weight: 900;
          color: var(--text);
        }

        /* ---------- Badge-like pills ---------- */
        .home-chip{
          display:inline-flex;
          align-items:center;
          justify-content:center;
          padding: 8px 12px;
          border-radius: 999px;
          border: 1px solid var(--border);
          background: rgba(255,255,255,0.06);
          color: var(--muted);
          font-weight: 750;
          font-size: 0.9rem;
        }

        /* ---------- Avatar ---------- */
        .home-avatar{
          aspect-ratio:1 / 1;
          border-radius:50%;
          overflow:hidden;
          flex-shrink:0;
          display:block;
          border:3px solid rgba(255,255,255,255);
          box-shadow:0 8px 20px rgba(0,0,0,0.25);
          background-repeat:no-repeat;
          background-size:cover !important;
          background-position:center center !important;
          background-color:#0f172a;
        }

        .home-avatar-lg{
          width:85px;
          height:85px;
          min-width:85px;
        }

        .home-avatar-sm{
          width:52px;
          height:52px;
          min-width:52px;
        }

        /* ---------- Horizontal scroll action buttons ---------- */
        .home-actions{
          display:flex;
          gap:12px;
          overflow-x:auto;
          overflow-y:hidden;
          padding:4px 0 10px 0;
          scrollbar-width:none;
          -webkit-overflow-scrolling: touch;
        }

        .home-actions::-webkit-scrollbar{
          display:none;
        }

        .home-actions > div{
          flex:0 0 120px;
        }

        /* ---------- Neon animation helper ---------- */
        @keyframes homeNeonPulse {
          0%, 100% {
            transform: translateY(0);
            filter: brightness(1);
          }
          50% {
            transform: translateY(-1px);
            filter: brightness(1.03);
          }
        }

        /* ---------- Bottom safe spacing ---------- */
        .home-bottom-space{
          height: 22px;
        }

        /* ---------- Mobile ---------- */
        @media (max-width: 768px){
          .block-container{
            padding-left: 0.85rem !important;
            padding-right: 0.85rem !important;
          }

          .home-topbar{
            padding: 14px 10px;
          }

          .home-topbar-main{
            flex-direction: column;
            align-items: flex-start;
            gap: 10px;
          }

          .home-topbar-brand{
            width: 45%;
            text-align: left;
            white-space: normal;
          }

          .home-hero{
            padding: 18px 14px;
          }

          .home-hero-card{
            padding:16px;
          }

          .home-menu-wrap{
            padding: 12px;
          }
        }

        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(f"<style>{_resource_cards_css()}</style>", unsafe_allow_html=True)

    st.markdown(_dark_widget_css(), unsafe_allow_html=True)

def load_css_app(compact: bool = False):
    _resource_css = _resource_cards_css()
    compact_css = """
        section[data-testid="stMain"] > div {
          padding-top: 0rem !important;
          padding-bottom: 1.0rem !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]{
          padding: 12px !important;
          border-radius: 16px !important;
        }
        div[data-testid="stButton"] button{
          padding: 0.58rem 0.85rem !important;
          border-radius: 14px !important;
        }
        div[data-testid="metric-container"]{
          padding: 12px 14px !important;
          border-radius: 16px !important;
        }
    """ if compact else ""

    st.markdown(f"<style>{_root_vars()}</style>", unsafe_allow_html=True)
    st.markdown(
        f"""
        <style>
        * {{ box-sizing: border-box; }}

        html, body,
        .stApp,
        [data-testid="stAppViewContainer"],
        section[data-testid="stMain"],
        section[data-testid="stMain"] > div,
        div.block-container {{
          overflow-x:hidden !important;
          max-width:100% !important;
        }}

        .stApp {{
          background:
            radial-gradient(900px 420px at 0% 0%, rgba(37,99,235,0.06), transparent 55%),
            linear-gradient(180deg, var(--bg-2) 0%, var(--bg) 100%) !important;
          color: var(--text) !important;
        }}

        [data-testid="stAppViewContainer"] {{
          background: transparent !important;
        }}

        .stApp, .stApp * {{
          color: var(--text);
          -webkit-text-fill-color: var(--text) !important;
        }}

        .stCaption, .stMarkdown p, .stMarkdown span, .stMarkdown li {{
          color: var(--muted) !important;
          -webkit-text-fill-color: var(--muted) !important;
        }}

        .stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4 {{
          color: var(--text) !important;
          -webkit-text-fill-color: var(--text) !important;
        }}

        label, label * {{
          color: var(--text) !important;
          -webkit-text-fill-color: var(--text) !important;
        }}

        section[data-testid="stMain"] > div {{
          padding-top: 1.2rem;
          padding-bottom: 2rem;
          max-width: 1200px;
        }}

        html, body, [class*="css"]{{
          font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
        }}

        h1, h2, h3 {{
          letter-spacing: -0.02em;
          font-weight: 800;
        }}

        h1 {{
          font-size: 2rem;
          margin-bottom: 0.75rem;
        }}

        h2 {{
          font-size: 1.5rem;
          margin-bottom: 0.6rem;
          margin-top: 1.5rem;
        }}

        h3 {{
          font-size: 1.25rem;
          margin-bottom: 0.5rem;
          margin-top: 1.25rem;
        }}

        .stMarkdown {{
          line-height: 1.6;
        }}

        div[data-testid="stVerticalBlockBorderWrapper"] {{
          background: linear-gradient(180deg, var(--panel), var(--panel-2)) !important;
          border: 1px solid var(--border) !important;
          border-radius: 16px !important;
          padding: 1.25rem !important;
          box-shadow: var(--shadow) !important;
          transition: all 250ms ease;
        }}

        div[data-testid="stVerticalBlockBorderWrapper"]:hover {{
          box-shadow: var(--shadow-lg) !important;
          border-color: rgba(37,99,235,0.15) !important;
        }}

        div[data-testid="metric-container"] {{
          background: linear-gradient(180deg, var(--panel), var(--panel-2)) !important;
          border: 1px solid var(--border) !important;
          padding: 1rem 1.2rem !important;
          border-radius: 16px !important;
          box-shadow: var(--shadow) !important;
          transition: all 250ms ease;
        }}

        div[data-testid="metric-container"]:hover {{
          transform: translateY(-2px);
          box-shadow: var(--shadow-lg) !important;
        }}

        div[data-testid="stButton"] button {{
          border-radius: 12px !important;
          padding: 0.7rem 1.2rem !important;
          border: 1px solid var(--border2) !important;
          background: linear-gradient(180deg, var(--panel), var(--panel-2)) !important;
          color: var(--text) !important;
          -webkit-text-fill-color: var(--text) !important;
          font-weight: 600 !important;
          font-size: 0.95rem !important;
          transition: all 200ms cubic-bezier(0.4, 0, 0.2, 1);
          box-shadow: var(--shadow-sm);
          cursor: pointer !important;
        }}

        div[data-testid="stButton"] button:hover {{
          transform: translateY(-2px);
          border-color: rgba(37,99,235,0.3) !important;
          background: linear-gradient(180deg, var(--panel-soft), var(--panel)) !important;
          box-shadow:
            0 0 0 3px rgba(37,99,235,0.08),
            0 12px 24px rgba(15,23,42,0.08);
        }}

        div[data-testid="stButton"] button:active {{
          transform: translateY(0);
          transition: all 100ms;
        }}

        div[data-testid="stLinkButton"] a {{
          border-radius: 12px !important;
          padding: 0.7rem 1.2rem !important;
          border: 1px solid var(--border2) !important;
          background: linear-gradient(180deg, var(--panel), var(--panel-2)) !important;
          color: var(--text) !important;
          -webkit-text-fill-color: var(--text) !important;
          font-weight: 600 !important;
          font-size: 0.95rem !important;
          transition: all 200ms cubic-bezier(0.4, 0, 0.2, 1);
          box-shadow: var(--shadow-sm);
          text-decoration: none !important;
        }}

        div[data-testid="stLinkButton"] a:hover {{
          transform: translateY(-2px);
          border-color: rgba(37,99,235,0.3) !important;
          background: linear-gradient(180deg, var(--panel-soft), var(--panel)) !important;
          box-shadow:
            0 0 0 3px rgba(37,99,235,0.08),
            0 12px 24px rgba(15,23,42,0.08);
        }}

        div[data-testid="stTextInput"] input,
        div[data-testid="stTextArea"] textarea,
        div[data-testid="stNumberInput"] input,
        div[data-testid="stDateInput"] input {{
          border-radius: 12px !important;
          background: var(--panel-soft) !important;
          border: 1.5px solid var(--border2) !important;
          color: var(--text) !important;
          -webkit-text-fill-color: var(--text) !important;
          padding: 0.65rem 0.9rem !important;
          font-size: 0.95rem !important;
          transition: all 200ms ease;
        }}

        div[data-testid="stTextInput"] input:focus,
        div[data-testid="stTextArea"] textarea:focus,
        div[data-testid="stNumberInput"] input:focus,
        div[data-testid="stDateInput"] input:focus {{
          border-color: var(--primary-light) !important;
          box-shadow: 0 0 0 3px rgba(37,99,235,0.1) !important;
          outline: none !important;
        }}

        div[data-testid="stSelectbox"] [data-baseweb="select"] > div {{
          border-radius: 12px !important;
          background: var(--panel-soft) !important;
          border: 1.5px solid var(--border2) !important;
          color: var(--text) !important;
          -webkit-text-fill-color: var(--text) !important;
          transition: all 200ms ease;
        }}

        div[data-testid="stSelectbox"] [data-baseweb="select"] > div:focus-within {{
          border-color: var(--primary-light) !important;
          box-shadow: 0 0 0 3px rgba(37,99,235,0.1) !important;
        }}

        .stRadio, .stRadio *, .stToggle, .stToggle * {{
          color: var(--text) !important;
          -webkit-text-fill-color: var(--text) !important;
        }}

        div[data-testid="stDataFrame"] {{
          border-radius: 18px !important;
          overflow: hidden !important;
          border: 1px solid var(--border) !important;
          box-shadow: var(--shadow) !important;
        }}

        /* Toggle styling */
        div[data-testid="stToggle"] div[data-baseweb="checkbox"] div[role="checkbox"] {{
          width: 42px !important;
          height: 24px !important;
          border-radius: 12px !important;
          background: #BFDBFE !important;
          border: 1px solid #93C5FD !important;
          position: relative !important;
          box-shadow: none !important;
        }}

        div[data-testid="stToggle"] div[data-baseweb="checkbox"] div[role="checkbox"][aria-checked="true"] {{
          background: #1D4ED8 !important;
          border-color: #1D4ED8 !important;
        }}

        div[data-testid="stToggle"] div[data-baseweb="checkbox"] div[role="checkbox"]::after {{
          content: "" !important;
          position: absolute !important;
          width: 18px !important;
          height: 18px !important;
          top: 2px !important;
          left: 2px !important;
          background: #ffffff !important;
          border-radius: 8px !important;
          transform: translateX(0) !important;
          transition: transform 180ms ease !important;
        }}

        div[data-testid="stToggle"] div[data-baseweb="checkbox"] div[role="checkbox"][aria-checked="true"]::after {{
          transform: translateX(18px) !important;
        }}

        div[data-testid="stToggle"] div[data-baseweb="checkbox"] svg,
        div[data-testid="stToggle"] div[data-baseweb="checkbox"] svg path {{
          fill: #ffffff !important;
        }}

        div[data-testid="stToggle"] div[data-baseweb="checkbox"] div[role="checkbox"]:focus,
        div[data-testid="stToggle"] div[data-baseweb="checkbox"] div[role="checkbox"]:focus-visible {{
          outline: none !important;
          box-shadow: none !important;
        }}

        .block-container{{
          padding-top: 0rem !important;
          margin-top: 0rem !important;
        }}

        [data-testid="stAppViewContainer"]{{
          padding-top: 0rem !important;
          margin-top: 0rem !important;
        }}

        section[data-testid="stMain"]{{
          padding-top: 0rem !important;
          margin-top: 0rem !important;
        }}

        /* Expander improvements */
        div[data-testid="stExpander"] {{
          border: 1px solid var(--border) !important;
          border-radius: 14px !important;
          background: linear-gradient(180deg, var(--panel), var(--panel-2)) !important;
          box-shadow: var(--shadow-sm) !important;
          margin-bottom: 0.75rem !important;
          transition: all 200ms ease;
        }}

        div[data-testid="stExpander"]:hover {{
          border-color: rgba(37,99,235,0.2) !important;
          box-shadow: var(--shadow) !important;
        }}

        div[data-testid="stExpander"] summary {{
          font-weight: 600 !important;
          color: var(--text) !important;
          padding: 0.9rem 1.1rem !important;
          font-size: 0.95rem !important;
        }}

        div[data-testid="stExpander"] details[open] summary {{
          border-bottom: 1px solid var(--border) !important;
          margin-bottom: 0.75rem !important;
        }}

        /* Success/Warning/Error messages */
        .stSuccess, .stWarning, .stError, .stInfo {{
          border-radius: 12px !important;
          padding: 0.85rem 1rem !important;
          border-left: 4px solid !important;
          font-size: 0.95rem !important;
          margin: 0.75rem 0 !important;
          background: linear-gradient(180deg, var(--panel), var(--panel-2)) !important;
        }}

        .stSuccess {{ border-left-color: var(--success) !important; }}
        .stWarning {{ border-left-color: var(--warning) !important; }}
        .stError   {{ border-left-color: var(--danger) !important; }}
        .stInfo    {{ border-left-color: var(--primary) !important; }}

        /* Loading spinners */
        .stSpinner > div {{
          border-top-color: var(--primary) !important;
        }}

        /* Better spacing for sections */
        .stMarkdown hr {{
          margin: 1.5rem 0 !important;
          border: none !important;
          height: 1px !important;
          background: linear-gradient(90deg, transparent, var(--border), transparent) !important;
        }}

        /* Tooltips and help text */
        .stTooltipIcon {{
          color: var(--muted) !important;
        }}

        /* Radio and checkbox improvements */
        .stRadio > div {{
          gap: 0.75rem !important;
        }}

        .stCheckbox > label {{
          padding: 0.5rem !important;
          border-radius: 8px !important;
          transition: all 150ms ease;
        }}

        .stCheckbox > label:hover {{
          background: rgba(37,99,235,0.05) !important;
        }}

        /* Mobile responsiveness */
        @media (max-width: 768px) {{
          section[data-testid="stMain"] > div {{
            padding-left: 0.75rem;
            padding-right: 0.75rem;
          }}

          h1 {{ font-size: 1.75rem; }}
          h2 {{ font-size: 1.35rem; }}
          h3 {{ font-size: 1.15rem; }}

          div[data-testid="stButton"] button {{
            padding: 0.6rem 1rem !important;
            font-size: 0.9rem !important;
          }}
        }}

        {compact_css}
        {_resource_css}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(_dark_widget_css(), unsafe_allow_html=True)

# =========================
