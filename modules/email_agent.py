import urllib.parse

import streamlit as st

from core import llm, ui

TEMPLATES = {
    "Custom": "",
    "Job application": "Apply for the role of [position] at [company] and attach my CV",
    "Follow-up after interview": "Thank the interviewer and politely ask about next steps",
    "Request to professor": "Ask my professor for an extension / meeting / recommendation letter",
    "Leave request": "Request leave from [date] to [date] and explain coverage",
    "Complaint": "Politely complain about a problem and ask for a resolution",
    "Cold outreach": "Introduce myself and propose a short call",
    "Apology": "Apologise for a mistake and explain how I'll fix it",
}
LANGS = ["English", "Urdu", "Roman Urdu", "Arabic", "French", "Spanish", "German"]


def _run(purpose, recipient, sender, tone, length, points, original, lang, n):
    steps = [
        dict(role="Executive Communications Writer", goal="Write emails that get a response",
             backstory="A professional writer with a gift for clear, courteous, effective emails.",
             task=f"Write {n} distinct email option(s).\nGoal: {purpose}\nRecipient: {recipient}\nSender: {sender or 'the sender'}\n"
                  f"Tone: {tone}\nLength: {length}\nKey points to include: {points or 'none'}\nLanguage: {lang}\n"
                  f"Email being replied to (if any): {original or 'none'}\n"
                  "Each email needs a compelling subject line, greeting, body and sign-off. No placeholders unless info is missing.",
             expected="Draft emails."),
        dict(role="Proofreader", goal="Polish the drafts and return strict JSON",
             backstory="An editor who fixes grammar, tone and clarity without changing the meaning.",
             task="Proofread the drafts. Return ONLY valid JSON, no markdown fences, in this shape: "
                  '{"emails":[{"subject":"...","body":"..."}]} using \\n for line breaks inside body.',
             expected="Valid JSON."),
    ]
    return llm.run_crew(steps, max_tokens=2500)


def render():
    ui.page_header("✉️", "Email Writer", "Describe the goal — get polished, ready-to-send emails in the tone you choose.")
    c1, c2 = st.columns(2)
    with c1:
        tpl = ui.sticky(st.selectbox, "Quick start", "em_tpl", "Custom", options=list(TEMPLATES))
        purpose = st.text_area("What should this email achieve?", value=TEMPLATES[tpl], height=100, key=f"em_p_{tpl}")
        recipient = ui.sticky(st.text_input, "Who is it to?", "em_rec", "", placeholder="e.g. Dr. Khan, my course instructor")
        sender = ui.sticky(st.text_input, "Your name", "em_snd", "")
    with c2:
        tone = ui.sticky(st.selectbox, "Tone", "em_tone", "Professional",
                         options=["Professional", "Friendly", "Formal", "Persuasive", "Apologetic", "Concise & direct"])
        length = ui.sticky(st.select_slider, "Length", "em_len", "Short", options=["Very short", "Short", "Medium", "Detailed"])
        lang = ui.sticky(st.selectbox, "Language", "em_lang", "English", options=LANGS)
        n = ui.sticky(st.slider, "Options to generate", "em_n", 2, min_value=1, max_value=3)
        points = ui.sticky(st.text_area, "Key points to include (optional)", "em_pts", "", height=68)
    with st.expander("Replying to an email? Paste it here"):
        original = ui.sticky(st.text_area, "Original email", "em_orig", "", height=120, label_visibility="collapsed")
    if st.button("✨ Generate emails", type="primary", disabled=not purpose.strip()):
        if ui.need_key():
            with st.spinner("Writing and proofreading…"):
                raw = llm.safe_run(_run, purpose.strip(), recipient.strip() or "the recipient", sender.strip(),
                                   tone, length, points.strip(), original.strip(), lang, n)
            if raw:
                try:
                    items = llm.extract_json(raw)["emails"]
                    st.session_state["emails"] = [dict(subject=str(i.get("subject", "")), body=str(i.get("body", "")))
                                                  for i in items][:3]
                except Exception:  # noqa: BLE001
                    st.session_state["emails"] = [dict(subject="", body=raw)]
    mails = st.session_state.get("emails")
    if mails:
        tabs = st.tabs([f"Option {i + 1}" for i in range(len(mails))])
        for i, (tab, m) in enumerate(zip(tabs, mails)):
            with tab:
                subj = st.text_input("Subject", m["subject"], key=f"em_s_{i}_{hash(m['subject'])}")
                body = st.text_area("Body", m["body"], height=300, key=f"em_b_{i}_{hash(m['body'])}")
                a, b, _ = st.columns([1, 1, 2])
                url = "mailto:?subject=" + urllib.parse.quote(subj) + "&body=" + urllib.parse.quote(body[:1500])
                a.link_button("📨 Open in mail app", url)
                b.download_button("⬇️ Save .txt", f"Subject: {subj}\n\n{body}", f"email_{i + 1}.txt")
