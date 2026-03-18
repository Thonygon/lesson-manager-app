import streamlit as st
import datetime, os, uuid
from PIL import Image
import io
from core.i18n import t
from core.state import get_current_user_id
from core.timezone import now_local
from core.database import get_sb, load_table, load_students
import pandas as pd
import re
from io import BytesIO
import streamlit.components.v1 as components
from core.state import with_owner
from core.database import clear_app_caches
from helpers.ui_components import to_dt_naive, ts_today_naive
from helpers.schedule import load_schedules, load_overrides
from translations import I18N

# 07.11) GOALS HELPERS
# =========================
YEAR_GOAL_SCOPE = "personal"

def _first_col(df: pd.DataFrame, candidates) -> str | None:
    if df is None or df.empty:
        return None
    norm = {str(c).strip().casefold(): c for c in df.columns}
    for cand in candidates:
        k = str(cand).strip().casefold()
        if k in norm:
            return norm[k]
    return None


def _parse_float_loose(v, default=0.0) -> float:
    """
    Parses numbers from: 150000, 150.000, 150,000, '150000 TL', Decimal, etc.
    """
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return float(default)
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip()
        if s == "":
            return float(default)

        # remove currency/text
        s = re.sub(r"[^\d,.\-]", "", s)

        # handle "150.000" as 150000 (common in TR) if no comma decimals pattern
        # Strategy:
        # - If both ',' and '.' exist -> assume thousand separators, remove both then parse
        # - If only '.' exists and it's like 150.000 -> treat as thousands separator -> remove dots
        # - If only ',' exists -> could be decimal OR thousands; for goals usually thousands -> remove commas
        if "," in s and "." in s:
            s = s.replace(".", "").replace(",", "")
        elif "." in s:
            # if dot groups of 3 at end -> thousands
            if re.fullmatch(r"-?\d{1,3}(\.\d{3})+", s):
                s = s.replace(".", "")
        elif "," in s:
            if re.fullmatch(r"-?\d{1,3}(,\d{3})+", s):
                s = s.replace(",", "")
            else:
                # could be decimal comma, convert to dot
                s = s.replace(",", ".")

        return float(s)
    except Exception:
        return float(default)
    
@st.cache_data(ttl=45, show_spinner=False)
def _load_app_settings_map_cached(uid: str) -> dict:
    try:
        df = load_table("app_settings")
    except Exception:
        return {}

    if df is None or df.empty:
        return {}

    key_col = _first_col(df, ["key", "setting_key", "name"])
    val_col = _first_col(df, ["value", "setting_value", "val"])

    if not key_col or not val_col:
        return {}

    tmp = df.copy()
    tmp[key_col] = tmp[key_col].astype(str).str.strip()

    out = {}
    for _, row in tmp.iterrows():
        k = str(row.get(key_col, "")).strip()
        if not k:
            continue
        out[k] = row.get(val_col)

    return out


def load_app_settings_map() -> dict:
    uid = get_current_user_id()
    return _load_app_settings_map_cached(uid)

def load_app_setting(key: str, default=None, key_fallbacks: list[str] | None = None):
    settings_map = load_app_settings_map()

    keys_to_try = [str(key).strip()]
    if key_fallbacks:
        keys_to_try += [str(k).strip() for k in key_fallbacks if str(k).strip()]

    for k in keys_to_try:
        if k in settings_map:
            v = settings_map[k]
            return _parse_float_loose(v, default) if isinstance(default, (int, float)) else v

    return default


def save_app_setting(key: str, value, key_fallbacks: list[str] | None = None) -> bool:
    if not key:
        return False

    payload = with_owner({
        "key": str(key).strip(),
        "value": str(value),
    })

    uid = get_current_user_id()
    if not uid:
        st.error("Missing user_id while saving app setting.")
        return False

    try:
        get_sb().table("app_settings").upsert(
            payload,
            on_conflict="user_id,key"
        ).execute()
        clear_app_caches()
        return True
    except Exception as e:
        st.error(f"Could not save app setting '{key}': {e}")
        return False


def get_year_goal_progress_snapshot(year: int | None = None, goal_key: str = "yearly_income_goal") -> dict:
    today = ts_today_naive()
    yr = int(year or today.year)

    goal = load_app_setting(
        goal_key,
        default=0.0,
        key_fallbacks=["annual_income_goal", "year_income_goal", "income_goal_year"],
    )
    goal = _parse_float_loose(goal, 0.0)

    # YTD income from payments
    ytd = 0.0
    try:
        p = load_table("payments")
        if p is not None and not p.empty:
            if "payment_date" not in p.columns:
                p["payment_date"] = None
            if "paid_amount" not in p.columns:
                p["paid_amount"] = 0.0

            p = p.copy()
            p["payment_date"] = to_dt_naive(p["payment_date"], utc=True)
            p["paid_amount"] = pd.to_numeric(p["paid_amount"], errors="coerce").fillna(0.0).astype(float)
            p = p.dropna(subset=["payment_date"])
            p = p[p["payment_date"].dt.year == yr]
            ytd = float(p["paid_amount"].sum())
    except Exception:
        ytd = 0.0

    progress = 0.0
    if goal > 0:
        progress = max(0.0, min(1.0, ytd / goal))

    remaining = max(0.0, goal - ytd)

    return {"year": yr, "goal": float(goal), "ytd_income": float(ytd), "progress": float(progress), "remaining": float(remaining)}

