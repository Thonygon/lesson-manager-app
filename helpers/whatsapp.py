import streamlit as st
import datetime, re, urllib.parse
from core.i18n import t
from core.state import get_current_user_id
from core.timezone import now_local, today_local, get_app_tz
from core.database import get_sb, load_table, load_students
import pandas as pd
from helpers.pricing import load_pricing_items, money_try

# 07.4) WHATSAPP HELPERS
# =========================

def _digits_only(s: str) -> str:
    return re.sub(r"\D+", "", str(s or ""))


def normalize_phone_for_whatsapp(raw_phone: str) -> str:
    """
    WhatsApp expects international format digits only (no +).
    Designed for Turkey numbers but tolerant of other formats.

    Examples:
      +90 5xx xxx xx xx  -> 905xxxxxxxxx
      05xx xxx xx xx     -> 905xxxxxxxxx
      5xx xxx xx xx      -> 905xxxxxxxxx
      00<country><num>   -> <country><num>
    """
    d = _digits_only(raw_phone)
    if not d:
        return ""

    # Remove leading 00
    if d.startswith("00") and len(d) > 2:
        d = d[2:]

    # Already looks like an international number (e.g., 90xxxxxxxxxx, 4917..., 1...)
    # Keep as-is if >= 11 digits and doesn't start with trunk '0'
    if len(d) >= 11 and not d.startswith("0"):
        return d

    # Turkey specific normalization
    # 0 + 10 digits starting with 5xxxxxxxxx  -> add country code
    if len(d) == 11 and d.startswith("0") and d[1] == "5":
        return "90" + d[1:]

    # 10 digits starting with 5xxxxxxxxx -> add country code
    if len(d) == 10 and d.startswith("5"):
        return "90" + d

    # If we can't safely normalize, return empty (so we fall back to wa.me/?text=...)
    return ""


def build_whatsapp_url(message: str, raw_phone: str = "") -> str:
    encoded = urllib.parse.quote(message or "")
    phone = normalize_phone_for_whatsapp(raw_phone)
    if phone:
        return f"https://wa.me/{phone}?text={encoded}"
    return f"https://wa.me/?text={encoded}"


def _msg_lang_label(lang: str) -> str:
    return {"en": "English", "es": "Español", "tr": "Türkçe"}.get(lang, lang)


def _package_status_text(status: str, lang: str) -> str:
    """
    status expected like: 'almost_finished', 'finished', etc.
    We map 'almost'/'soon' variations → "almost finished"
    """
    s = str(status or "").strip().casefold()
    is_almost = (
        ("almost_finished" in s)
        or ("almost" in s)
        or ("finish_soon" in s)
        or ("soon" in s)
        or ("about" in s and "finish" in s)
    )

    if lang == "es":
        return "por terminar" if is_almost else "finalizado"
    if lang == "tr":
        return "bitmek üzere" if is_almost else "tamamlandı"
    return "almost finished" if is_almost else "finished"


def build_msg_confirm(name: str, lang: str, time_text: str = "") -> str:
    """
    Template #2: confirm today's lesson (EN/ES/TR)
    time_text optional; if empty, we omit time.
    """
    name = (name or "").strip()
    tt = (time_text or "").strip()

    if lang == "es":
        return (
            f"Hola {name}! Solo para confirmar nuestra clase de hoy"
            f"{f' a las {tt}' if tt else ''}. ¿Todo bien por tu lado?"
        )
    if lang == "tr":
        return (
            f"Merhaba {name}! Bugünkü dersimizi"
            f"{f' {tt} için' if tt else ''} teyit etmek istiyorum. Sizin için uygun mu?"
        )
    return (
        f"Hi {name}! Just confirming our lesson today"
        f"{f' at {tt}' if tt else ''}. Is everything okay for you?"
    )


def build_msg_cancel(name: str, lang: str) -> str:
    """
    Template #3: cancel today's lesson (EN/ES/TR)
    """
    name = (name or "").strip()

    if lang == "es":
        return f"Hola {name}. Lo siento, pero necesito cancelar la clase de hoy. ¿Quieres reprogramarla?"
    if lang == "tr":
        return f"Merhaba {name}. Üzgünüm, bugünkü dersi iptal etmem gerekiyor. Yeniden planlayalım mı?"
    return f"Hi {name}. I’m sorry, but I need to cancel today’s lesson. Would you like to reschedule?"


