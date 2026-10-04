import io

import streamlit as st

from core import llm, textcheck, ui, utils

LEVELS = ["High school", "Undergraduate", "Postgraduate"]
KINDS = ["Argumentative", "Analytical", "Narrative / reflective", "Research paper", "Report", "Other"]
STRICT = {"Lenient": "encouraging; round marks up when in doubt", "Balanced": "fair and realistic",
          "Strict": "demanding, like a tough examiner; do not inflate marks"}
CRITERIA = ["Thesis & argument", "Structure & organisation", "Evidence & analysis", "Clarity & style",
            "Grammar & mechanics"]
MAX_CHARS = 12000


def _list(v, limit=8):
    return [str(x).strip()[:400] for x in (v if isinstance(v, list) else []) if str(x).strip()][:limit]


def _num(v, lo, hi, default=0):
    try:
        return max(lo, min(hi, round(float(v))))
    except (TypeError, ValueError):
        return default


def normalize_feedback(raw) -> dict:
    """Clamp and clean the AI's JSON so the UI never breaks on odd values. Raises ValueError if unusable."""
    if not isinstance(raw, dict) or not isinstance(raw.get("criteria"), list):
        raise ValueError("The feedback wasn't in the expected format. Please click the button again.")
    crit = [dict(name=str(c.get("name", "")).strip()[:60] or "Criterion", score=_num(c.get("score"), 0, 10),
                 comment=str(c.get("comment", "")).strip()[:600], fix=str(c.get("fix", "")).strip()[:400])
            for c in raw["criteria"] if isinstance(c, dict)][:10]
    if not crit:
        raise ValueError("The feedback had no criteria. Please try again.")
    fixes = [dict(issue=str(f.get("issue", "")).strip()[:300], where=str(f.get("where", "")).strip()[:200],
                  suggestion=str(f.get("suggestion", "")).strip()[:400])
             for f in raw.get("priority_fixes", []) if isinstance(f, dict)][:6]
    edits = [dict(original=str(e.get("original", "")).strip()[:300], improved=str(e.get("improved", "")).strip()[:300],
                  why=str(e.get("why", "")).strip()[:300])
             for e in raw.get("line_edits", []) if isinstance(e, dict) and e.get("original")][:6]
    overall = _num(raw.get("overall"), 0, 100, default=round(10 * sum(c["score"] for c in crit) / len(crit)))
    return dict(overall=overall, band=str(raw.get("grade_band", "")).strip()[:40],
                summary=str(raw.get("summary", "")).strip()[:900], criteria=crit, strengths=_list(raw.get("strengths")),
                fixes=fixes, edits=edits, next_steps=_list(raw.get("next_steps"), 6))


def to_markdown(fb: dict) -> str:
    md = [f"# Essay feedback — {fb['overall']}/100" + (f" ({fb['band']})" if fb["band"] else ""), "", fb["summary"], "",
          "## Criteria"]
    for c in fb["criteria"]:
        md += [f"### {c['name']} — {c['score']}/10", c["comment"], f"**To improve:** {c['fix']}" if c["fix"] else "", ""]
    if fb["strengths"]:
        md += ["## Strengths"] + [f"- {s}" for s in fb["strengths"]] + [""]
    if fb["fixes"]:
        md += ["## Priority fixes"] + [f"- **{f['issue']}**" + (f" (“{f['where']}”)" if f["where"] else "")
                                       + f" — {f['suggestion']}" for f in fb["fixes"]] + [""]
    if fb["edits"]:
        md += ["## Sentence-level suggestions"]
        for e in fb["edits"]:
            md += [f"- Original: {e['original']}", f"- Better: {e['improved']}", f"- Why: {e['why']}", ""]
    if fb["next_steps"]:
        md += ["## Next steps"] + [f"- {s}" for s in fb["next_steps"]]
    return "\n".join(md)


def _analyse(essay, prompt, level, kind, strict, criteria, rubric):
    rub = (f"Use this rubric exactly (criteria names from it):\n{rubric}" if rubric.strip()
           else "Assess these criteria: " + "; ".join(criteria))
    steps = [dict(
        role="Writing Examiner", goal="Give accurate, specific, constructive essay feedback",
        backstory="A university writing-centre examiner who marks fairly, quotes the student's own words as evidence, "
                  "and never rewrites the whole essay for them.",
        task=f"Assess this {kind.lower()} essay written at {level.lower()} level. Marking style: {STRICT[strict]}.\n"
             f"Assignment prompt: {prompt.strip() or 'not provided'}\n{rub}\n\n"
             "Return ONLY valid JSON (no markdown fences) shaped exactly like: "
             '{"overall":0-100,"grade_band":"e.g. B+","summary":"3 sentences","criteria":[{"name":"","score":0-10,'
             '"comment":"specific, 1-2 sentences","fix":"one concrete action"}],"strengths":["..."],'
             '"priority_fixes":[{"issue":"","where":"a short exact quote from the essay, max 12 words","suggestion":""}],'
             '"line_edits":[{"original":"exact short excerpt","improved":"better wording","why":""}],'
             '"next_steps":["..."]}. Give 3-6 strengths-or-fixes items, at most 4 line_edits, and only quote text that '
             f"really appears in the essay. Do not rewrite the essay.\n\nESSAY:\n{essay[:MAX_CHARS]}",
        expected="Valid JSON feedback.")]
    return llm.run_crew(steps, temperature=0.2, max_tokens=3500)


