import uuid

import streamlit as st
import streamlit.components.v1 as components

from core import llm, ui
from core import resume_render as rr

PERSONAL = [("name", "Full name"), ("title", "Professional title"), ("email", "Email"), ("phone", "Phone"),
            ("location", "Location")]
SECTIONS = {
    "experience": [("role", "Role / position", "text"), ("company", "Company", "text"), ("location", "Location", "text"),
                   ("start", "Start (e.g. Jun 2024)", "text"), ("end", "End (or Present)", "text"),
                   ("bullets", "Achievements — one per line", "area")],
    "education": [("degree", "Degree", "text"), ("school", "University / school", "text"), ("location", "Location", "text"),
                  ("year", "Years (e.g. 2022 – 2026)", "text"), ("details", "Highlights — one per line", "area")],
    "projects": [("name", "Project name", "text"), ("link", "Link", "text"), ("bullets", "What you built — one per line", "area")],
}
TITLE_KEY = {"experience": "role", "education": "degree", "projects": "name"}
LABEL = {"experience": "experience", "education": "education", "projects": "project"}

SAMPLE = dict(
    name="Alex Morgan", title="Software Engineer · AI Developer", email="you@example.com",
    phone="+00 000 0000000", location="City, Country", links="github.com/yourname\nlinkedin.com/in/yourname",
    summary="Engineer with hands-on experience building AI applications using Python, "
            "Streamlit and LLM agents. Passionate about turning ideas into reliable, user-friendly software.",
    skills="Languages: Python, C++, SQL\nAI/ML: CrewAI, Groq, RAG, scikit-learn\nTools: Git, Streamlit, Linux",
    certifications="", experience=[dict(role="AI Developer Intern", company="Example Labs", location="Remote",
                                        start="Jun 2026", end="Aug 2026",
                                        bullets="Built a multi-agent research assistant that cut report drafting time by 60%\n"
                                                "Designed a PDF question-answering pipeline with page-level citations")],
    education=[dict(degree="BSc Computer Engineering", school="Example University", location="City", year="2022 – 2026",
                    details="")],
    projects=[dict(name="Student Stack Pro", link="github.com/yourname/student-stack-pro",
                   bullets="Streamlit app with 8 AI tools powered by CrewAI and Groq")])


def _w(fn, label, key, default="", **kw):
    """Create a widget without clashing default-value vs session-state (avoids Streamlit warnings)."""
    if key in st.session_state:
        return fn(label, key=key, **kw)
    return fn(label, value=default, key=key, **kw)


def _new_id():
    return uuid.uuid4().hex[:8]


def _blank():
    return dict(name="", title="", email="", phone="", location="", links="", summary="", skills="", certifications="",
                experience=[], education=[], projects=[])


def _with_ids(r):
    r = dict(r)
    for sec in SECTIONS:
        r[sec] = [dict(e, id=e.get("id") or _new_id()) for e in r.get(sec, [])]
    return r


def _txt(v):
    return "\n".join(str(x) for x in v) if isinstance(v, list) else str(v or "")


def _coerce(data, old=None):
    """Turn AI/JSON output into the form model (strings everywhere, ids kept where possible)."""
    r = _blank()
    for k in ("name", "title", "email", "phone", "location", "links", "summary", "skills", "certifications"):
        r[k] = _txt(data.get(k, (old or {}).get(k, "")))
    for sec, fields in SECTIONS.items():
        items = data.get(sec, []) or []
        prev = (old or {}).get(sec, [])
        for i, it in enumerate(items):
            if not isinstance(it, dict):
                continue
            ent = {k: _txt(it.get(k, "")) for k, _, _ in fields}
            ent["id"] = prev[i]["id"] if len(prev) == len(items) else _new_id()
            r[sec].append(ent)
    return r


def _push_to_widgets(r):
    for k, _ in PERSONAL:
        st.session_state[f"r_{k}"] = r[k]
    for k in ("links", "summary", "skills", "certifications"):
        st.session_state[f"r_{k}"] = r[k]
    for sec, fields in SECTIONS.items():
        for e in r[sec]:
            for k, _, _ in fields:
                st.session_state[f"{sec}_{e['id']}_{k}"] = e.get(k, "")


def _add(sec):
    st.session_state["resume"][sec].append(dict(id=_new_id(), **{k: "" for k, _, _ in SECTIONS[sec]}))


def _remove(sec, eid):
    st.session_state["resume"][sec] = [e for e in st.session_state["resume"][sec] if e["id"] != eid]


def _entries(sec):
    for e in st.session_state["resume"][sec]:
        head = e.get(TITLE_KEY[sec]) or f"New {LABEL[sec]}"
        with st.expander(head, expanded=not e.get(TITLE_KEY[sec])):
            for k, lab, kind in SECTIONS[sec]:
                wk = f"{sec}_{e['id']}_{k}"
                if kind == "area":
                    e[k] = _w(st.text_area, lab, wk, e.get(k, ""), height=120)
                else:
                    e[k] = _w(st.text_input, lab, wk, e.get(k, ""))
            st.button("🗑 Remove", key=f"rm_{sec}_{e['id']}", on_click=_remove, args=(sec, e["id"]))
    st.button(f"➕ Add {LABEL[sec]}", key=f"add_{sec}", on_click=_add, args=(sec,))


def _clean_for_ai(r):
    return {k: v for k, v in r.items() if k not in SECTIONS} | {
        s: [{k: v for k, v in e.items() if k != "id"} for e in r[s]] for s in SECTIONS}