def upload_avatar_to_supabase(file, user_id: str) -> str:
    """
    Uploads a normalized profile avatar to Supabase Storage and returns a public URL.

    Requires:
    - A Supabase Storage bucket named: avatars
    - The bucket should allow reads for the uploaded file URL to work
      (or you can switch to signed URLs later).
    """
    if file is None:
        return ""

    content_type = str(getattr(file, "type", "") or "").strip().lower()
    if not content_type.startswith("image/"):
        raise ValueError(t("avatar_upload_invalid_image"))

    raw = file.getvalue()
    if not raw:
        raise ValueError(t("avatar_upload_empty"))

    max_size_mb = 5
    if len(raw) > max_size_mb * 1024 * 1024:
        raise ValueError(t("avatar_upload_too_large").format(max_size_mb=max_size_mb))

    safe_user_id = str(user_id).strip()
    if not safe_user_id:
        raise ValueError(t("avatar_upload_missing_user"))

    try:
        img = Image.open(BytesIO(raw)).convert("RGBA")
    except Exception:
        raise ValueError(t("avatar_upload_invalid_image"))

    # Center crop to square
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    img = img.crop((left, top, left + side, top + side))

    # Flatten transparency onto dark background
    bg = Image.new("RGB", (side, side), (15, 23, 42))
    bg.paste(img, mask=img.split()[-1])

    # Resize to a clean avatar size
    bg = bg.resize((512, 512))

    buf = BytesIO()
    bg.save(buf, format="JPEG", quality=92)
    final_raw = buf.getvalue()

    ext = "jpeg"
    final_content_type = "image/jpeg"
    object_path = f"{safe_user_id}/{uuid.uuid4().hex}.{ext}"

    try:
        get_sb().storage.from_("avatars").upload(
            path=object_path,
            file=final_raw,
            file_options={
                "content-type": final_content_type,
                "upsert": "true",
            },
        )
    except Exception as e:
        raise RuntimeError(f"{t('avatar_upload_storage_failed')}: {e}")

    try:
        public_url = get_sb().storage.from_("avatars").get_public_url(object_path)
    except Exception as e:
        raise RuntimeError(f"{t('avatar_upload_url_failed')}: {e}")

    if isinstance(public_url, dict):
        public_url = public_url.get("publicUrl") or public_url.get("public_url") or ""

    public_url = str(public_url or "").strip()
    if not public_url:
        raise RuntimeError(t("avatar_upload_no_public_url"))

    return public_url

