import streamlit as st

from core import llm, ui, utils

OUTPUTS = {
    "Detailed report": "a structured research report: title, executive summary, background, key findings in sections, analysis, challenges/limitations, conclusion, and further reading topics",
    "Executive summary": "a crisp executive summary with the main takeaways, implications and recommended next steps",
    "Briefing / key points": "a briefing: a one-paragraph overview followed by tight bullet points grouped by theme",
    "Literature-style overview": "a literature-style overview: major themes, schools of thought, key debates, open problems",
    "Pros & cons analysis": "a balanced pros and cons analysis with a final verdict and conditions where each side wins",
    "Study guide": "a study guide: key concepts, definitions, examples, common misconceptions and 8 self-test questions with answers",
    "Custom request": "exactly what the user's custom instructions ask for",
}
LENGTHS = {"Short (~400 words)": 400, "Medium (~900 words)": 900, "Long (~1800 words)": 1800}


def _run(topic, kind, custom, audience, words, web_ctx):
    ctx = f"\n\nLIVE WEB SNIPPETS (use as evidence, do not invent beyond them):\n{web_ctx}" if web_ctx else ""
    steps = [
        dict(role="Senior Research Analyst", goal="Collect accurate, well-organised facts about the topic",
             backstory="A meticulous analyst who separates solid facts from speculation and labels uncertainty.",
             task=f"Research the topic: {topic}.{ctx}\nProduce structured research notes: definitions, key facts, "
                  "timeline, stakeholders, data points you are confident about, competing viewpoints and open "
                  "questions. Mark anything uncertain as (unverified). Never fabricate statistics or sources.",
             expected="Organised research notes in Markdown."),
        dict(role="Critical Reviewer", goal="Strengthen the research by removing errors and filling gaps",
             backstory="An editor with a fact-checking mindset who hates unsupported claims.",
             task="Review the research notes. Remove or flag weak claims, resolve contradictions, note gaps and "
                  f"propose a logical outline for this deliverable: {OUTPUTS[kind]}.",
             expected="Verified notes plus a clear outline."),
        dict(role="Professional Writer", goal="Deliver a polished final document",
             backstory="A writer who turns complex research into clear, engaging prose for the right audience.",
             task=f"Write {OUTPUTS[kind]}. Topic: {topic}. Audience: {audience}. Target length: about {words} words. "
                  f"Extra instructions: {custom or 'none'}. Use Markdown headings and bullets where useful. "
                  "If web snippets were provided, end with a 'Sources' list using only those URLs. "
                  "Never invent citations or URLs.",
             expected="The final Markdown document."),
    ]
    return llm.run_crew(steps, max_tokens=4000)


def render():
    ui.page_header("🔎", "Research Agents", "Three agents — Researcher → Reviewer → Writer — turn any topic into a report, summary or study guide.")
    c1, c2 = st.columns([2, 1])
    topic = ui.sticky(c1.text_input, "Topic or question", "rs_topic", "",
                      placeholder="e.g. Impact of solar energy on Pakistan's power grid")
    kind = ui.sticky(c2.selectbox, "What do you need?", "rs_kind", list(OUTPUTS)[0], options=list(OUTPUTS))
    c3, c4, c5 = st.columns(3)
    audience = ui.sticky(c3.text_input, "Audience", "rs_aud", "university students")
    length = ui.sticky(c4.selectbox, "Length", "rs_len", list(LENGTHS)[1], options=list(LENGTHS))
    use_web = ui.sticky(c5.toggle, "Use live web search", "rs_web", False, disabled=not utils.web_available(),
                        help="Install optional package: pip install -r requirements-optional.txt")
    custom = ui.sticky(st.text_area, "Custom instructions (optional)", "rs_custom", "", height=80,
                       placeholder="e.g. Focus on economic impact, include a comparison table, formal tone")
    if st.button("🚀 Run research crew", type="primary", disabled=not topic.strip()):
        if ui.need_key():
            web_ctx = ""
            if use_web:
                snips = utils.web_snippets(topic)
                web_ctx = "\n".join(f"- {t} ({u}): {b}" for t, u, b in snips)
                if not snips:
                    st.warning("Web search returned nothing — continuing with the model's own knowledge.")
            with st.spinner("Agents are researching, reviewing and writing…"):
                out = llm.safe_run(_run, topic.strip(), kind, custom.strip(), audience.strip() or "general readers",
                                   LENGTHS[length], web_ctx)
            if out:
                st.session_state["research_out"] = dict(topic=topic.strip(), text=out)
    res = st.session_state.get("research_out")
    if res:
        st.divider()
        st.markdown(res["text"])
        d1, d2, d3, _ = st.columns([1, 1, 1, 2])
        pdf = utils.safe_pdf(res["text"], res["topic"])
        d1.download_button("⬇️ PDF", pdf, "research.pdf", "application/pdf", disabled=not pdf, type="primary")
        d2.download_button("⬇️ Markdown", res["text"], "research.md", "text/markdown")
        d3.download_button("⬇️ Word (.docx)", utils.md_to_docx(res["text"], res["topic"]), "research.docx",
                           "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        st.caption("AI can make mistakes — verify important facts, especially without web search.")
