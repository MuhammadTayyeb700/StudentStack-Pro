import streamlit as st

from core import llm, textcheck, ui, utils

TEMPLATES = {
    "Blank": "",
    "Essay": "# Title\n\n## Introduction\nHook, context and thesis statement.\n\n## Body\n### Point 1\nEvidence and explanation.\n\n### Point 2\nEvidence and explanation.\n\n## Conclusion\nRestate the thesis and close strongly.\n",
    "Report": "# Report Title\n\n**Author:** \n**Date:** \n\n## Executive Summary\n\n## Background\n\n## Findings\n- \n\n## Recommendations\n1. \n",
    "Formal letter": "Dear Sir/Madam,\n\nI am writing to …\n\nThank you for your time and consideration.\n\nSincerely,\n[Your name]\n",
    "Meeting notes": "# Meeting Notes\n\n**Date:** \n**Attendees:** \n\n## Agenda\n- \n\n## Decisions\n- \n\n## Action items\n- [ ] \n",
}
SNIPPETS = {
    "H1": "# Heading", "H2": "## Subheading", "• List": "- Item one\n- Item two", "1. List": "1. First\n2. Second",
    "☑ Tasks": "- [ ] Task", "❝ Quote": "> Quote", "▦ Table": "| Column A | Column B |\n|---|---|\n| Value | Value |",
    "― Line": "---",
}
ACTIONS = {
    "Fix grammar & spelling": "Correct all grammar, spelling and punctuation. Do not change wording or style beyond fixes.",
    "Improve clarity & flow": "Improve clarity, flow and word choice while keeping the meaning and the author's voice.",
    "Make concise": "Rewrite to be about 30% shorter without losing key information.",
    "Expand with detail": "Expand with more detail, examples and explanation, roughly 50% longer.",
    "Change tone": "Rewrite in a {tone} tone, keeping the meaning.",
    "Paraphrase": "Paraphrase completely in fresh wording, keeping the meaning.",
    "Summarize": "Summarize into a short paragraph followed by 3-5 bullet points.",
    "Continue writing": "Continue the text naturally with 1-2 more paragraphs in the same voice.",
}
MAX_CHARS = 12000


def _insert(snippet):
    cur = st.session_state.get("doc_text", "").rstrip("\n")
    st.session_state["doc_text"] = (cur + "\n\n" if cur else "") + snippet + "\n"


def _load_tpl():
    st.session_state["doc_text"] = TEMPLATES[st.session_state["tpl_choice"]]
    st.session_state.pop("ai_out", None)


def _replace():
    st.session_state["doc_text"] = st.session_state.pop("ai_out")["text"]


def _append():
    st.session_state["doc_text"] = st.session_state.get("doc_text", "").rstrip() + "\n\n" + st.session_state.pop("ai_out")["text"]


def _discard():
    st.session_state.pop("ai_out", None)


def _ai(action, tone, text):
    instr = ACTIONS[action].format(tone=tone)
    out = llm.single("Expert Editor", "Improve writing exactly as instructed",
                     "A veteran editor: precise, respectful of the author's intent, never adds commentary.",
                     f"{instr}\nPreserve Markdown formatting. Return ONLY the resulting text — no preface, no quotes, no explanation.\n\nTEXT:\n{text}",
                     "Only the resulting text.", temperature=0.3, max_tokens=3500)
    return llm.strip_fences(out)


