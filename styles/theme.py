import streamlit as st


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





def load_css_home_dark():
    st.markdown(
        """
        <style>
        :root { color-scheme: light !important; }
        html, body { color-scheme: light !important; }

        :root{
          --bg-1:#f5f7fb;
          --bg-2:#f8faff;
          --bg-3:#eef4ff;

          --text:#0f172a;
          --muted:#475569;

          --panel:rgba(255,255,255,0.88);
          --panel-2:rgba(255,255,255,0.72);
          --border:rgba(17,24,39,0.08);
          --border-strong:rgba(17,24,39,0.12);

          --primary:#2563EB;
          --primary-strong:#1D4ED8;
          --success:#10B981;
          --danger:#EF4444;

          --shadow-lg:0 22px 55px rgba(15,23,42,0.10);
          --shadow-md:0 12px 28px rgba(15,23,42,0.08);
          --radius-xl:24px;
          --radius-lg:18px;
          --radius-md:14px;
        }

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
          border-radius:18px;
          border:1px solid var(--border);
          background:linear-gradient(180deg,var(--panel),var(--panel-2));
          box-shadow:var(--shadow-md);
        }

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
          padding: 14px;
          margin-top: 8px;
          border-radius: var(--radius-xl);
          background: linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.03));
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

def load_css_app_light(compact: bool = False):
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

    st.markdown(
        f"""
        <style>
        :root {{ color-scheme: light !important; }}
        html, body {{ color-scheme: light !important; }}

        :root{{
          --bg:#f5f7fb;
          --panel:#ffffff;
          --panel-soft:#fbfcff;
          --border:rgba(17,24,39,0.08);
          --border2:rgba(17,24,39,0.10);
          --text:#0f172a;
          --muted:#475569;
          --primary:#2563EB;
          --shadow:0 12px 28px rgba(15,23,42,0.08);
        }}

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
            linear-gradient(180deg, #f8faff 0%, var(--bg) 100%) !important;
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
          padding-top: 0rem;
          padding-bottom: 1.4rem;
          max-width: 1200px;
        }}

        html, body, [class*="css"]{{
          font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
        }}

        h1, h2, h3 {{
          letter-spacing: -0.02em;
        }}

        div[data-testid="stVerticalBlockBorderWrapper"] {{
          background: linear-gradient(180deg, #ffffff, #fcfdff) !important;
          border: 1px solid var(--border) !important;
          border-radius: 18px !important;
          padding: 18px !important;
          box-shadow: var(--shadow) !important;
        }}

        div[data-testid="metric-container"] {{
          background: linear-gradient(180deg, #ffffff, #fbfdff) !important;
          border: 1px solid var(--border) !important;
          padding: 14px 16px !important;
          border-radius: 18px !important;
          box-shadow: var(--shadow) !important;
        }}

        div[data-testid="stButton"] button {{
          border-radius: 14px !important;
          padding: 0.64rem 1rem !important;
          border: 1px solid var(--border2) !important;
          background: linear-gradient(180deg, #ffffff, #f8fbff) !important;
          color: var(--text) !important;
          -webkit-text-fill-color: var(--text) !important;
          font-weight: 700 !important;
          transition: all 160ms ease;
          box-shadow: 0 4px 14px rgba(15,23,42,0.04);
        }}

        div[data-testid="stButton"] button:hover {{
          transform: translateY(-1px);
          border-color: rgba(37,99,235,0.25) !important;
          box-shadow:
            0 0 0 4px rgba(37,99,235,0.08),
            0 8px 18px rgba(15,23,42,0.06);
        }}

        div[data-testid="stTextInput"] input,
        div[data-testid="stTextArea"] textarea,
        div[data-testid="stNumberInput"] input,
        div[data-testid="stDateInput"] input {{
          border-radius: 14px !important;
          background: white !important;
          border: 1px solid var(--border2) !important;
          color: var(--text) !important;
          -webkit-text-fill-color: var(--text) !important;
        }}

        div[data-testid="stSelectbox"] [data-baseweb="select"] > div {{
          border-radius: 14px !important;
          background: white !important;
          border: 1px solid var(--border2) !important;
          color: var(--text) !important;
          -webkit-text-fill-color: var(--text) !important;
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

        {compact_css}
        </style>
        """,
        unsafe_allow_html=True,
    )

# =========================
