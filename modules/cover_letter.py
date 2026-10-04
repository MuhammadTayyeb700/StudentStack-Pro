import re
from datetime import date

import streamlit as st

from core import llm, ui, utils

TONES = ["Professional", "Enthusiastic", "Confident", "Warm & personable", "Formal"]
LENGTHS = {"Short (~200 words)": 200, "Standard (~300 words)": 300, "Detailed (~400 words)": 400}
LANGS = ["English", "Urdu", "Roman Urdu", "Arabic", "French", "Spanish", "German"]


def _t(v) -> str:
    return str(v or "").strip()


def resume_context(r) -> str:
    """Plain-text candidate profile from Resume Studio data ('' when the resume is empty)."""
    if not isinstance(r, dict):
        return ""
    out = []
    head = " · ".join(x for x in (_t(r.get("name")), _t(r.get("title"))) if x)
    contact = " | ".join(x for x in (_t(r.get("email")), _t(r.get("phone")), _t(r.get("location"))) if x)
    for label, val in (("Candidate", head), ("Contact", contact), ("Summary", _t(r.get("summary"))),
                       ("Skills", _t(r.get("skills"))), ("Certifications", _t(r.get("certifications")))):
        if val:
            out.append(f"{label}: {val}")
    for sec, fields in (("Experience", ("role", "company", "start", "end", "bullets")),
                        ("Education", ("degree", "school", "year", "details")),
                        ("Projects", ("name", "link", "bullets"))):
        rows = []
        for e in r.get(sec.lower(), []) if isinstance(r.get(sec.lower()), list) else []:
            if isinstance(e, dict) and any(_t(e.get(f)) for f in fields):
                rows.append("- " + "; ".join(_t(e.get(f)).replace("\n", " / ") for f in fields if _t(e.get(f))))
        if rows:
            out.append(f"{sec}:\n" + "\n".join(rows))
    return "\n".join(out)


def _clean_letter(text: str) -> str:
    t = llm.strip_fences(text)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def _write(profile, extra, ad, company, role, manager, tone, words, lang, header, emphasis, today):
    greet = f"Dear {manager}," if manager else "Dear Hiring Manager,"
    steps = [
        dict(role="Career Coach & Cover Letter Writer", goal="Write a specific, honest cover letter that earns an interview",
             backstory="A recruiter-turned-coach who matches a candidate's real evidence to what the employer asks for, "
                       "and never invents facts.",
             task=f"Write a cover letter for the {role or 'advertised'} role at {company or 'the company'}.\n"
                  f"Tone: {tone}. Length: about {words} words. Language: {lang}. Greeting: {greet}\n"
                  f"{'Start with a header: candidate name and contact details, then ' + today + ', then the company.' if header else 'No address header; start at the greeting.'}\n"
                  f"Emphasise: {emphasis or 'the strongest fit with the job ad'}\n\n"
                  f"CANDIDATE PROFILE (the ONLY source of facts about the candidate):\n{profile or 'not provided'}\n"
                  f"ADDITIONAL BACKGROUND:\n{extra or 'none'}\n\nJOB AD:\n{ad[:6000]}\n\n"
                  "Rules: pick 2-3 requirements from the job ad and prove each with real evidence from the profile; "
                  "never invent employers, numbers, degrees or skills; no clichés like 'I am writing to apply'; "
                  "no placeholders in brackets; end with a confident call to action and a sign-off with the candidate's name.",
             expected="A full cover letter."),
        dict(role="Editor", goal="Tighten the letter and verify it only uses supplied facts",
             backstory="An editor who cuts fluff, fixes tone and removes any claim not backed by the candidate profile.",
             task=f"Edit the draft: keep about {words} words, remove unsupported claims, fix grammar. "
                  "Return ONLY the final letter as plain text — no commentary, no markdown, no fences.",
             expected="The final cover letter text."),
    ]
    return llm.run_crew(steps, temperature=0.5, max_tokens=1800)


def render():
    ui.page_header("💌", "Cover Letter Writer", "Paste a job ad → a tailored letter built from your Resume Studio data.")
    profile = resume_context(st.session_state.get("resume"))
    use_resume = ui.sticky(st.toggle, "Use my Resume Studio data", "cl_use_resume", True)
    if use_resume and profile:
        st.success("✅ Using your resume: " + (profile.splitlines()[0].replace("Candidate: ", "") or "details found"))
    elif use_resume:
        st.warning("Your resume is empty. Fill in **📄 Resume Studio** first, or describe your background below.")
    c1, c2 = st.columns(2)
    with c1:
        ad = ui.sticky(st.text_area, "Job ad (paste the full description)", "cl_ad", "", height=240)
        extra = ui.sticky(st.text_area, "Extra background or achievements (optional)", "cl_extra", "", height=90)
    with c2:
        role = ui.sticky(st.text_input, "Job title", "cl_role", "")
        company = ui.sticky(st.text_input, "Company", "cl_company", "")
        manager = ui.sticky(st.text_input, "Hiring manager's name (optional)", "cl_mgr", "")
        tone = ui.sticky(st.selectbox, "Tone", "cl_tone", "Professional", options=TONES)
        length = ui.sticky(st.selectbox, "Length", "cl_len", "Standard (~300 words)", options=list(LENGTHS))
        lang = ui.sticky(st.selectbox, "Language", "cl_lang", "English", options=LANGS)
        emphasis = ui.sticky(st.text_input, "Emphasise (optional)", "cl_emph", "", placeholder="e.g. my internship and Python projects")
        header = ui.sticky(st.checkbox, "Include contact header and date", "cl_header", True)
    have_facts = bool((use_resume and profile) or extra.strip())
    if st.button("✨ Write cover letter", type="primary", disabled=len(ad.strip()) < 40 or not have_facts):
        if ui.need_key():
            with st.spinner("Writing and editing…"):
                raw = llm.safe_run(_write, profile if use_resume else "", extra.strip(), ad.strip(), company.strip(),
                                   role.strip(), manager.strip(), tone, LENGTHS[length], lang, header,
                                   emphasis.strip(), date.today().strftime("%d %B %Y"))
            if raw:
                letter = _clean_letter(raw)
                st.session_state["cover_letter"] = letter
                st.session_state["cl_edit"] = letter
    if not have_facts:
        st.caption("Add resume data or some background so the letter only contains real facts about you.")
    if "cl_edit" not in st.session_state and st.session_state.get("cover_letter"):
        st.session_state["cl_edit"] = st.session_state["cover_letter"]
    if "cl_edit" not in st.session_state:
        return
    st.divider()
    letter = st.text_area("Your cover letter (edit freely)", key="cl_edit", height=420)
    st.session_state["cover_letter"] = letter
    st.caption(f"{len(letter.split())} words · AI can make mistakes — check every fact before sending.")
    a, b, c, _ = st.columns([1, 1, 1, 2])
    pdf = utils.safe_pdf(letter)
    a.download_button("⬇️ PDF", pdf, "cover_letter.pdf", "application/pdf", disabled=not pdf, type="primary")
    b.download_button("⬇️ Word", utils.md_to_docx(letter), "cover_letter.docx",
                      "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    c.download_button("⬇️ Text", letter, "cover_letter.txt")