def build_msg_package_header(name: str, lang: str, status: str) -> str:
    """
    Template #1 header: finished / almost finished package (EN/ES/TR)
    Pricing block is appended separately.
    """
    name = (name or "").strip()
    stxt = _package_status_text(status, lang)

    if lang == "es":
        return (
            f"Hola {name}! Espero que estés bien.\n"
            f"Tu paquete actual está {stxt}. Si quieres continuar, aquí están mis precios actuales:\n"
        )
    if lang == "tr":
        return (
            f"Merhaba {name}, umarım iyisinizdir.\n"
            f"Mevcut paketiniz {stxt}. Devam etmek isterseniz güncel fiyatlarım aşağıdadır:\n"
        )
    return (
        f"Hi {name}! Hope you’re doing well.\n"
        f"Your current package is {stxt}. If you’d like to continue, here are my current prices:\n"
    )


def _get_pricing_snapshot() -> dict:
    """
    Loads active pricing from Supabase via load_pricing_items().

    Returns:
      {
        "online_hourly": int,
        "offline_hourly": int,
        "online_packages": [(hours:int, price:int, per:int), ...],
        "offline_packages": [(hours:int, price:int, per:int), ...],
      }
    """
    df = load_pricing_items()
    if df is None or df.empty:
        return {
            "online_hourly": 0,
            "offline_hourly": 0,
            "online_packages": [],
            "offline_packages": [],
        }

    df = df.copy()
    if "active" in df.columns:
        df = df[df["active"] == True].copy()

    # normalize
    df["modality"] = df["modality"].fillna("").astype(str).str.strip().str.lower()
    df["kind"] = df["kind"].fillna("").astype(str).str.strip().str.lower()
    # Support both old column name (price_try) and new renamed column (price)
    price_col = "price" if "price" in df.columns else "price_try"
    df["price_try"] = pd.to_numeric(df[price_col], errors="coerce").fillna(0).astype(int)
    df["hours"] = pd.to_numeric(df["hours"], errors="coerce")  # NaN ok for hourly

    def _hourly(mod: str) -> int:
        h = df[(df["modality"] == mod) & (df["kind"] == "hourly")].copy()
        if h.empty:
            return 0
        if "sort_order" in h.columns:
            h["sort_order"] = pd.to_numeric(h["sort_order"], errors="coerce").fillna(0).astype(int)
            h = h.sort_values(["sort_order", "id"], na_position="last")
        return int(h.iloc[0].get("price_try") or 0)

    def _packages(mod: str) -> list:
        p = df[(df["modality"] == mod) & (df["kind"] == "package")].copy()
        if p.empty:
            return []
        p["hours"] = pd.to_numeric(p["hours"], errors="coerce").fillna(0).astype(int)
        p["sort_order"] = pd.to_numeric(p.get("sort_order", 0), errors="coerce").fillna(0).astype(int)

        # Sort packages: sort_order ascending, then hours descending (e.g., 44, 20, 10, 5)
        p = p.sort_values(["sort_order", "hours"], ascending=[True, False], na_position="last")

        out = []
        for _, r in p.iterrows():
            hours = int(r.get("hours") or 0)
            price = int(r.get("price_try") or 0)
            if hours <= 0:
                continue
            per = int(round(price / hours))
            out.append((hours, price, per))
        return out

    return {
        "online_hourly": _hourly("online"),
        "offline_hourly": _hourly("offline"),
        "online_packages": _packages("online"),
        "offline_packages": _packages("offline"),
    }


