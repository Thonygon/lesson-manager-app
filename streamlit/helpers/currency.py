"""Currency conversion and inflation adjustment utilities."""

import json
import urllib.request
import streamlit as st


# ── Currency definitions ─────────────────────────────────────
CURRENCIES = {
    "TRY": {"symbol": "₺", "name": "Turkish Lira"},
    "USD": {"symbol": "$", "name": "US Dollar"},
    "EUR": {"symbol": "€", "name": "Euro"},
    "GBP": {"symbol": "£", "name": "British Pound"},
    "ARS": {"symbol": "AR$", "name": "Argentine Peso"},
    "BRL": {"symbol": "R$", "name": "Brazilian Real"},
    "MXN": {"symbol": "MX$", "name": "Mexican Peso"},
    "JPY": {"symbol": "¥", "name": "Japanese Yen"},
    "CAD": {"symbol": "C$", "name": "Canadian Dollar"},
    "AUD": {"symbol": "A$", "name": "Australian Dollar"},
    "CHF": {"symbol": "CHF", "name": "Swiss Franc"},
    "COP": {"symbol": "COL$", "name": "Colombian Peso"},
    "CLP": {"symbol": "CL$", "name": "Chilean Peso"},
    "INR": {"symbol": "₹", "name": "Indian Rupee"},
    "KRW": {"symbol": "₩", "name": "South Korean Won"},
    "SEK": {"symbol": "kr", "name": "Swedish Krona"},
    "NOK": {"symbol": "kr", "name": "Norwegian Krone"},
    "DKK": {"symbol": "kr", "name": "Danish Krone"},
    "PLN": {"symbol": "zł", "name": "Polish Zloty"},
    "CNY": {"symbol": "¥", "name": "Chinese Yuan"},
}

CURRENCY_CODES = list(CURRENCIES.keys())

# ── Timezone → currency heuristic ────────────────────────────
_TZ_CURRENCY: dict[str, str] = {
    # Americas
    "America/New_York": "USD", "America/Chicago": "USD", "America/Denver": "USD",
    "America/Los_Angeles": "USD", "America/Phoenix": "USD", "America/Anchorage": "USD",
    "Pacific/Honolulu": "USD", "America/Indiana/Indianapolis": "USD",
    "America/Toronto": "CAD", "America/Vancouver": "CAD", "America/Edmonton": "CAD",
    "America/Winnipeg": "CAD", "America/Halifax": "CAD", "America/St_Johns": "CAD",
    "America/Argentina/Buenos_Aires": "ARS", "America/Argentina/Cordoba": "ARS",
    "America/Sao_Paulo": "BRL", "America/Manaus": "BRL", "America/Belem": "BRL",
    "America/Mexico_City": "MXN", "America/Monterrey": "MXN", "America/Tijuana": "MXN",
    "America/Bogota": "COP", "America/Santiago": "CLP",
    # Europe
    "Europe/Istanbul": "TRY", "Asia/Istanbul": "TRY",
    "Europe/London": "GBP", "Europe/Dublin": "EUR",
    "Europe/Paris": "EUR", "Europe/Berlin": "EUR", "Europe/Rome": "EUR",
    "Europe/Madrid": "EUR", "Europe/Amsterdam": "EUR", "Europe/Brussels": "EUR",
    "Europe/Vienna": "EUR", "Europe/Athens": "EUR", "Europe/Lisbon": "EUR",
    "Europe/Warsaw": "PLN", "Europe/Zurich": "CHF",
    "Europe/Stockholm": "SEK", "Europe/Oslo": "NOK", "Europe/Copenhagen": "DKK",
    # Asia / Pacific
    "Asia/Tokyo": "JPY", "Asia/Seoul": "KRW",
    "Asia/Kolkata": "INR", "Asia/Calcutta": "INR",
    "Asia/Shanghai": "CNY", "Asia/Hong_Kong": "CNY",
    "Australia/Sydney": "AUD", "Australia/Melbourne": "AUD", "Australia/Brisbane": "AUD",
    "Australia/Perth": "AUD",
}


