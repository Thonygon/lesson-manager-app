from __future__ import annotations

from contextlib import contextmanager

import streamlit as st

from core.i18n import t


@contextmanager
def action_spinner(message_key: str = "processing_action"):
    """Show a consistent busy state for user-triggered mutations."""
    with st.spinner(t(message_key)):
        yield

