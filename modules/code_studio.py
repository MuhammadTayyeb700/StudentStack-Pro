"""💻 Code Studio — AI code generator + mini IDE."""
# pyrefly: ignore [missing-import]
import streamlit as st
# pyrefly: ignore [missing-import]
import streamlit.components.v1 as components

from core import llm, ui
from core.codegen import LANGS, MODES, build_prompt, clamp, run_python, trim_history

# Try streamlit-ace; fall back to st.text_area.
try:
    from streamlit_ace import st_ace  # type: ignore[import-untyped]
    _HAS_ACE = True
except ImportError:
    _HAS_ACE = False

_ACE_LANG_MAP = {
    "Python": "python",
    "JavaScript": "javascript",
    "HTML/CSS/JS": "html",
    "C++": "c_cpp",
    "SQL": "sql",
}


def _editor(lang: str, key: str) -> str:
    """Render the code editor (ace or textarea) and return its content."""
    code = st.session_state.get(key, "")
    if _HAS_ACE:
        new = st_ace(
            value=code,
            language=_ACE_LANG_MAP.get(lang, "text"),
            theme="monokai",
            min_lines=18,
            max_lines=40,
            key=f"_ace_{key}",
            auto_update=True,
        )
        if new is not None:
            st.session_state[key] = new
        return st.session_state.get(key, "")
    return ui.sticky(st.text_area, "Code", key, "", height=400)


def _generate(mode: str, lang: str, request: str, code: str, stderr: str):
    """Call the LLM to generate / fix / refactor code."""
    context = stderr if mode == "Fix / Debug" and stderr else request
    prompt = build_prompt(mode, lang, context, code=clamp(code))
    history = st.session_state.get("cs_history", [])
    history.append({"role": "user", "content": prompt})
    history = trim_history(history)
    st.session_state["cs_history"] = history

    raw = llm.safe_run(
        llm.single,
        role="Code Assistant",
        goal=f"{mode} code in {lang}",
        backstory="An expert programmer who returns only clean, working code.",
        task=prompt,
        expected="A single fenced code block.",
        temperature=0.2,
        max_tokens=1500,
    )
    if raw:
        result = llm.strip_fences(raw)
        st.session_state["cs_code"] = result
        history.append({"role": "assistant", "content": result})
        st.session_state["cs_history"] = trim_history(history)
    return raw


def render():
    ui.page_header("💻", "Code Studio", "Generate, edit, run and fix code with AI.")

    left, right = st.columns([2, 3])

    with left:
        lang = ui.sticky(st.selectbox, "Language", "cs_lang", "Python", options=list(LANGS))
        mode = ui.sticky(st.selectbox, "Mode", "cs_mode", "Generate", options=MODES)
        request = ui.sticky(st.text_area, "What do you need?", "cs_request", "",
                            height=120, placeholder="Describe the code you want…")

        gen_disabled = mode == "Generate" and len(request.strip()) < 5
        if st.button("🚀 Generate", type="primary", disabled=gen_disabled):
            if ui.need_key():
                with st.spinner("Writing code…"):
                    _generate(mode, lang, request, st.session_state.get("cs_code", ""),
                              st.session_state.get("cs_stderr", ""))

        # "Fix with AI" sends code + last stderr
        stderr = st.session_state.get("cs_stderr", "")
        if stderr and st.button("✨ Fix with AI"):
            if ui.need_key():
                with st.spinner("Fixing…"):
                    _generate("Fix / Debug", lang, "", st.session_state.get("cs_code", ""), stderr)

    with right:
        code = _editor(lang, "cs_code")

        btn_cols = st.columns(4)

        # Run (Python only)
        with btn_cols[0]:
            can_run = lang == "Python" and bool(code.strip())
            if st.button("▶️ Run", disabled=not can_run):
                with st.spinner("Running…"):
                    stdout, stderr_out, rc = run_python(code)
                    st.session_state["cs_stdout"] = stdout
                    st.session_state["cs_stderr"] = stderr_out
                    st.session_state["cs_rc"] = rc

        # Download
        with btn_cols[1]:
            ext = LANGS.get(lang, ".txt")
            fname = f"code_studio{ext}"
            st.download_button("⬇️ Download", code or "", fname,
                               mime="text/plain", disabled=not code.strip())

        # Copy-friendly view
        with btn_cols[2]:
            if st.button("📋 View", disabled=not code.strip()):
                st.session_state["cs_show_code"] = not st.session_state.get("cs_show_code", False)

        # HTML/CSS/JS live preview
        with btn_cols[3]:
            if lang == "HTML/CSS/JS" and code.strip():
                if st.button("🌐 Preview"):
                    st.session_state["cs_preview"] = True

        # Copy-friendly st.code view
        if st.session_state.get("cs_show_code") and code.strip():
            lang_hint = _ACE_LANG_MAP.get(lang, "")
            st.code(code, language=lang_hint)

        # HTML preview (sandboxed)
        if lang == "HTML/CSS/JS" and st.session_state.get("cs_preview") and code.strip():
            components.html(code, height=400, scrolling=True)

        # Output panel
        stdout = st.session_state.get("cs_stdout", "")
        stderr_val = st.session_state.get("cs_stderr", "")
        rc = st.session_state.get("cs_rc")
        if stdout or stderr_val or rc is not None:
            st.markdown("#### Output")
            if stdout:
                st.text(stdout[:5000])
            if stderr_val:
                st.error(stderr_val[:3000])
            if rc is not None:
                st.caption(f"Exit code: {rc}")