def guess_currency_from_timezone() -> str | None:
    """Return a currency code inferred from the browser timezone, or None if unknown."""
    tz = str(st.session_state.get("browser_tz") or "").strip()
    if not tz:
        return None
    if tz in _TZ_CURRENCY:
        return _TZ_CURRENCY[tz]
    # Try matching by region prefix (e.g. "Europe/Helsinki" → EUR)
    prefix = tz.split("/")[0] if "/" in tz else ""
    region_defaults = {"Europe": "EUR", "America": "USD", "Asia": "USD", "Australia": "AUD"}
    return region_defaults.get(prefix)


def get_preferred_currency() -> str:
    """Return the user's preferred currency code from their profile (default TRY)."""
    return str(st.session_state.get("preferred_currency", "TRY"))


def currency_symbol(code: str = None) -> str:
    """Return the symbol for a currency code (or the user's preferred currency)."""
    if code is None:
        code = get_preferred_currency()
    return CURRENCIES.get(code, {}).get("symbol", code)


def format_currency(x, code: str = None) -> str:
    """Format *x* as a readable currency string with the symbol."""
    if code is None:
        code = get_preferred_currency()
    sym = currency_symbol(code)
    try:
        x = float(x)
        formatted = f"{int(round(x)):,}".replace(",", ".")
        return f"{sym} {formatted}"
    except Exception:
        return str(x)


# ── Countries for inflation (World Bank ISO-3 codes) ─────────
INFLATION_COUNTRIES = {
    "Argentina": "ARG",
    "Australia": "AUS",
    "Brazil": "BRA",
    "Canada": "CAN",
    "Chile": "CHL",
    "China": "CHN",
    "Colombia": "COL",
    "Denmark": "DNK",
    "France": "FRA",
    "Germany": "DEU",
    "India": "IND",
    "Italy": "ITA",
    "Japan": "JPN",
    "Mexico": "MEX",
    "Netherlands": "NLD",
    "Norway": "NOR",
    "Poland": "POL",
    "South Korea": "KOR",
    "Spain": "ESP",
    "Sweden": "SWE",
    "Switzerland": "CHE",
    "Turkey": "TUR",
    "United Kingdom": "GBR",
    "United States": "USA",
}


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_exchange_rates(base: str) -> dict:
    """Fetch current exchange rates from open.er-api.com (free, no key)."""
    try:
        url = f"https://open.er-api.com/v6/latest/{base}"
        req = urllib.request.Request(url, headers={"User-Agent": "ClassioApp/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        if data.get("result") == "success":
            return data.get("rates", {})
    except Exception:
        pass
    return {}


def get_exchange_rate(from_cur: str, to_cur: str) -> float:
    """Exchange rate from *from_cur* to *to_cur*.  Returns 1.0 on same-currency or failure."""
    if from_cur == to_cur:
        return 1.0
    rates = _fetch_exchange_rates(from_cur)
    return float(rates.get(to_cur, 1.0))


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_cpi_data(country_code: str) -> dict:
    """Fetch annual CPI index from the World Bank.  Returns ``{year_int: cpi_float}``."""
    try:
        url = (
            f"https://api.worldbank.org/v2/country/{country_code}"
            f"/indicator/FP.CPI.TOTL?date=2000:2026&format=json&per_page=100"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "ClassioApp/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        if len(data) < 2 or not data[1]:
            return {}
        result = {}
        for entry in data[1]:
            yr = entry.get("date")
            val = entry.get("value")
            if yr and val is not None:
                result[int(yr)] = float(val)
        return result
    except Exception:
        return {}


def inflate(amount: float, from_year: int, to_year: int, cpi: dict) -> float:
    """Adjust *amount* from *from_year* purchasing power to *to_year*.

    Returns the original amount unchanged when CPI data is unavailable.
    """
    if from_year == to_year or not cpi:
        return amount
    c_from = cpi.get(from_year)
    c_to = cpi.get(to_year)
    if not c_from or not c_to or c_from == 0:
        return amount
    return amount * (c_to / c_from)