def _read_upload(f) -> str:
    name = f.name.lower()
    if name.endswith(".pdf"):
        return "\n\n".join(t for _, t in utils.read_pdf(f.getvalue()))
    if name.endswith(".docx"):
        from docx import Document
        return "\n".join(p.text for p in Document(io.BytesIO(f.getvalue())).paragraphs)
    return f.getvalue().decode("utf-8", errors="ignore")


def render():
    ui.page_header("🧾", "Essay Feedback", "Paste or upload an essay → scored feedback, priority fixes and sentence-level suggestions.")
    up = st.file_uploader("Upload an essay (.docx, .pdf or .txt) — or paste it below", type=["docx", "pdf", "txt"])
    if up and st.button("📥 Load file into the editor"):
        try:
            st.session_state["es_text"] = _read_upload(up).strip()
        except Exception as exc:  # noqa: BLE001
            st.error(f"Couldn't read this file: {llm.scrub(exc)[:200]}")
    c1, c2 = st.columns([3, 2])
    with c1:
        essay = ui.sticky(st.text_area, "Your essay", "es_text", "", height=330, placeholder="Paste your essay here…")
        st.session_state["_essay_text_saved"] = essay
    with c2:
        prompt = ui.sticky(st.text_area, "Assignment prompt / question (optional)", "es_prompt", "", height=100)
        st.session_state["_essay_prompt_saved"] = prompt
        level = ui.sticky(st.selectbox, "Level", "es_level", "Undergraduate", options=LEVELS)
        kind = ui.sticky(st.selectbox, "Essay type", "es_kind", "Argumentative", options=KINDS)
        strict = ui.sticky(st.select_slider, "Marking style", "es_strict", "Balanced", options=list(STRICT))
    with st.expander("Marking criteria / rubric"):
        criteria = ui.sticky(st.multiselect, "Criteria", "es_crit", CRITERIA, options=CRITERIA)
        rubric = ui.sticky(st.text_area, "Or paste your teacher's rubric (overrides the criteria above)", "es_rubric", "", height=110)
    if essay.strip():
        s = textcheck.analyze(essay)
        a, b, c = st.columns(3)
        a.metric("Words", f"{s['words']:,}")
        b.metric("Reading time", f"{s['minutes']} min")
        c.metric("Readability", f"{s['flesch']}/100", s["label"], delta_color="off")
        if len(essay) > MAX_CHARS:
            st.warning(f"Only the first {MAX_CHARS:,} characters are analysed.")
    if st.button("🧾 Get feedback", type="primary", disabled=len(essay.strip()) < 150 or not (criteria or rubric.strip())):
        if ui.need_key():
            with st.spinner("The examiner is reading your essay…"):
                raw = llm.safe_run(_analyse, essay.strip(), prompt, level, kind, strict, criteria, rubric)
            if raw:
                try:
                    st.session_state["essay_fb"] = normalize_feedback(llm.extract_json(raw))
                except (ValueError, llm.LLMError) as exc:
                    st.error(str(exc))
    if len(essay.strip()) < 150:
        st.caption("Add at least ~150 characters to enable feedback.")
    try:
        fb = normalize_feedback(st.session_state["essay_fb"]) if st.session_state.get("essay_fb") else None
    except ValueError:
        fb = None
    if not fb:
        return
    st.divider()
    m1, m2 = st.columns([1, 3])
    m1.metric("Overall", f"{fb['overall']}/100", fb["band"] or None, delta_color="off")
    m2.markdown(fb["summary"])
    st.markdown("#### Criteria")
    for c in fb["criteria"]:
        st.markdown(f"**{c['name']}** — {c['score']}/10")
        st.progress(c["score"] / 10)
        st.caption(c["comment"] + (f"  \n➡️ {c['fix']}" if c["fix"] else ""))
    t1, t2, t3 = st.tabs(["💪 Strengths", "🛠️ Priority fixes", "✏️ Sentence suggestions"])
    with t1:
        for s_ in fb["strengths"] or ["—"]:
            st.markdown(f"- {s_}")
    with t2:
        for f in fb["fixes"] or []:
            st.markdown(f"- **{f['issue']}**" + (f"  \n  _“{f['where']}”_" if f["where"] else "") + f"  \n  {f['suggestion']}")
    with t3:
        for e in fb["edits"] or []:
            st.markdown(f"> {e['original']}")
            st.markdown(f"✅ {e['improved']}  \n_{e['why']}_")
    if fb["next_steps"]:
        st.markdown("#### Next steps")
        for s_ in fb["next_steps"]:
            st.markdown(f"- {s_}")
    md = to_markdown(fb)
    d1, d2, d3, _ = st.columns([1, 1, 1, 2])
    pdf = utils.safe_pdf(md)
    d1.download_button("⬇️ PDF", pdf, "essay_feedback.pdf", "application/pdf", disabled=not pdf, type="primary")
    d2.download_button("⬇️ Markdown", md, "essay_feedback.md", "text/markdown")
    d3.download_button("⬇️ Word", utils.md_to_docx(md), "essay_feedback.docx",
                       "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    st.caption("AI feedback is a study aid, not an official grade — and it never rewrites your essay for you.")
