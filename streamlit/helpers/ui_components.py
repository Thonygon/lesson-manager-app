import streamlit as st
import streamlit.components.v1 as components
from core.i18n import t
from core.database import LESSON_NOTE_DEFAULT_TOKEN, load_table
import pandas as pd
import re
from core.navigation import go_to
from core.timezone import now_local
from helpers.language import translate_status, translate_modality_value, translate_language_value


def _loading_overlay_style() -> str:
    return """
        .classio-loading-overlay {
            position: fixed;
            inset: 0;
            z-index: 999999;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 24px;
            background:
                radial-gradient(circle at 12% 14%, color-mix(in srgb, var(--primary, #2563EB) 16%, transparent), transparent 28%),
                radial-gradient(circle at 85% 18%, color-mix(in srgb, var(--success, #10B981) 12%, transparent), transparent 24%),
                linear-gradient(
                    180deg,
                    color-mix(in srgb, var(--bg-2, #f8faff) 92%, transparent),
                    color-mix(in srgb, var(--bg-1, #f5f7fb) 96%, transparent)
                );
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
        }

        .classio-loading-card {
            min-width: 240px;
            max-width: min(92vw, 360px);
            padding: 18px 20px;
            border-radius: 0;
            border: none;
            background: transparent;
            box-shadow: none;
            text-align: center;
        }

        .classio-loading-spinner {
            width: 36px;
            height: 36px;
            margin: 0 auto 12px auto;
            border-radius: 999px;
            border: 3px solid color-mix(in srgb, var(--border-strong, rgba(17,24,39,0.12)) 80%, transparent);
            border-top-color: var(--primary, #2563EB);
            animation: classio-loading-spin 0.82s linear infinite;
        }

        .classio-loading-title {
            font-size: 0.98rem;
            font-weight: 700;
            color: var(--text, #0f172a);
            margin-bottom: 4px;
        }

        .classio-loading-copy {
            font-size: 0.84rem;
            color: var(--muted, #64748b);
            line-height: 1.45;
        }

        .classio-loading-overlay.is-hiding {
            opacity: 0;
            visibility: hidden;
            pointer-events: none;
        }

        @keyframes classio-loading-spin {
            to { transform: rotate(360deg); }
        }

        @media (prefers-color-scheme: dark) {
            .classio-loading-overlay {
                background:
                    radial-gradient(circle at 12% 14%, rgba(59,130,246,0.18), transparent 28%),
                    radial-gradient(circle at 85% 18%, rgba(52,211,153,0.14), transparent 24%),
                    linear-gradient(180deg, rgba(26,38,64,0.94), rgba(15,23,42,0.97));
            }

            .classio-loading-spinner {
                border-color: rgba(255,255,255,0.14);
                border-top-color: #60A5FA;
            }

            .classio-loading-title { color: #f1f5f9; }
            .classio-loading-copy { color: #94a3b8; }
        }
    """


def _route_loading_style() -> str:
    return """
        .classio-route-loading {
            position: fixed;
            inset: 0;
            z-index: 999998;
            pointer-events: none;
        }

        .classio-route-loading__bar {
            position: fixed;
            left: 0;
            width: 100%;
            height: 4px;
            background: color-mix(in srgb, var(--border-strong, rgba(17,24,39,0.12)) 70%, transparent);
            overflow: hidden;
            box-shadow: 0 0 0 1px color-mix(in srgb, var(--border, rgba(17,24,39,0.08)) 82%, transparent);
        }

        .classio-route-loading__bar--top {
            top: 0;
        }

        .classio-route-loading__bar--bottom {
            bottom: 0;
        }

        .classio-route-loading__fill {
            height: 100%;
            width: var(--classio-route-progress, 42%);
            background: linear-gradient(
                90deg,
                var(--primary, #2563EB) 0%,
                color-mix(in srgb, var(--primary-strong, #1D4ED8) 68%, white 32%) 55%,
                var(--success, #10B981) 100%
            );
            box-shadow: 0 0 18px color-mix(in srgb, var(--primary, #2563EB) 36%, transparent);
            transition: width 180ms ease;
        }

        @media (prefers-color-scheme: dark) {
            .classio-route-loading__bar {
                background: rgba(255,255,255,0.08);
                box-shadow: 0 0 0 1px rgba(255,255,255,0.04);
            }
        }

        @media (max-width: 768px) {
            .classio-route-loading__bar {
                height: 5px;
            }
        }
    """


