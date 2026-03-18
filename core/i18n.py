import streamlit as st
from translations import I18N


def t(key: str, **kwargs) -> str:
    lang = st.session_state.get("ui_lang", "en")
    s = I18N.get(lang, I18N["en"]).get(key, key)
    try:
        return s.format(**kwargs)
    except Exception:
        return s
