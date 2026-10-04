"""Student Stack Pro — 12 study and career tools in one Streamlit app (CrewAI + Groq)."""
import importlib

# pyrefly: ignore [missing-import]
import streamlit as st

st.set_page_config(page_title="Student Stack Pro", page_icon="🎓", layout="wide", initial_sidebar_state="expanded")

try:
    from core import backup, guard, llm, ui  # noqa: E402  (must come after set_page_config)
except Exception as _exc:  # noqa: BLE001  - Streamlit redacts import errors; show file/line (never secrets)
    import sys
    st.error(f"Startup error: {type(_exc).__name__} in {getattr(_exc, 'filename', None) or 'an imported module'}, "
             f"line {getattr(_exc, 'lineno', '?')}: {getattr(_exc, 'msg', None) or str(_exc)[:200]}")
    st.code((getattr(_exc, "text", None) or "").strip() or "(no source line available)")
    st.caption(f"Running on Python {sys.version.split()[0]}. This app needs Python 3.10 or newer.")
    st.stop()

PAGES = {
    "🏠 Home": (None, ""),
    "🔎 Research Agents": ("modules.research", "Reports, summaries and study guides from any topic."),
    "✉️ Email Writer": ("modules.email_agent", "Polished emails in any tone and language."),
    "💼 LinkedIn Posts": ("modules.linkedin", "Posts in your voice, with hooks and hashtags."),
    "💌 Cover Letter": ("modules.cover_letter", "Tailored letters built from your resume and a job ad."),
    "📚 PDF Study Lab": ("modules.study_rag", "RAG over your PDFs: notes, flashcards, Q&A."),
    "🖼️ Slide Reader": ("modules.slides", "Slides in, comprehensive notes and quizzes out."),
    "🎞️ Slideshow Maker": ("modules.slideshow", "Topic in, editable slideshow out (.pptx or web)."),
    "🧾 Essay Feedback": ("modules.essay", "Scored feedback, priority fixes and sentence tips."),
    "🗓️ Timetable Maker": ("modules.timetable", "Clash-free weekly plan with .ics export."),
    "📅 Study Tracker": ("modules.study_tracker", "Deadlines, focus timer and GPA calculator."),
    "📝 Writer's Desk": ("modules.editor", "Word-like editor with grammar checks and AI."),
    "📄 Resume Studio": ("modules.resume", "Beautiful resumes as PDF or Word."),
    "💻 Code Studio": ("modules.code_studio", "Generate, edit, run and fix code with AI."),
}
LABELS = list(PAGES)


def go(label: str) -> None:
    st.session_state["nav"] = label


def home() -> None:
    ui.hero("Student Stack Pro 🎓", "Twelve tools for study, work and career — powered by CrewAI and Groq.")
    if not llm.get_api_key():
        st.info("🔑 AI features need a `GROQ_API_KEY` in the server secrets (app owner). "
                "Tools that don't need AI — timetable, editor checks — work right away.")
    tools = LABELS[1:]
    for row in range(0, len(tools), 4):
        cols = st.columns(4)
        for col, label in zip(cols, tools[row:row + 4]):
            with col, st.container(border=True):
                st.markdown(f"### {label}")
                st.caption(PAGES[label][1])
                st.button("Open →", key=f"open_{label}", on_click=go, args=(label,), use_container_width=True)
    st.markdown("#### 🔒 Privacy by design")
    st.markdown("- There is no key field: the API key lives only in server secrets and is never shown to anyone.\n"
                "- Uploaded files and text are processed in memory and discarded when you close the tab.\n"
                "- Optional access code and daily/session request caps protect the shared key from misuse.\n"
                "- CrewAI telemetry is switched off. Only the text needed for a request is sent to Groq.")


def main() -> None:
    ui.inject_css()
    if not guard.require_access():
        return
    st.session_state.setdefault("nav", LABELS[0])
    with st.sidebar:
        st.markdown("## 🎓 Student Stack Pro")
        st.radio("Tools", LABELS, key="nav", label_visibility="collapsed")
    llm.sidebar_settings()
    backup.sidebar_backup()
    st.sidebar.caption("🔒 Key is server-side only · telemetry off")
    page = st.session_state["nav"]
    if page == LABELS[0]:
        home()
        return
    try:
        importlib.import_module(PAGES[page][0]).render()
    except Exception as exc:  # noqa: BLE001  - never show raw tracebacks (could echo secrets)
        st.error(f"Something went wrong in this tool: {llm.scrub(exc)[:300]}")
        st.caption("Try again, or switch tool and come back. If it keeps happening, open an issue on the GitHub repo.")


main()
