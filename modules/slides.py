import streamlit as st

from core import llm, ui, utils

OUTPUTS = ["Slide-by-slide notes", "Summary", "Key terms glossary", "Practice questions", "Cheat-sheet"]
DETAIL = {"Concise": "concise", "Standard": "thorough but efficient", "Comprehensive": "highly detailed and comprehensive"}


def _slide_text(s, limit=1500):
    t = f"### Slide {s['n']}: {s['title']}\n{s['text'][:limit]}"
    if s["notes"]:
        t += f"\nSpeaker notes: {s['notes'][:600]}"
    return t


def _notes(slides, detail):
    texts = [_slide_text(s) for s in slides]
    groups = utils.group_by_chars(texts, 6000)
    out = []
    bar = st.progress(0.0, text="Writing notes…")
    for gi, g in enumerate(groups, 1):
        bar.progress(gi / len(groups), text=f"Writing notes… {gi}/{len(groups)}")
        body = "\n\n".join(texts[i] for i in g)
        out.append(llm.single(
            "Lecture Note Specialist", "Expand slide bullets into complete, understandable notes",
            "A teaching assistant who explains what each slide means, adds context from the slide text only, "
            "and keeps slide numbers.",
            f"For every slide below write {DETAIL[detail]} notes under its own heading '## Slide N – title'. "
            "Explain bullets in full sentences, define terms, and keep examples. Do not invent facts that "
            f"aren't implied by the slides.\n\n{body}", "Markdown notes per slide.", max_tokens=3000))
    bar.empty()
    return "\n\n".join(out)


def _overview(kind, slides, detail):
    ctx = "\n\n".join(_slide_text(s, 500) for s in slides)[:11000]
    prompts = {
        "Summary": f"Write a {DETAIL[detail]} summary of the whole presentation: purpose, main sections, key takeaways.",
        "Key terms glossary": "Extract every important term and give a clear 1-2 sentence definition (alphabetical, Markdown list).",
        "Practice questions": "Write 10 exam-style questions (mix of MCQ, short answer, and one long answer) followed by an answer key.",
        "Cheat-sheet": "Create a one-page revision cheat-sheet of the most important facts, formulas and concepts.",
    }
    return llm.single("Study Coach", "Create high-quality revision material",
                      "A coach who knows exactly what students need before exams.",
                      f"{prompts[kind]} Base it only on this presentation:\n\n{ctx}", "Markdown.", max_tokens=2500)


def render():
    ui.page_header("🖼️", "Slide Reader", "Upload a PowerPoint or PDF deck → comprehensive notes, summary, glossary and practice questions.")
    f = st.file_uploader("Upload slides (.pptx or .pdf)", type=["pptx", "pdf"])
    if f and st.button("📥 Read slides", type="primary"):
        try:
            if f.name.lower().endswith(".pptx"):
                slides = utils.read_pptx(f.getvalue())
            else:
                slides = [dict(n=p, title=f"Slide {p}", text=t, notes="") for p, t in utils.read_pdf(f.getvalue())]
        except Exception as exc:  # noqa: BLE001
            st.error(f"Couldn't read this file: {exc}")
            slides = []
        if slides and any(s["text"] for s in slides):
            st.session_state["slides"] = dict(name=f.name, slides=slides)
            st.session_state.pop("slide_out", None)
        elif slides:
            st.warning("No text found in the slides (images only?). OCR isn't supported.")
    data = st.session_state.get("slides")
    if not data:
        st.info("Legacy .ppt files aren't supported — save as .pptx or export to PDF first.")
        return
    slides = data["slides"]
    st.success(f"{data['name']} — {len(slides)} slides, {sum(len(s['text']) for s in slides):,} characters")
    with st.expander("Preview extracted text"):
        for s in slides[:60]:
            st.markdown(f"**{s['n']}. {s['title']}**")
            st.text(s["text"][:500] or "(no text)")
    c1, c2 = st.columns([2, 1])
    wanted = ui.sticky(c1.multiselect, "What should I create?", "sl_want", ["Slide-by-slide notes", "Summary"], options=OUTPUTS)
    detail = ui.sticky(c2.selectbox, "Detail level", "sl_detail", "Standard", options=list(DETAIL))
    if st.button("✨ Generate", type="primary", disabled=not wanted) and ui.need_key():
        res = {}
        for kind in wanted:
            with st.spinner(f"{kind}…"):
                out = llm.safe_run(_notes, slides, detail) if kind == OUTPUTS[0] else llm.safe_run(_overview, kind, slides, detail)
            if out:
                res[kind] = out
        st.session_state["slide_out"] = res
    res = st.session_state.get("slide_out")
    if res:
        tabs = st.tabs(list(res))
        for tab, (kind, text) in zip(tabs, res.items()):
            with tab:
                st.markdown(text)
        full = "\n\n---\n\n".join(f"# {k}\n\n{v}" for k, v in res.items())
        a, b, c, _ = st.columns([1, 1, 1, 2])
        pdf = utils.safe_pdf(full, data["name"])
        a.download_button("⬇️ PDF", pdf, "slide_notes.pdf", "application/pdf", disabled=not pdf, type="primary")
        b.download_button("⬇️ Markdown", full, "slide_notes.md", "text/markdown")
        c.download_button("⬇️ Word", utils.md_to_docx(full, data["name"]), "slide_notes.docx",
                          "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
