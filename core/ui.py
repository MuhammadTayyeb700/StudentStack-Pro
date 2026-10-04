from __future__ import annotations

import html

import streamlit as st

CSS = """
<style>
.block-container{padding-top:3.2rem;max-width:1250px}
button[aria-label="Show password text"],button[aria-label="Hide password text"]{display:none !important}
.hero{background:linear-gradient(120deg,#4f46e5 0%,#7c3aed 55%,#db2777 100%);padding:2rem 2.2rem;border-radius:20px;
 margin-bottom:1.2rem;box-shadow:0 10px 30px rgba(79,70,229,.25)}
.hero h1{margin:0;font-size:2.1rem;color:#fff !important;padding:0}
.hero p{margin:.45rem 0 0;color:#eef;font-size:1.05rem}
.phead{display:flex;gap:.9rem;align-items:center;padding:.9rem 1.1rem;border-radius:16px;
 background:rgba(99,102,241,.09);border:1px solid rgba(99,102,241,.25);margin-bottom:1rem}
.phead h2{margin:0;padding:0;font-size:1.35rem}
.phead p{margin:.1rem 0 0;opacity:.75;font-size:.92rem}
.pico{font-size:2rem}
div.stButton>button,div.stDownloadButton>button,a[data-testid="stBaseLinkButton-secondary"]{border-radius:12px;font-weight:600}
div.stButton>button[kind="primary"]{background:linear-gradient(120deg,#4f46e5,#7c3aed);border:0;color:#fff}
.stTabs [data-baseweb="tab"]{border-radius:10px 10px 0 0;padding:.5rem 1rem}
.paper{background:#fff;color:#1f2937;border-radius:12px;padding:1.4rem 1.6rem;border:1px solid #e5e7eb;
 box-shadow:0 2px 10px rgba(0,0,0,.06);line-height:1.6;white-space:pre-wrap}
.lcard{background:#fff;color:#1f2937;border:1px solid #e5e7eb;border-radius:12px;padding:1rem 1.2rem;
 box-shadow:0 2px 8px rgba(0,0,0,.06);white-space:pre-wrap;line-height:1.5;font-size:.95rem}
.lcard .who{font-weight:700}.lcard .sub{color:#6b7280;font-size:.8rem;margin-bottom:.6rem}
.flash{word-break:break-word;border-radius:18px;padding:2.2rem 1.6rem;text-align:center;font-size:1.25rem;min-height:170px;
 display:flex;align-items:center;justify-content:center;color:#fff;
 background:linear-gradient(135deg,#4f46e5,#7c3aed);box-shadow:0 8px 24px rgba(79,70,229,.3)}
.flash.back{background:linear-gradient(135deg,#059669,#0d9488)}
mark.i-repeat{background:#fecaca}mark.i-passive{background:#fde68a}mark.i-weak{background:#e9d5ff}
mark.i-long{background:#bfdbfe}mark.i-cliche{background:#fbcfe8}mark.i-case{background:#fed7aa}
ins{background:#bbf7d0;text-decoration:none}del{background:#fecaca}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def hero(title: str, sub: str) -> None:
    st.markdown(f'<div class="hero"><h1>{html.escape(title)}</h1><p>{html.escape(sub)}</p></div>',
                unsafe_allow_html=True)


def page_header(icon: str, title: str, desc: str) -> None:
    st.markdown(f'<div class="phead"><span class="pico">{icon}</span><div><h2>{html.escape(title)}</h2>'
                f'<p>{html.escape(desc)}</p></div></div>', unsafe_allow_html=True)


def need_key() -> bool:
    from core import llm
    if llm.get_api_key():
        return True
    st.info("🔑 AI features are not configured yet. The app owner must add `GROQ_API_KEY` to the server secrets.")
    return False


def keep(*keys: str) -> None:
    """Streamlit drops widget state when you leave a page. Re-assigning the value keeps it."""
    for k in keys:
        if k in st.session_state:
            st.session_state[k] = st.session_state[k]


def sticky(fn, label: str, key: str, default=None, **kw):
    """Create a widget whose value survives switching between tools."""
    if key in st.session_state:
        st.session_state[key] = st.session_state[key]
    else:
        st.session_state[key] = default
    return fn(label, key=key, **kw)
