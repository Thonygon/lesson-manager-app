import streamlit as st
import datetime
import pandas as pd
from core.i18n import t
from core.state import get_current_user_id
from core.timezone import now_local
from core.database import get_sb, load_table, load_students
from core.database import clear_app_caches
from helpers.currency import CURRENCIES, CURRENCY_CODES, get_preferred_currency, currency_symbol, format_currency

# 07.6) PRICING ITEMS HELPERS
# =========================

@st.cache_data(ttl=45, show_spinner=False)
def _load_pricing_items_cached(uid: str) -> pd.DataFrame:
    try:
        q = get_sb().table("pricing_items").select("*").order("sort_order")
        if uid:
            q = q.eq("user_id", str(uid))

        res = q.execute()
        rows = getattr(res, "data", None) or []
        df = pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame(columns=["id", "user_id", "modality", "kind", "hours", "price", "currency", "active", "sort_order"])

    if df.empty:
        return pd.DataFrame(columns=["id", "user_id", "modality", "kind", "hours", "price", "currency", "active", "sort_order"])

    defaults = {
        "id": None,
        "user_id": None,
        "modality": "",
        "kind": "",
        "hours": None,
        "price": 0,
        "currency": "TRY",
        "active": True,
        "sort_order": 0,
    }
    for c, default in defaults.items():
        if c not in df.columns:
            df[c] = default

    df["active"] = df["active"].fillna(True).astype(bool)
    df["sort_order"] = pd.to_numeric(df["sort_order"], errors="coerce").fillna(0).astype(int)
    df["modality"] = df["modality"].fillna("").astype(str).str.strip().str.lower()
    df["kind"] = df["kind"].fillna("").astype(str).str.strip().str.lower()
    df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0).astype(int)
    df["currency"] = df["currency"].fillna("TRY").astype(str).str.strip()
    df["hours"] = pd.to_numeric(df["hours"], errors="coerce")

    return df


def load_pricing_items() -> pd.DataFrame:
    uid = get_current_user_id()
    return _load_pricing_items_cached(uid)

def upsert_pricing_item(payload: dict) -> None:
    if not isinstance(payload, dict):
        raise ValueError("payload must be a dict")

    table = "pricing_items"
    item_id = payload.get("id")
    uid = get_current_user_id()

    if uid:
        payload["user_id"] = uid

    clean = {k: v for k, v in payload.items() if k != "id"}

    if item_id is not None and str(item_id).strip() != "":
        q = get_sb().table(table).update(clean).eq("id", int(item_id))
        if uid:
            q = q.eq("user_id", uid)
        resp = q.execute()
    else:
        resp = get_sb().table(table).insert(clean).execute()

    if getattr(resp, "error", None):
        raise RuntimeError(resp.error)
    
    clear_app_caches()

def delete_pricing_item(item_id: int) -> None:
    if item_id is None:
        return

    uid = get_current_user_id()
    q = get_sb().table("pricing_items").delete().eq("id", int(item_id))
    if uid:
        q = q.eq("user_id", uid)
    resp = q.execute()
    clear_app_caches()

    if getattr(resp, "error", None):
        raise RuntimeError(resp.error)

def money_try(x) -> str:
    try:
        return f"{int(round(float(x))):,} TL".replace(",", ".")
    except Exception:
        return str(x)


