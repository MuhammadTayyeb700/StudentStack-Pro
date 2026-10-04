"""Usage protection for a shared server key: optional access code + request caps.

Settings (Streamlit secrets or environment variables, all optional):
  ACCESS_CODE    visitors must enter this code before they can use the app
  SESSION_LIMIT  max AI requests per browser session   (default 60, 0 = unlimited)
  DAILY_LIMIT    max AI requests per day, all visitors (default 500, 0 = unlimited)
The access code is never stored in session state, only the fact that it was accepted.
"""
from __future__ import annotations

import hmac
import os
import threading
import time
from datetime import date

import streamlit as st

DEFAULT_SESSION_LIMIT = 60
DEFAULT_DAILY_LIMIT = 500
MAX_FAILS = 5
LOCK_SECONDS = 60
_LOCK = threading.Lock()


class LimitReached(Exception):
    """Friendly message, safe to show to the user."""


# ------------------------------------------------------------------ pure helpers (unit-tested)
def check_code(given: str, expected: str) -> bool:
    return bool(expected) and hmac.compare_digest(str(given).encode(), str(expected).encode())


def consume(session, store: dict, session_limit: int, daily_limit: int, today: str) -> None:
    """Count one AI request or raise LimitReached. `store` is the counter shared by all visitors."""
    with _LOCK:
        if store.get("day") != today:
            store["day"], store["count"] = today, 0
        if session_limit and session.get("_used", 0) >= session_limit:
            raise LimitReached(f"You've used the {session_limit} AI requests allowed in one session. "
                               "Please try again later.")
        if daily_limit and store.get("count", 0) >= daily_limit:
            raise LimitReached("Today's shared AI quota is used up. Please try again tomorrow.")
        store["count"] = store.get("count", 0) + 1
        session["_used"] = session.get("_used", 0) + 1


# ------------------------------------------------------------------ settings
def _setting(name: str) -> str:
    try:
        val = st.secrets.get(name, "")
    except Exception:  # no secrets file
        val = ""
    return str(val or os.getenv(name, "")).strip()


def _int(name: str, default: int) -> int:
    raw = _setting(name)
    try:
        return max(int(raw), 0) if raw else default
    except ValueError:
        return default


@st.cache_resource
def _store() -> dict:
    return {"day": "", "count": 0}


def consume_request() -> None:
    consume(st.session_state, _store(), _int("SESSION_LIMIT", DEFAULT_SESSION_LIMIT),
            _int("DAILY_LIMIT", DEFAULT_DAILY_LIMIT), date.today().isoformat())


def usage_caption() -> str:
    sl, dl = _int("SESSION_LIMIT", DEFAULT_SESSION_LIMIT), _int("DAILY_LIMIT", DEFAULT_DAILY_LIMIT)
    store = _store()
    today = store["count"] if store.get("day") == date.today().isoformat() else 0
    used = st.session_state.get("_used", 0)
    return (f"Requests: {used}/{sl or '∞'} this session · {today}/{dl or '∞'} today (all visitors)")


# ------------------------------------------------------------------ access gate
def require_access() -> bool:
    """Show an access-code form when ACCESS_CODE is set. Returns True when the visitor may continue."""
    code = _setting("ACCESS_CODE")
    if not code or st.session_state.get("_auth_ok"):
        return True
    st.markdown("## 🔒 Private app")
    st.caption("Enter the access code you were given to continue.")
    with st.form("access_gate"):
        entered = st.text_input("Access code", type="password")
        go = st.form_submit_button("Unlock", type="primary")
    if go:
        wait = st.session_state.get("_lock_until", 0) - time.time()
        if wait > 0:
            st.error(f"Too many attempts. Try again in {int(wait) + 1} seconds.")
        elif check_code(entered, code):
            st.session_state["_auth_ok"] = True
            st.session_state.pop("_fails", None)
            st.rerun()
        else:
            fails = st.session_state.get("_fails", 0) + 1
            if fails >= MAX_FAILS:
                st.session_state["_lock_until"] = time.time() + LOCK_SECONDS
                fails = 0
            st.session_state["_fails"] = fails
            st.error("Wrong access code.")
    return False