def render_home_indicator(
    status: str = None,
    badge: str = None,
    items=None,                     # list[tuple[str,str]]
    progress: float | None = None,  # 0..1
    accent: str = "#3B82F6",
    progress_label: str | None = None,  # e.g. t("completed")
):
    # Avoid calling t() in default args (safer if t() is defined later)
    if status is None:
        status = t("online")
    if badge is None:
        badge = t("today")

    if items is None:
        items = [
            (t("students"), "0"),
            (t("ytd_income"), "₺0"),   # fixed key (was "ydt_income")
            (t("goal"), "0"),
            (t("next"), t("no_events")),
        ]
    else:
        # If caller passed raw keys like ("students","0"), translate labels
        cleaned = []
        for lbl, val in items:
            lbl_s = str(lbl or "").strip()
            if lbl_s in I18N.get(st.session_state.get("ui_lang", "en"), {}) or lbl_s in I18N.get("en", {}):
                lbl_s = t(lbl_s)
            cleaned.append((lbl_s, val))
        items = cleaned

    if progress_label is None:
        progress_label = t("completed")

    # progress percent
    pct = None
    if progress is not None:
        try:
            pct = int(round(max(0.0, min(1.0, float(progress))) * 100))
        except Exception:
            pct = None

    kpis_html = "".join(
        f"""
        <div class="home-indicator-kpi">
          <div class="k">{lbl}</div>
          <div class="v">{val}</div>
        </div>
        """
        for (lbl, val) in items
    )

    badge_html = f'<span class="home-indicator-badge">{badge}</span>' if badge else ""

    right_html = ""
    if pct is not None:
        right_html = f"""
        <div class="home-indicator-mini">{pct}% {progress_label}</div>
        <div class="home-indicator-progress">
          <div style="width:{pct}%;"></div>
        </div>
        """

    html = f"""
<div class="home-indicator-wrap">
  <div class="home-indicator">

    <div class="home-indicator-left">
      <div class="home-indicator-dot"></div>
      <div class="home-indicator-title">
        <div class="s">{status} {badge_html}</div>
      </div>
    </div>

    <div class="home-indicator-mid">
      {kpis_html}
    </div>

    <div class="home-indicator-right">
      {right_html}
    </div>

  </div>
</div>

<style>
.home-indicator-wrap {{
  width: 100%;
  margin: 0rem 0 0rem 0;
}}

.home-indicator {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;

  padding: 14px 16px;
  border-radius: 18px;

  background: linear-gradient(
    135deg,
    rgba(59,130,246,0.12),
    rgba(255,255,255,0.10)
  );
  border: 1px solid rgba(59,130,246,0.25);
  box-shadow: 0 10px 28px rgba(37,99,235,0.18);
  color: var(--text);
}}

.home-indicator-left {{
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 240px;
}}

.home-indicator-dot {{
  width: 12px;
  height: 12px;
  border-radius: 999px;
  background: {accent};
  box-shadow: 0 0 0 6px rgba(59,130,246,0.12);
}}

.home-indicator-title {{
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}}

.home-indicator-title .s {{
  font-size: 0.82rem;
  opacity: 0.78;
}}

.home-indicator-badge {{
  margin-left: 6px;
  font-size: 0.72rem;
  font-weight: 800;
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(255,255,255,0.10);
  border: 1px solid rgba(255,255,255,0.14);
}}

.home-indicator-mid {{
  flex: 1;
  display: flex;
  align-items: center;
  gap: 14px;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}}

.home-indicator-mid::-webkit-scrollbar {{
  display: none;
}}
.home-indicator-mid {{
  -ms-overflow-style: none;
  scrollbar-width: none;
}}

.home-indicator-kpi {{
  padding: 6px 12px;
  border-radius: 14px;
  background: rgba(59,130,246,0.12);
  border: 1px solid rgba(255,255,255,0.14);

  flex: 0 0 130px;
  min-width: 130px;
  max-width: 130px;

  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}}

.home-indicator-kpi .k {{
  font-size: 0.70rem;
  opacity: 0.72;
  margin-bottom: 2px;
}}

.home-indicator-kpi .v {{
  font-size: 0.92rem;
  font-weight: 900;
}}

.home-indicator-right {{
  min-width: 210px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: flex-end;
}}

.home-indicator-progress {{
  width: 100%;
  height: 10px;
  border-radius: 999px;
  overflow: hidden;
  background: rgba(255,255,255,0.10);
  border: 1px solid rgba(59,130,246,0.12);
}}

.home-indicator-progress > div {{
  height: 100%;
  background: linear-gradient(90deg, {accent}, rgba(255,255,255,0.25));
  border-radius: 999px;
  box-shadow: 0 0 18px rgba(59,130,246,0.22);
}}

.home-indicator-mini {{
  font-size: 0.78rem;
  opacity: 0.8;
}}

@media (max-width: 820px) {{
  .home-indicator {{
    flex-direction: column;
    align-items: stretch;
  }}
  .home-indicator-right {{
    align-items: flex-start;
  }}
}}
</style>
"""
    # Height: allow more space on mobile when it stacks
    height = 220 if bool(st.session_state.get("compact_mode", False)) else 160
    components.html(html, height=height, scrolling=False)

def get_next_lesson_display() -> str:
    """
    Returns next lesson time like 'Tue 19:15' or '--:--' if none.
    Uses schedules + overrides (scheduled only).
    """
    try:
        sched = load_schedules()
        ov = load_overrides()
    except Exception:
        return "--:--"

    now = now_local()
    now_ts = pd.Timestamp(now.replace(tzinfo=None))

    candidates = []

    # --- 1) Overrides: take upcoming scheduled new_datetime ---
    if ov is not None and not ov.empty and "new_datetime" in ov.columns:
        tmp = ov.copy()
        tmp["status"] = tmp.get("status", "").astype(str).str.lower()
        tmp = tmp[tmp["status"] == "scheduled"].copy()
        tmp["new_datetime"] = pd.to_datetime(tmp["new_datetime"], errors="coerce")
        tmp = tmp[tmp["new_datetime"].notna()].copy()
        tmp["new_datetime"] = tmp["new_datetime"].dt.tz_localize(None)

        upcoming = tmp[tmp["new_datetime"] >= now_ts].sort_values("new_datetime")
        for _, r in upcoming.head(20).iterrows():
            candidates.append(pd.Timestamp(r["new_datetime"]).to_pydatetime())

    # --- 2) Weekly schedules: generate next occurrence for each active schedule ---
    if sched is not None and not sched.empty:
        s = sched.copy()
        s = s[s.get("active", True) == True].copy()

        # weekday: 0=Mon ... 6=Sun in your code
        for _, r in s.iterrows():
            try:
                wd = int(r.get("weekday", 0))
                time_str = str(r.get("time", "00:00")).strip()
                hh, mm = [int(x) for x in time_str.split(":")[:2]]

                days_ahead = (wd - now_ts.weekday()) % 7
                dt = (now_ts + pd.Timedelta(days=days_ahead)).normalize() + pd.Timedelta(hours=hh, minutes=mm)

                if dt < now_ts:
                    dt = dt + pd.Timedelta(days=7)

                candidates.append(dt.to_pydatetime())
            except Exception:
                continue

    if not candidates:
        return "--:--"

    next_dt = min(candidates)
    return next_dt.strftime("%a %H:%M")

# =========================