def _pricing_section(df: pd.DataFrame, modality: str, title_key: str, hourly_default: int) -> None:
    """
    Renders one modality pricing editor (online/offline).
    modality must be lowercase: "online" or "offline"
    title_key must be a translation key.
    """

    st.markdown(f"### {t(title_key)}")

    if df is None or df.empty:
        df = pd.DataFrame(columns=["id", "modality", "kind", "hours", "price", "currency", "active", "sort_order"])
    else:
        df = df.copy()

    # Ensure expected columns exist
    defaults = {
        "id": None,
        "modality": "",
        "kind": "",
        "hours": None,
        "price": 0,
        "currency": "TRY",
        "active": True,
        "sort_order": 0,
    }
    for c, default in defaults.items():
        if c not in df.columns:
            df[c] = default

    # Active only
    df["active"] = df["active"].fillna(True).astype(bool)
    df = df[df["active"] == True].copy()

    # Normalize strings
    df["modality"] = df["modality"].fillna("").astype(str).str.strip().str.lower()
    df["kind"] = df["kind"].fillna("").astype(str).str.strip().str.lower()
    df["currency"] = df["currency"].fillna("TRY").astype(str).str.strip()

    # Numeric
    df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0).astype(int)
    df["hours"] = pd.to_numeric(df["hours"], errors="coerce")  # NaN ok for hourly

    # ---------- Hourly ----------
    hourly = df[(df["modality"] == modality) & (df["kind"] == "hourly")].copy()

    # Seed hourly if missing
    if hourly.empty:
        safe_default = pd.to_numeric(hourly_default, errors="coerce")
        safe_default = 0 if pd.isna(safe_default) else int(safe_default)

        upsert_pricing_item(
            {
                "modality": modality,
                "kind": "hourly",
                "hours": None,
                "price": safe_default,
                "currency": get_preferred_currency(),
                "active": True,
                "sort_order": 0,
            }
        )
        df = load_pricing_items()
        df = df[df["active"] == True].copy()
        hourly = df[(df["modality"] == modality) & (df["kind"] == "hourly")].copy()

    if hourly.empty:
        st.error(t("pricing_hourly_load_error"))
        return

    # If multiple hourly rows exist, use the first by sort_order then id
    hourly = hourly.sort_values(["sort_order", "id"], na_position="last")
    hourly_row = hourly.iloc[0].to_dict()

    _hourly_cur_default = str(hourly_row.get("currency") or get_preferred_currency())
    _hourly_cur_idx = CURRENCY_CODES.index(_hourly_cur_default) if _hourly_cur_default in CURRENCY_CODES else 0

    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        st.caption(t("pricing_hourly_caption"))
    with c2:
        new_hourly_cur = st.selectbox(
            t("payment_currency"),
            CURRENCY_CODES,
            index=_hourly_cur_idx,
            format_func=lambda c: f"{CURRENCIES[c]['symbol']} {c}",
            key=f"hourly_cur_{modality}",
            label_visibility="collapsed",
        )
    with c3:
        new_hourly = st.number_input(
            t("pricing_hourly_price_label"),
            min_value=0,
            step=50,
            value=int(hourly_row.get("price") or 0),
            key=f"hourly_price_{modality}",
            label_visibility="collapsed",
        )

    if int(new_hourly) != int(hourly_row.get("price") or 0) or new_hourly_cur != _hourly_cur_default:
        upsert_pricing_item(
            {
                "id": int(hourly_row["id"]),
                "modality": modality,
                "kind": "hourly",
                "hours": None,
                "price": int(new_hourly),
                "currency": new_hourly_cur,
                "active": True,
                "sort_order": int(hourly_row.get("sort_order") or 0),
            }
        )
        st.success(t("pricing_hourly_updated"))
        st.rerun()

    st.divider()

    # ---------- Packages ----------
    pk = df[(df["modality"] == modality) & (df["kind"] == "package")].copy()
    pk["sort_order"] = pd.to_numeric(pk["sort_order"], errors="coerce").fillna(0).astype(int)
    pk["hours"] = pd.to_numeric(pk["hours"], errors="coerce").fillna(0).astype(int)
    pk = pk.sort_values(["sort_order", "hours", "id"], na_position="last")

    if pk.empty:
        st.info(t("pricing_no_packages"))
    else:
        # Use enumerate to guarantee unique Streamlit widget keys even if duplicate IDs appear
        for i, (_, row) in enumerate(pk.iterrows(), start=1):
            row_id = int(row.get("id") or 0)
            hours = int(row.get("hours") or 0)
            price = int(row.get("price") or 0)
            cur = str(row.get("currency") or "TRY")
            sym = currency_symbol(cur)
            per = int(round(price / hours)) if hours > 0 else 0

            with st.container(border=True):
                a, b, c = st.columns([2, 2, 1])

                with a:
                    st.markdown(f"**{hours} {t('pricing_hours')}**")
                    st.caption(f"≈ {sym} {per:,} {t('pricing_per_hour')}")

                with b:
                    st.markdown(f"**{format_currency(price, cur)}**")

                with c:
                    if st.button(t("pricing_edit"), key=f"edit_pkg_{modality}_{row_id}_{i}"):
                        st.session_state[f"edit_price_id_{modality}"] = row_id

                if st.session_state.get(f"edit_price_id_{modality}") == row_id:
                    e1, e2, e3, e4 = st.columns([1, 1, 1, 1])
                    with e1:
                        new_hours = st.number_input(
                            t("pricing_hours"),
                            min_value=1,
                            step=1,
                            value=max(1, hours),
                            key=f"pkg_hours_{modality}_{row_id}_{i}",
                        )
                    with e2:
                        _edit_cur_idx = CURRENCY_CODES.index(cur) if cur in CURRENCY_CODES else 0
                        new_pkg_cur = st.selectbox(
                            t("payment_currency"),
                            CURRENCY_CODES,
                            index=_edit_cur_idx,
                            format_func=lambda c: f"{CURRENCIES[c]['symbol']} {c}",
                            key=f"pkg_cur_{modality}_{row_id}_{i}",
                        )
                    with e3:
                        new_price = st.number_input(
                            t("pricing_price_label"),
                            min_value=0,
                            step=50,
                            value=price,
                            key=f"pkg_price_{modality}_{row_id}_{i}",
                        )
                    with e4:
                        if st.button(t("pricing_save"), key=f"save_pkg_{modality}_{row_id}_{i}"):
                            upsert_pricing_item(
                                {
                                    "id": row_id,
                                    "modality": modality,
                                    "kind": "package",
                                    "hours": int(new_hours),
                                    "price": int(new_price),
                                    "currency": new_pkg_cur,
                                    "active": True,
                                    "sort_order": int(row.get("sort_order") or new_hours),
                                }
                            )
                            st.session_state[f"edit_price_id_{modality}"] = None
                            st.success(t("pricing_package_updated"))
                            st.rerun()

                        if st.button(t("pricing_delete"), key=f"del_pkg_{modality}_{row_id}_{i}"):
                            delete_pricing_item(row_id)
                            st.session_state[f"edit_price_id_{modality}"] = None
                            st.success(t("pricing_package_deleted"))
                            st.rerun()

    st.divider()

    # ---------- Add package ----------
    st.markdown(f"**{t('pricing_add_package')}**")
    n1, n2, n3, n4 = st.columns([1, 1, 1, 1])

    with n1:
        add_hours = st.number_input(
            t("pricing_hours"),
            min_value=1,
            step=1,
            value=10,
            key=f"add_pkg_hours_{modality}",
        )
    with n2:
        _add_cur_default = get_preferred_currency()
        _add_cur_idx = CURRENCY_CODES.index(_add_cur_default) if _add_cur_default in CURRENCY_CODES else 0
        add_currency = st.selectbox(
            t("payment_currency"),
            CURRENCY_CODES,
            index=_add_cur_idx,
            format_func=lambda c: f"{CURRENCIES[c]['symbol']} {c}",
            key=f"add_pkg_cur_{modality}",
        )
    with n3:
        add_price = st.number_input(
            t("pricing_price_label"),
            min_value=0,
            step=50,
            value=0,
            key=f"add_pkg_price_{modality}",
        )
    with n4:
        if st.button(t("pricing_add"), key=f"add_pkg_btn_{modality}"):
            upsert_pricing_item(
                {
                    "modality": modality,
                    "kind": "package",
                    "hours": int(add_hours),
                    "price": int(add_price),
                    "currency": add_currency,
                    "active": True,
                    "sort_order": int(add_hours),
                }
            )
            st.success(t("pricing_package_added"))
            st.rerun()


def render_pricing_editor() -> None:
    """
    Pricing editor UI. Call this ONLY inside a page (e.g. add_payment).
    """
    with st.expander(t("pricing_editor_title"), expanded=False):

        df = load_pricing_items()

        # Show hint if prices are missing or invalid
        if df.empty or (pd.to_numeric(df.get("price"), errors="coerce").fillna(0) <= 0).all():
            st.info("⚠️ " + t("pricing_set_price_hint"))

        _pricing_section(df, modality="online", title_key="pricing_online_title", hourly_default=0)

        st.divider()

        df = load_pricing_items()
        if df.empty or (pd.to_numeric(df.get("price"), errors="coerce").fillna(0) <= 0).all():
            st.info("⚠️ " + t("pricing_set_price_hint"))        

        _pricing_section(df, modality="offline", title_key="pricing_offline_title", hourly_default=0)

# =========================
