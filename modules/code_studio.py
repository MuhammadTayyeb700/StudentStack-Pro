"""💻 Code Studio - multi-file mini IDE with an AI assistant.

Code runs in the visitor's browser (Pyodide / JS in a Web Worker, see static/ide_runner),
never on the server, so it is safe on a public deployment."""
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from core import llm, ui
from core.codegen import (MAX_FILES, MODES, REPLACE_MODES, STARTER, ace_mode, build_prompt, clamp, inline_assets,
                          lang_for, make_zip, run_kind, valid_name)

try:
    from streamlit_ace import st_ace
    _HAS_ACE = True
except ImportError:  # falls back to a plain text box
    _HAS_ACE = False

_RUNNER = components.declare_component(
    "ide_runner", path=str(Path(__file__).resolve().parent.parent / "static" / "ide_runner"))
THEMES = ["monokai", "dracula", "tomorrow_night", "github", "solarized_light", "chrome"]
KEYS = ["vscode", "sublime", "vim", "emacs"]
HINTS = {"Generate": "Describe what to build…", "Edit": "Describe the change to make…",
         "Fix / Debug": "Optional: what's going wrong? (the last error is used automatically)",
         "Explain": "Optional: what should I focus on?", "Refactor": "Optional notes",
         "Add tests": "Optional notes", "Add comments": "Optional notes"}
MAX_EDIT_CHARS = 8000


# ------------------------------------------------------------------ state
def _init() -> None:
    ss = st.session_state
    ss.setdefault("cs_files", dict(STARTER))
    ss.setdefault("cs_ver", {})
    ss.setdefault("cs_run_id", 0)
    ss.setdefault("cs_done_id", 0)
    ss.setdefault("cs_run_entry", "")
    for k, v in (("cs_theme", "monokai"), ("cs_font", 14), ("cs_wrap", False), ("cs_keys", "vscode"),
                 ("cs_mode", "Generate"), ("cs_request", ""), ("cs_stdin", "")):
        ss.setdefault(k, v)
    if ss.get("cs_active") not in ss["cs_files"]:
        ss["cs_active"] = next(iter(ss["cs_files"]))


def _queue(mode: str) -> None:
    st.session_state["cs_action"] = mode


def _queue_current() -> None:
    st.session_state["cs_action"] = st.session_state["cs_mode"]


def _run_cb() -> None:
    ss = st.session_state
    ss["cs_run_id"] += 1
    ss["cs_run_entry"] = ss["cs_active"]
    ss.pop("cs_out", None)


def _create_cb() -> None:
    ss = st.session_state
    name = (ss.get("cs_newname") or "").strip()
    err = valid_name(name, ss["cs_files"])
    if err:
        st.toast(err, icon="⚠️")
        return
    ss["cs_files"][name] = ""
    ss["cs_active"] = name
    ss["cs_newname"] = ""


def _rename_cb() -> None:
    ss = st.session_state
    old, new = ss["cs_active"], (ss.get("cs_renamed") or "").strip()
    err = valid_name(new, {k: 1 for k in ss["cs_files"] if k != old})
    if err:
        st.toast(err, icon="⚠️")
        return
    ss["cs_files"] = {(new if k == old else k): v for k, v in ss["cs_files"].items()}
    ss["cs_ver"][new] = ss["cs_ver"].pop(old, 0) + 1
    ss["cs_active"] = new


def _delete_cb() -> None:
    ss = st.session_state
    if len(ss["cs_files"]) > 1:
        ss["cs_files"].pop(ss["cs_active"], None)
        ss["cs_active"] = next(iter(ss["cs_files"]))


def _save_note_cb() -> None:
    ss = st.session_state
    base = ss["cs_active"]
    name = f"test_{base}" if not base.startswith("test_") else f"new_{base}"
    if valid_name(name, ss["cs_files"]):
        st.toast("Could not add a file (name taken or limit reached).", icon="⚠️")
        return
    ss["cs_files"][name] = ss["cs_note"][1]
    ss["cs_active"] = name
    ss.pop("cs_note", None)


# ------------------------------------------------------------------ AI
def _handle_ai() -> None:
    ss = st.session_state
    mode = ss.pop("cs_action", None)
    if not mode:
        return
    files, active = ss["cs_files"], ss["cs_active"]
    code, lang = files[active], lang_for(active)
    if mode != "Generate" and not code.strip():
        st.warning("This file is empty. Write or generate some code first.")
        return
    if mode in REPLACE_MODES and mode != "Generate" and len(code) > MAX_EDIT_CHARS:
        st.warning(f"This file is longer than {MAX_EDIT_CHARS} characters; split it into smaller files first.")
        return
    if not ui.need_key():
        return
    request = ss.get("cs_request", "")
    if mode == "Fix / Debug":
        request = (ss.get("cs_out") or {}).get("stderr") or request or "it does not work as intended"
    prompt = build_prompt(mode, lang, request, code=clamp(code, MAX_EDIT_CHARS))
    with st.spinner(f"{mode}…"):
        raw = llm.safe_run(llm.single, role="Code Assistant", goal=f"{mode} {lang} code",
                           backstory="An expert programmer who returns only clean, working code.",
                           task=prompt, expected="A single fenced code block.", temperature=0.2, max_tokens=1500)
    if not raw:
        return
    if mode in REPLACE_MODES:
        files[active] = llm.strip_fences(raw)
        ss["cs_ver"][active] = ss["cs_ver"].get(active, 0) + 1
        ss.pop("cs_note", None)
    elif mode == "Add tests":
        ss["cs_note"] = (mode, llm.strip_fences(raw))
    else:
        ss["cs_note"] = (mode, raw.strip())


