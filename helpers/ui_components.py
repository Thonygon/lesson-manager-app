import streamlit as st
import streamlit.components.v1 as components
import datetime
from core.i18n import t
from core.state import get_current_user_id
from core.database import load_table, load_students
import pandas as pd
import re
from core.navigation import go_to
from core.timezone import now_local
from helpers.language import translate_status, translate_modality_value, translate_language_value

# 08) UI COMPONENTS
# =========================

def nav_pill(label: str, page: str, css_class: str):
    # Render a pill-looking button
    st.markdown(
        f"""
        <style>
        div[data-testid="stButton"] > button.{css_class} {{
            width: 100%;
            border-radius: 18px;
            padding: 1.05rem 1.15rem;
            margin: 0.55rem 0;
            font-weight: 950;
            text-align: center;
            color: #ffffff !important;
            background: linear-gradient(180deg, rgba(255,255,255,0.12), rgba(255,255,255,0.05));
            border: 1px solid rgba(255,255,255,0.18);
            box-shadow: 0 18px 34px rgba(0,0,0,0.32), inset 0 1px 0 rgba(255,255,255,0.12);
            backdrop-filter: blur(14px);
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    if st.button(label, key=f"pill_{page}", use_container_width=True):
        go_to(page)
        st.rerun()

def to_dt_naive(x, utc: bool = True):
    """
    Parse to pandas datetime and return tz-naive timestamps.

    - If x is a Series/array-like -> returns a Series[datetime64[ns]] (tz-naive)
    - If x is scalar -> returns a Timestamp or NaT (tz-naive)
    - If utc=True -> parse/convert to UTC then drop tz
    """
    s = pd.to_datetime(x, errors="coerce", utc=utc)

    # Series path
    if isinstance(s, pd.Series):
        try:
            return s.dt.tz_convert(None)  # tz-aware -> drop tz
        except Exception:
            return s  # already tz-naive or not datetimelike

    # Scalar path
    try:
        if getattr(s, "tzinfo", None) is not None:
            return s.tz_convert(None)
        return s
    except Exception:
        return s


def ts_today_naive() -> pd.Timestamp:
    # Always tz-naive "today" at midnight in the user's browser timezone
    return pd.Timestamp(now_local().replace(hour=0, minute=0, second=0, microsecond=0).replace(tzinfo=None))


def pretty_df(df: pd.DataFrame) -> pd.DataFrame:
    """Light formatting helper used across the app (values only; keeps column names)."""
    if df is None or df.empty:
        return df

    out = df.copy()

    # Trim object columns
    for c in out.columns:
        if out[c].dtype == "object":
            out[c] = out[c].astype(str).str.strip()

    return out


def translate_df_headers(df: pd.DataFrame) -> pd.DataFrame:
    """Translate dataframe column headers using t() with robust normalization."""
    if df is None or df.empty:
        return df

    out = df.copy()

    def norm_key(col: str) -> str:
        k = str(col or "").strip()
        k = k.replace("-", " ").replace("/", " ")
        k = re.sub(r"\s+", " ", k)

        # normalize common display variants
        k = k.replace(" ID", " Id")
        k = k.replace("Id", "ID")
        k = k.replace("ID", " id ")

        k = k.strip().casefold()
        k = k.replace(" ", "_")
        k = re.sub(r"__+", "_", k).strip("_")
        return k

    out.columns = [t(norm_key(c)) for c in out.columns]
    return out


def translate_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Translate headers + common coded values (Status/Modality/Languages) when present.
    Works for snake_case or pretty title columns.
    """
    if df is None or df.empty:
        return df

    out = df.copy()

    # headers
    out = translate_df_headers(out)

    cols = set(out.columns.astype(str))

    # values
    for status_col in [t("status"), "Status", "status"]:
        if status_col in cols:
            out[status_col] = out[status_col].astype(str).str.strip().str.casefold().apply(translate_status)

    for mod_col in [t("modality"), "Modality", "modality"]:
        if mod_col in cols:
            out[mod_col] = out[mod_col].astype(str).apply(translate_modality_value)

    for lang_col in [t("subject"), "Subject", "subject", t("languages"), "Languages", "languages"]:
        if lang_col in cols:
            out[lang_col] = out[lang_col].astype(str).apply(translate_language_value)

    return out


def chart_series(df: pd.DataFrame, index_col: str, value_col: str, index_key: str, value_key: str):
    """
    Builds a Series for Streamlit charts with translated axis labels.
    index_key/value_key are I18N keys (e.g., "student", "income").
    """
    if df is None or df.empty or index_col not in df.columns or value_col not in df.columns:
        return None

    s = df[[index_col, value_col]].copy()
    s[index_col] = s[index_col].astype(str)
    s[value_col] = pd.to_numeric(s[value_col], errors="coerce").fillna(0.0)

    series = s.set_index(index_col)[value_col]
    series.index.name = t(index_key)
    series.name = t(value_key)
    return series

def inject_pwa_head():
    components.html(
        """
        <script>
        (function () {
          const w = window.parent;
          const doc = w.document;

          const icon192 = w.location.origin + "/app/static/icon-192.png";
          const icon512 = w.location.origin + "/app/static/icon-512.png";
          const apple180 = w.location.origin + "/app/static/apple-touch-icon.png";

          // Remove old injected items
          doc.querySelectorAll('link[rel="manifest"][data-cm="1"]').forEach(el => el.remove());
          doc.querySelectorAll('link[rel="apple-touch-icon"][data-cm="1"]').forEach(el => el.remove());

          // Build manifest dynamically
          const manifest = {
            name: "Classman",
            short_name: "Classman",
            start_url: w.location.origin + "/",
            scope: w.location.origin + "/",
            display: "standalone",
            background_color: "#0b1220",
            theme_color: "#0b1220",
            icons: [
              { src: icon192, sizes: "192x192", type: "image/png", purpose: "any" },
              { src: icon512, sizes: "512x512", type: "image/png", purpose: "any" }
            ]
          };

          const blob = new Blob([JSON.stringify(manifest)], { type: "application/manifest+json" });
          const manifestURL = URL.createObjectURL(blob);

          const link = doc.createElement("link");
          link.rel = "manifest";
          link.href = manifestURL;
          link.setAttribute("data-cm", "1");
          doc.head.appendChild(link);

          // Apple touch icon
          doc.querySelectorAll('link[rel="apple-touch-icon"][data-cm="1"]').forEach(el => el.remove());
          const ati = doc.createElement("link");
          ati.rel = "apple-touch-icon";
          ati.href = apple180;
          ati.sizes = "180x180";
          ati.setAttribute("data-cm", "1");
          doc.head.appendChild(ati);

          // Favicon override
          doc.querySelectorAll('link[rel="icon"][data-cm="1"]').forEach(el => el.remove());
          const fav = doc.createElement("link");
          fav.rel = "icon";
          fav.href = apple180;
          fav.setAttribute("data-cm", "1");
          doc.head.appendChild(fav);

          // Meta tags
          const metas = [
            { name: "apple-mobile-web-app-capable", content: "yes" },
            { name: "mobile-web-app-capable", content: "yes" },
            { name: "apple-mobile-web-app-status-bar-style", content: "black-translucent" },
            { name: "apple-mobile-web-app-title", content: "Classio" },
            { name: "theme-color", content: "#0b1220" }
          ];

          metas.forEach(m => {
            let el = doc.querySelector('meta[name="' + m.name + '"][data-cm="1"]');
            if (!el) {
              el = doc.createElement("meta");
              el.setAttribute("data-cm", "1");
              el.name = m.name;
              doc.head.appendChild(el);
            }
            el.content = m.content;
          });

        })();
        </script>
        """,
        height=0,
    )



# =========================