def render():
    ui.page_header("📝", "Writer's Desk", "A distraction-free Markdown editor with Grammarly-style checks and AI rewriting — free.")
    st.session_state.setdefault("doc_text", st.session_state.get("_saved_doc_text", ""))
    st.session_state.setdefault("doc_title", st.session_state.get("_saved_doc_title", "Untitled document"))
    ui.keep("tpl_choice")

    top = st.columns([3, 2, 1.3, 1.2])
    top[0].text_input("Title", key="doc_title", label_visibility="collapsed", placeholder="Document title")
    top[1].selectbox("Template", list(TEMPLATES), key="tpl_choice", label_visibility="collapsed")
    top[2].button("Load template", on_click=_load_tpl, use_container_width=True)
    focus = top[3].toggle("Focus mode")

    bar = st.columns(len(SNIPPETS))
    for col, (label, snip) in zip(bar, SNIPPETS.items()):
        col.button(label, key=f"sn_{label}", on_click=_insert, args=(snip,), use_container_width=True)

    main, side = (st.container(), None) if focus else st.columns([2.6, 1.2])
    text = None
    with main:
        t_write, t_prev, t_proof = st.tabs(["✍️ Write", "👁 Preview", "🔍 Proofread"])
        with t_write:
            text = st.text_area("Document", key="doc_text", height=520, label_visibility="collapsed",
                                placeholder="Start writing… Markdown is supported (# headings, **bold**, - lists).")
        with t_prev:
            if text.strip():
                st.markdown(f"# {st.session_state['doc_title']}" if st.session_state["doc_title"].strip() else "")
                st.markdown(text)
            else:
                st.caption("Nothing to preview yet.")
        with t_proof:
            issues = textcheck.find_issues(text)
            if not text.strip():
                st.caption("Write something to see suggestions.")
            else:
                st.markdown(f'<div class="paper">{textcheck.highlight_html(text, issues)}</div>', unsafe_allow_html=True)
                st.caption("Hover over a highlight for the suggestion.  🟥 repeated · 🟨 passive · 🟪 filler · 🟦 long sentence · 🩷 cliché · 🟧 capitalisation")
                for it in issues[:40]:
                    st.write(f"• {it['msg']}")
                if len(issues) > 40:
                    st.caption(f"…and {len(issues) - 40} more")

    st.session_state["_saved_doc_text"] = text
    st.session_state["_saved_doc_title"] = st.session_state["doc_title"]

    if side is not None:
        with side:
            stats = textcheck.analyze(text)
            c1, c2 = st.columns(2)
            c1.metric("Words", stats["words"])
            c2.metric("Read time", f"{stats['minutes']} min")
            c3, c4 = st.columns(2)
            c3.metric("Sentences", stats["sentences"])
            c4.metric("Readability", f"{stats['flesch']}/100")
            st.caption(f"Reading level: {stats['label']} · {len(textcheck.find_issues(text))} suggestions · {stats['chars']:,} characters")
            st.divider()
            st.markdown("**✨ AI assistant**")
            action = st.selectbox("Action", list(ACTIONS), label_visibility="collapsed")
            tone = "professional"
            if action == "Change tone":
                tone = st.selectbox("Tone", ["professional", "friendly", "formal", "persuasive", "academic", "casual", "confident"])
            if st.button("Run on document", type="primary", use_container_width=True, disabled=not text.strip()):
                if ui.need_key():
                    body = text[:MAX_CHARS]
                    if len(text) > MAX_CHARS:
                        st.warning(f"Only the first {MAX_CHARS:,} characters were sent.")
                    with st.spinner("Editing…"):
                        out = llm.safe_run(_ai, action, tone, body)
                    if out:
                        st.session_state["ai_out"] = dict(text=out, base=body, action=action)

    ai = st.session_state.get("ai_out")
    if ai:
        st.divider()
        st.markdown(f"**AI result — {ai['action']}**")
        if ai["action"] in ("Summarize", "Continue writing"):
            st.markdown(ai["text"])
        else:
            st.markdown(f'<div class="paper">{textcheck.diff_html(ai["base"], ai["text"])}</div>', unsafe_allow_html=True)
            st.caption("🟩 added · 🟥 removed")
        a, b, c, _ = st.columns([1.2, 1.2, 1, 2])
        a.button("✅ Replace document", on_click=_replace, type="primary")
        b.button("➕ Append below", on_click=_append)
        c.button("✖ Discard", on_click=_discard)

    st.divider()
    d1, d4, d2, d3, _ = st.columns([1, 1, 1, 1, 1])
    name = (st.session_state["doc_title"].strip() or "document").replace(" ", "_")[:40]
    d1.download_button("⬇️ Word (.docx)", utils.md_to_docx(text, st.session_state["doc_title"].strip()), f"{name}.docx",
                       "application/vnd.openxmlformats-officedocument.wordprocessingml.document", disabled=not text.strip())
    pdf = utils.safe_pdf(text, st.session_state["doc_title"].strip()) if text.strip() else b""
    d4.download_button("⬇️ PDF", pdf, f"{name}.pdf", "application/pdf", disabled=not pdf)
    d2.download_button("⬇️ Markdown", text, f"{name}.md", "text/markdown", disabled=not text.strip())
    d3.download_button("⬇️ Plain text", text, f"{name}.txt", disabled=not text.strip())
    st.caption("Your text lives only in this browser session — nothing is stored on a server. Download to keep it.")