def render_route_loading_markup(
    *,
    title: str,
    copy: str,
    progress_ratio: float,
) -> str:
    progress_pct = max(0.0, min(float(progress_ratio or 0.0), 1.0)) * 100.0
    return f"""
        <style>
        {_route_loading_style()}
        </style>
        <div class="classio-route-loading" style="--classio-route-progress: {progress_pct:.0f}%;" aria-live="polite">
            <div class="classio-route-loading__bar classio-route-loading__bar--top">
                <div class="classio-route-loading__fill"></div>
            </div>
            <div class="classio-route-loading__bar classio-route-loading__bar--bottom">
                <div class="classio-route-loading__fill"></div>
            </div>
        </div>
    """


def render_loading_overlay_markup(
    *,
    overlay_id: str,
    title: str,
    copy: str,
) -> str:
    return f"""
        <style>
        {_loading_overlay_style()}
        </style>
        <div id="{overlay_id}" class="classio-loading-overlay" aria-live="polite">
            <div class="classio-loading-card">
                <div class="classio-loading-spinner"></div>
                <div class="classio-loading-title">{title}</div>
                <div class="classio-loading-copy">{copy}</div>
            </div>
        </div>
    """


def mount_loading_overlay_hide_script(overlay_id: str, *, auto_hide_ms: int = 500) -> None:
    delay_ms = max(0, int(auto_hide_ms))
    fallback_ms = delay_ms + 700
    components.html(
        f"""
        <script>
        (function() {{
            function hideOverlay() {{
                const hostDoc = window.parent?.document || document;
                const overlay = hostDoc.getElementById("{overlay_id}");
                if (overlay) {{
                    overlay.classList.add("is-hiding");
                }}
            }}

            window.addEventListener("load", function() {{
                window.setTimeout(hideOverlay, {delay_ms});
            }});

            window.setTimeout(hideOverlay, {fallback_ms});
        }})();
        </script>
        """,
        height=0,
    )