def _polish(r, job):
    import json
    raw = llm.single(
        "Executive Resume Writer", "Rewrite resumes so they win interviews",
        "A recruiter-turned-writer: strong verbs, quantified impact, ATS-friendly keywords, zero fluff, never invents facts.",
        "Improve this resume. Rewrite the summary (2-3 sentences) and every achievement bullet with strong action verbs "
        "and, only where the data already implies it, measurable impact. Keep ALL facts true — never invent employers, "
        "degrees, dates or numbers. Keep the same number of entries in the same order and the same keys. "
        f"Target job (optional): {job or 'general'}.\nReturn ONLY the complete resume as JSON with the same structure "
        "(bullets as one string with newlines).\n\nRESUME JSON:\n" + json.dumps(_clean_for_ai(r), ensure_ascii=False),
        "JSON.", temperature=0.3, max_tokens=3500)
    return _coerce(llm.extract_json(raw), r)


def _import(text):
    raw = llm.single(
        "Resume Parser", "Convert plain-text resumes into structured data",
        "A precise parser that never invents information.",
        'Extract this resume into JSON with keys: name, title, email, phone, location, links (newline string), summary, '
        'skills (newline string, format "Category: a, b"), certifications (newline string), experience '
        '[{role,company,location,start,end,bullets}], education [{degree,school,location,year,details}], '
        'projects [{name,link,bullets}]. Use empty strings when unknown. Return ONLY JSON.\n\nRESUME TEXT:\n' + text[:9000],
        "JSON.", temperature=0.1, max_tokens=3500)
    return _coerce(llm.extract_json(raw))


def render():
    ui.page_header("📄", "Resume Studio", "Fill in the form, let AI sharpen it, preview live and export a beautiful PDF or Word file.")
    if "resume" not in st.session_state:
        st.session_state["resume"] = _with_ids(_blank())
    pending = st.session_state.pop("resume_pending", None)
    if pending is not None:
        st.session_state["resume"] = pending
        _push_to_widgets(pending)
    r = st.session_state["resume"]

    c1, c2, c3 = st.columns([1, 1, 2])
    if c1.button("Load sample data"):
        st.session_state["resume_pending"] = _with_ids(SAMPLE)
        st.rerun()
    if c2.button("Clear all"):
        st.session_state["resume_pending"] = _with_ids(_blank())
        st.rerun()
    with c3.expander("📥 Import from pasted resume text (AI)"):
        pasted = st.text_area("Paste your old resume", height=140, label_visibility="collapsed")
        if st.button("Fill the form from this text", disabled=not pasted.strip()) and ui.need_key():
            with st.spinner("Reading your resume…"):
                new = llm.safe_run(_import, pasted)
            if new:
                st.session_state["resume_pending"] = _with_ids(new)
                st.rerun()

    form, preview = st.columns([1.05, 1])
    with form:
        tabs = st.tabs(["👤 You", "💼 Experience", "🎓 Education", "🛠 Skills & more", "🎨 Design & AI"])
        with tabs[0]:
            for k, lab in PERSONAL:
                r[k] = _w(st.text_input, lab, f"r_{k}", r[k])
            r["links"] = _w(st.text_area, "Links — one per line", "r_links", r["links"], height=80,
                                      placeholder="github.com/you\nlinkedin.com/in/you")
            r["summary"] = _w(st.text_area, "Professional summary", "r_summary", r["summary"], height=120)
        with tabs[1]:
            _entries("experience")
        with tabs[2]:
            _entries("education")
        with tabs[3]:
            r["skills"] = _w(st.text_area, "Skills — one group per line", "r_skills", r["skills"], height=120,
                                       placeholder="Languages: Python, C++\nTools: Git, Docker")
            st.markdown("**Projects**")
            _entries("projects")
            r["certifications"] = _w(st.text_area, "Certifications — one per line", "r_certifications",
                                     r["certifications"], height=80)
        with tabs[4]:
            template = st.radio("Template", ["modern", "classic"], horizontal=True,
                                format_func=lambda x: "Modern (colour header)" if x == "modern" else "Classic (serif)")
            accent = st.color_picker("Accent colour", "#4f46e5")
            compact = st.toggle("Compact spacing (preview)")
            st.divider()
            job = st.text_area("Target job description (optional)", height=90,
                               placeholder="Paste a job ad to tailor keywords and emphasis")
            if st.button("✨ Polish with AI", type="primary") and ui.need_key():
                with st.spinner("Rewriting for impact…"):
                    new = llm.safe_run(_polish, r, job.strip())
                if new:
                    st.session_state["resume_pending"] = new
                    st.rerun()
            st.caption("AI keeps your facts, improves wording. Always review before sending.")
    with preview:
        components.html(rr.to_html(r, template, accent, compact), height=900, scrolling=True)
    st.divider()
    if not r["name"].strip():
        st.info("Enter your name to enable the downloads.")
        return
    safe = r["name"].strip().replace(" ", "_")[:40]
    a, b, _ = st.columns([1, 1, 3])
    try:
        a.download_button("⬇️ Download PDF", rr.to_pdf(r, template, accent), f"{safe}_Resume.pdf", "application/pdf",
                          type="primary")
        b.download_button("⬇️ Download Word", rr.to_docx(r, accent), f"{safe}_Resume.docx",
                          "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    except Exception as exc:  # noqa: BLE001
        st.error(f"Couldn't build the file: {exc}")
    st.caption("PDF uses standard fonts (Latin characters). Your data never leaves this session except AI requests to Groq.")