def build_pricing_block(lang: str = "tr") -> str:
    """
    WhatsApp-friendly pricing list built from pricing_items.
    Prints both online and offline sections (matches your original Turkish message style).
    """
    s = _get_pricing_snapshot()

    online_hourly = int(s.get("online_hourly") or 0)
    offline_hourly = int(s.get("offline_hourly") or 0)
    online_pk = s.get("online_packages") or []
    offline_pk = s.get("offline_packages") or []

    # ---- Text labels ----
    if lang == "es":
        header = "📌 Las clases duran 50–60 minutos (1 hora).\n"
        online_title = "💻 Precios de clases online:\n"
        offline_title = "🏫 Precios de clases presenciales:\n"
        hourly_note = "*La clase se paga el mismo día.\n"
        prepaid_title = "📦 Paquetes online (prepago):\n"
        prepaid_note = "*El pago debe hacerse antes de empezar. Puedes tomar clases con la frecuencia que quieras.\n"
        offline_pk_title = "📦 Paquetes presenciales (prepago):\n"
        line_hourly = lambda price: f"1 hora → {money_try(price)}\n"
        line_pkg = lambda h, price, per: f"{h} horas → {money_try(price)} (≈ {money_try(per)} / hora)\n"
        no_online_hourly = "(No hay precio por hora online configurado)\n"
        no_online_pk = "(No hay paquetes online)\n"
        no_offline_pk = "(No hay paquetes presenciales)\n"

    elif lang == "en":
        header = "📌 Lessons are 50–60 minutes (1 hour).\n"
        online_title = "💻 Online lesson prices:\n"
        offline_title = "🏫 In-person lesson prices:\n"
        hourly_note = "*Each lesson is paid on the same day.\n"
        prepaid_title = "📦 Online prepaid packages:\n"
        prepaid_note = "*Payment must be made before starting. Lessons can be taken as frequently as you want.\n"
        offline_pk_title = "📦 In-person prepaid packages:\n"
        line_hourly = lambda price: f"1 hour → {money_try(price)}\n"
        line_pkg = lambda h, price, per: f"{h} hours → {money_try(price)} (≈ {money_try(per)} / hour)\n"
        no_online_hourly = "(No online hourly price set)\n"
        no_online_pk = "(No online packages)\n"
        no_offline_pk = "(No in-person packages)\n"

    else:  # TR default
        header = "Derslerim 50-60 dakika sürer (1 saat).\n"
        online_title = "Çevrimiçi ders fiyatları:\n"
        offline_title = "Yüz yüze ders fiyatları:\n"
        hourly_note = "*Her ders aynı gün ödenmelidir.\n"
        prepaid_title = "Çevrimiçi Ders Ön ödemeli paketler:\n"
        prepaid_note = "*Kursa başlamadan önce ödeme yapılmalıdır. Dersler istediğiniz sıklıkta alınabilir.\n"
        offline_pk_title = "Yüz yüze Ders Ön ödemeli paketler:\n"
        line_hourly = lambda price: f"1 saat → {money_try(price)}\n"
        line_pkg = lambda h, price, per: f"{h} saat → {money_try(price)} (≈ {money_try(per)} ders/saati)\n"
        no_online_hourly = "(Çevrimiçi saat ücreti ayarlanmamış)\n"
        no_online_pk = "(Çevrimiçi paket yok)\n"
        no_offline_pk = "(Yüz yüze paket yok)\n"

    # ---- Build block ----
    out = []
    out.append(header)

    # Online
    out.append(online_title)
    if online_hourly > 0:
        out.append(line_hourly(online_hourly))
        out.append(hourly_note)
    else:
        out.append(no_online_hourly)

    out.append("\n" + prepaid_title)
    if online_pk:
        for h, price, per in online_pk:
            out.append(line_pkg(h, price, per))
        out.append(prepaid_note)
    else:
        out.append(no_online_pk)

    # Offline
    out.append("\n" + offline_title)

    # Optional: include offline hourly in EN/ES only (as you had it)
    if offline_hourly > 0 and lang in ("en", "es"):
        out.append(line_hourly(offline_hourly))
        out.append(hourly_note)

    out.append("\n" + offline_pk_title)
    if offline_pk:
        for h, price, per in offline_pk:
            out.append(line_pkg(h, price, per))
        out.append(prepaid_note)
    else:
        out.append(no_offline_pk)

    return "".join(out).strip() + "\n"
# =========================