def inject_modern_section_switcher_styles() -> None:
    if st.session_state.get("_classio_modern_section_switcher_styles_injected"):
        return
    st.session_state["_classio_modern_section_switcher_styles_injected"] = True
    st.markdown(
        """
        <style>
        div[data-testid="stRadio"] div[role="radiogroup"][aria-label="Section"] {
            display: flex;
            flex-wrap: nowrap;
            align-items: stretch;
            gap: 0.2rem;
            overflow-x: auto;
            overflow-y: hidden;
            padding: 0 0 0.35rem 0;
            margin: 0 0 0.55rem 0;
            border-bottom: 1px solid color-mix(in srgb, var(--border, rgba(148,163,184,0.28)) 84%, transparent);
            scrollbar-width: none;
            -ms-overflow-style: none;
        }
        div[data-testid="stRadio"] div[role="radiogroup"][aria-label="Section"]::-webkit-scrollbar {
            display: none;
        }
        div[data-testid="stRadio"] div[role="radiogroup"][aria-label="Section"] label[data-baseweb="radio"] {
            display: inline-flex !important;
            align-items: center;
            min-width: max-content;
            margin: 0 !important;
            padding: 0.1rem 0.15rem 0.7rem 0.15rem !important;
            border-radius: 0 !important;
            border: none !important;
            border-bottom: 2px solid transparent !important;
            background: transparent !important;
            box-shadow: none !important;
            color: var(--muted, #64748b) !important;
            font-weight: 800 !important;
            transition: color .16s ease, border-color .16s ease, background-color .16s ease;
        }
        div[data-testid="stRadio"] div[role="radiogroup"][aria-label="Section"] label[data-baseweb="radio"] > div:first-child {
            display: none !important;
        }
        div[data-testid="stRadio"] div[role="radiogroup"][aria-label="Section"] label[data-baseweb="radio"] > div:last-child {
            padding: 0 !important;
        }
        div[data-testid="stRadio"] div[role="radiogroup"][aria-label="Section"] label[data-baseweb="radio"]:hover {
            color: var(--text, #0f172a) !important;
        }
        div[data-testid="stRadio"] div[role="radiogroup"][aria-label="Section"] label[data-baseweb="radio"]:has(input:checked) {
            color: var(--text, #0f172a) !important;
            border-bottom-color: var(--primary, #2563EB) !important;
        }
        div[data-testid="stRadio"] div[role="radiogroup"][aria-label="Section"] label[data-baseweb="radio"]:has(input:focus-visible) {
            outline: none !important;
            box-shadow: inset 0 -2px 0 var(--primary, #2563EB) !important;
        }
        @media (max-width: 768px) {
            div[data-testid="stRadio"] div[role="radiogroup"][aria-label="Section"] {
                gap: 0.1rem;
            }
            div[data-testid="stRadio"] div[role="radiogroup"][aria-label="Section"] label[data-baseweb="radio"] {
                padding-bottom: 0.65rem !important;
                font-size: 0.98rem !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_section_switcher(state_key: str, options: list[tuple[str, str]]) -> str:
    option_keys = [key for key, _label in options]
    label_map = {key: label for key, label in options}
    reverse_label_map = {label: key for key, label in options}
    current_value = st.session_state.get(state_key)
    if current_value not in option_keys:
        current_value = option_keys[0]

    try:
        from streamlit_option_menu import option_menu

        selected_label = option_menu(
            None,
            [label_map[key] for key in option_keys],
            default_index=option_keys.index(current_value),
            orientation="horizontal",
            key=f"{state_key}__option_menu",
            styles={
                "container": {
                    "padding": "0",
                    "margin": "0 0 .55rem 0",
                    "background-color": "transparent",
                },
                "nav": {
                    "flex-wrap": "nowrap",
                    "overflow-x": "auto",
                    "overflow-y": "hidden",
                    "white-space": "nowrap",
                    "gap": ".15rem",
                    "padding": "0 0 .35rem 0",
                    "border-bottom": "1px solid color-mix(in srgb, var(--border, rgba(148,163,184,0.28)) 84%, transparent)",
                },
                "nav-link": {
                    "padding": ".15rem .15rem .7rem .15rem",
                    "margin": "0 .45rem 0 0",
                    "border-radius": "0",
                    "border-bottom": "2px solid transparent",
                    "background-color": "transparent",
                    "color": "var(--muted, #64748b)",
                    "font-size": "1rem",
                    "font-weight": "800",
                    "line-height": "1.2",
                },
                "nav-link-selected": {
                    "padding": ".15rem .15rem .7rem .15rem",
                    "border-radius": "0",
                    "border-bottom": "2px solid var(--primary, #2563EB)",
                    "background-color": "transparent",
                    "color": "var(--text, #0f172a)",
                    "font-weight": "900",
                },
            },
        )
        resolved_value = reverse_label_map.get(selected_label, current_value)
        st.session_state[state_key] = resolved_value
        return str(resolved_value)
    except Exception:
        inject_modern_section_switcher_styles()
        return str(
            st.radio(
                "Section",
                options=option_keys,
                index=option_keys.index(current_value),
                format_func=lambda key: label_map.get(key, key),
                key=state_key,
                horizontal=True,
                label_visibility="collapsed",
            )
        )


def inject_loading_screen():
    st.markdown(
        render_loading_overlay_markup(
            overlay_id="app-preloader",
            title="Classio",
            copy="Loading your workspace...",
        ),
        unsafe_allow_html=True,
    )
    mount_loading_overlay_hide_script("app-preloader", auto_hide_ms=500)

# 08) UI COMPONENTS
# =========================

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
            out[c] = out[c].replace(LESSON_NOTE_DEFAULT_TOKEN, "—")

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


def trigger_book_rain(
    *,
    nonce: int | str,
    total_books: int = 28,
    min_font_px: int = 42,
    max_font_px: int = 68,
    min_duration_s: float = 3.2,
    max_duration_s: float = 5.9,
) -> None:
    safe_nonce = str(nonce)
    components.html(
        f"""
        <script>
        (function () {{
          const hostWindow = window.parent;
          const hostDoc = hostWindow.document;
          const overlayId = "classio-book-rain-overlay";
          const styleId = "classio-book-rain-style";
          const stateKey = "__classioBookRainState";
          const nonce = {safe_nonce!r};
          const books = ["📚", "📖", "📘", "📗", "📕", "📙", "📒"];

          if (!hostDoc.getElementById(styleId)) {{
            const style = hostDoc.createElement("style");
            style.id = styleId;
            style.textContent = `
              #${{overlayId}} {{
                position: fixed;
                inset: 0;
                width: 100vw;
                height: 100vh;
                overflow: hidden;
                pointer-events: none;
                z-index: 999999;
              }}
              #${{overlayId}} .classio-book-rain-item {{
                position: absolute;
                top: -120px;
                opacity: 1;
                user-select: none;
                will-change: transform;
                filter: drop-shadow(0 7px 8px rgba(15,23,42,.28));
                animation-name: classio-book-rain-fall;
                animation-timing-function: linear;
                animation-fill-mode: forwards;
              }}
              @keyframes classio-book-rain-fall {{
                0% {{
                  transform: translateY(-120px) translateX(0px) rotate(0deg);
                }}
                25% {{
                  transform: translateY(25vh) translateX(-20px) rotate(90deg);
                }}
                50% {{
                  transform: translateY(50vh) translateX(15px) rotate(180deg);
                }}
                75% {{
                  transform: translateY(75vh) translateX(-10px) rotate(270deg);
                }}
                100% {{
                  transform: translateY(calc(100vh + 180px)) translateX(20px) rotate(360deg);
                }}
              }}
              @media (prefers-reduced-motion: reduce) {{
                #${{overlayId}} .classio-book-rain-item {{
                  animation-duration: 2.8s !important;
                }}
              }}
            `;
            hostDoc.head.appendChild(style);
          }}

          if (!hostWindow[stateKey]) {{
            hostWindow[stateKey] = {{ lastNonce: null, cleanupTimer: null }};
          }}
          const state = hostWindow[stateKey];
          if (state.lastNonce === nonce) {{
            return;
          }}
          state.lastNonce = nonce;

          const prior = hostDoc.getElementById(overlayId);
          if (prior) prior.remove();

          const overlay = hostDoc.createElement("div");
          overlay.id = overlayId;

          for (let i = 0; i < {total_books}; i += 1) {{
            const book = hostDoc.createElement("div");
            book.className = "classio-book-rain-item";
            book.textContent = books[Math.floor(Math.random() * books.length)];
            book.style.left = (Math.random() * 100) + "vw";
            book.style.fontSize = ({min_font_px} + Math.random() * ({max_font_px} - {min_font_px})) + "px";
            book.style.animationDuration = ({min_duration_s} + Math.random() * ({max_duration_s} - {min_duration_s})) + "s";
            book.style.animationDelay = (Math.random() * 1.2) + "s";
            overlay.appendChild(book);
          }}

          hostDoc.body.appendChild(overlay);

          if (state.cleanupTimer) {{
            hostWindow.clearTimeout(state.cleanupTimer);
          }}
          state.cleanupTimer = hostWindow.setTimeout(() => {{
            overlay.remove();
          }}, 8000);
        }})();
        </script>
        """,
        height=0,
    )


def render_styled_dataframe(df: pd.DataFrame, max_rows: int = 200):
    """Render a DataFrame as a styled HTML table matching the app theme."""
    if df is None or df.empty:
        st.caption(t("no_data"))
        return

    show = df.head(max_rows)

    uid = f"stbl_{id(df)}"

    rows_html = []
    for i, (_, row) in enumerate(show.iterrows()):
        row_class = "cm-row-alt" if i % 2 else "cm-row"
        cells = "".join(
            f'<td style="padding:8px 12px;border-bottom:1px solid var(--border);'
            f'color:var(--text);font-size:0.85rem;white-space:nowrap;">{_esc(v)}</td>'
            for v in row
        )
        rows_html.append(f'<tr class="{row_class}">{cells}</tr>')

    header_cells = "".join(
        f'<th style="padding:8px 12px;text-align:left;font-weight:700;font-size:0.78rem;'
        f'text-transform:uppercase;letter-spacing:0.04em;color:var(--text);'
        f'border-bottom:2px solid var(--border);white-space:nowrap;">{_esc(c)}</th>'
        for c in show.columns
    )

    html = f"""
    <style>
    .{uid}-wrap {{
      overflow-x: auto;
      border: 1px solid var(--border);
      border-radius: 12px;
      background: var(--panel);
      margin: 8px 0;
    }}

    .{uid}-table {{
      width: 100%;
      border-collapse: collapse;
      font-family: Inter, system-ui, sans-serif;
    }}

    .{uid}-table thead tr {{
      background: var(--panel-2);
    }}

    .{uid}-table .cm-row {{
      background: var(--panel);
      transition: background 150ms;
    }}

    .{uid}-table .cm-row-alt {{
      background: var(--panel-soft);
      transition: background 150ms;
    }}

    .{uid}-table .cm-row:hover,
    .{uid}-table .cm-row-alt:hover {{
      background: var(--bg-3);
    }}
    </style>

    <div class="{uid}-wrap">
      <table class="{uid}-table">
        <thead><tr>{header_cells}</tr></thead>
        <tbody>{"".join(rows_html)}</tbody>
      </table>
    </div>
    """

    if len(df) > max_rows:
        html += (
            f'<p style="color:var(--muted);font-size:0.8rem;opacity:0.85;text-align:center;">'
            f'{t("showing")} {max_rows} / {len(df)}</p>'
        )

    st.markdown(html, unsafe_allow_html=True)


def _esc(val) -> str:
    """Escape HTML in cell values."""
    s = str(val) if not pd.isna(val) else ""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# =========================