def _ai_panel(active: str) -> None:
    ss = st.session_state
    st.markdown("##### ✨ AI assistant")
    st.caption(f"Works on **{active}**")
    mode = st.selectbox("Action", MODES, key="cs_mode")
    st.text_area("Request", key="cs_request", height=130, placeholder=HINTS.get(mode, ""),
                 label_visibility="collapsed")
    need = mode in ("Generate", "Edit") and len(ss["cs_request"].strip()) < 5
    st.button(f"🚀 {mode}", type="primary", on_click=_queue_current, disabled=need, use_container_width=True)
    note = ss.get("cs_note")
    if note:
        with st.container(border=True):
            st.markdown(f"**{note[0]}**")
            if note[0] == "Add tests":
                st.code(note[1], language="python")
                st.button("➕ Save as new file", on_click=_save_note_cb)
            else:
                st.markdown(note[1])
            if st.button("Dismiss", key="cs_dismiss"):
                ss.pop("cs_note", None)
                st.rerun()


# ------------------------------------------------------------------ editor
def _settings() -> None:
    with st.popover("⚙️"):
        st.selectbox("Theme", THEMES, key="cs_theme")
        st.slider("Font size", 11, 22, key="cs_font")
        st.selectbox("Keybindings", KEYS, key="cs_keys")
        st.checkbox("Wrap long lines", key="cs_wrap")


def _editor(active: str) -> None:
    ss = st.session_state
    files = ss["cs_files"]
    if _HAS_ACE:
        new = st_ace(value=files[active], language=ace_mode(active), theme=ss["cs_theme"],
                     font_size=ss["cs_font"], wrap=ss["cs_wrap"], tab_size=4, show_gutter=True,
                     show_print_margin=False, keybinding=ss["cs_keys"],
                     min_lines=24, max_lines=24, auto_update=True,
                     key=f"ace_{active}_{ss['cs_ver'].get(active, 0)}")
    else:
        new = st.text_area("Code", files[active], height=480, key=f"ta_{active}_{ss['cs_ver'].get(active, 0)}")
    if new is not None:
        files[active] = new


def _output(active: str) -> None:
    ss = st.session_state
    files = ss["cs_files"]
    kind = run_kind(ss["cs_run_entry"]) if ss["cs_run_entry"] in files else None
    pending = ss["cs_run_id"] > ss["cs_done_id"]
    res = _RUNNER(files=files, entry=ss["cs_run_entry"], lang=kind, stdin=ss["cs_stdin"], timeout=20,
                  run_id=ss["cs_run_id"] if pending else 0, key="cs_runner", default=None)
    if pending and res and res.get("run_id") == ss["cs_run_id"]:
        ss["cs_out"], ss["cs_done_id"] = res, ss["cs_run_id"]
        pending = False
    if pending:
        st.info("⏳ Running… the first Python run downloads the runtime (about 10 s).")
        return
    out = ss.get("cs_out")
    if not out:
        return
    st.markdown(f"#### Output · `{ss['cs_run_entry']}`")
    st.code(out.get("stdout") or "(no output)", language=None)
    if out.get("stderr"):
        st.error("Error")
        st.code(out["stderr"], language=None)
        st.button("✨ Fix with AI", on_click=_queue, args=("Fix / Debug",))
    st.caption(f"Finished in {out.get('ms', 0) / 1000:.1f} s · ran in your browser")


def render() -> None:
    ui.page_header("💻", "Code Studio", "Write, run and fix code with AI, all in your browser.")
    _init()
    _handle_ai()
    ss = st.session_state
    files = ss["cs_files"]

    bar = st.columns([6, 1.2, 1.2, 0.8, 1.4])
    with bar[0]:
        st.radio("Files", list(files), key="cs_active", horizontal=True, label_visibility="collapsed")
    active = ss["cs_active"]
    with bar[1].popover("➕ New", use_container_width=True):
        st.text_input("File name", key="cs_newname", placeholder="utils.py")
        st.button("Create", on_click=_create_cb)
    with bar[2].popover("✏️ Rename", use_container_width=True):
        if ss.get("cs_ren_for") != active:
            ss["cs_renamed"], ss["cs_ren_for"] = active, active
        st.text_input("New name", key="cs_renamed", placeholder=active)
        st.button("Rename", on_click=_rename_cb)
    with bar[3].popover("🗑", use_container_width=True):
        st.write(f"Delete **{active}**?")
        st.button("Delete", on_click=_delete_cb, disabled=len(files) <= 1)

    left, right = st.columns([3, 1.25])
    with right:
        _ai_panel(active)
    with left:
        tools = st.columns([1.3, 0.7, 4])
        kind = run_kind(active)
        with tools[1]:
            _settings()
        tools[2].caption(f"{lang_for(active)} · {len(files)}/{MAX_FILES} files · runs in your browser")
        _editor(active)
        # Rendered AFTER the editor so they always see the latest typed code.
        tools[0].button("▶️ Run", type="primary", on_click=_run_cb, disabled=not kind,
                        help=None if kind else "Run supports .py and .js files", use_container_width=True)
        bar[4].download_button("⬇️ ZIP", make_zip(files), "code_studio.zip", mime="application/zip",
                               use_container_width=True)
        if kind == "python":
            with st.expander("⌨️ Program input (stdin, one line per input() call)"):
                st.text_area("stdin", key="cs_stdin", height=70, label_visibility="collapsed")
        _output(active)
        if active.lower().endswith(".html") and files[active].strip():
            st.markdown("#### 🌐 Live preview")
            components.html(inline_assets(files[active], files), height=420, scrolling=True)
