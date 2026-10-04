import csv
import html
import io
import time

import streamlit as st

from core import llm, ui, utils

NOTE_STYLES = {
    "Detailed study notes": "detailed, well-structured study notes with headings, sub-bullets, definitions in bold, formulas and examples",
    "Cornell-style": "Cornell-style notes: a 'Cues/Questions' list, main 'Notes', and a 2-sentence 'Summary' per section",
    "Exam cheat-sheet": "an ultra-compact exam cheat-sheet: key formulas, definitions, rules, and memory hooks",
    "Outline": "a hierarchical outline with short phrases",
}
MAX_MB = 30


def _load(files):
    all_pages, chunks, names = [], [], []
    for f in files:
        data = f.getvalue()
        if len(data) > MAX_MB * 1024 * 1024:
            st.error(f"{f.name}: larger than {MAX_MB} MB.")
            continue
        try:
            pages = utils.read_pdf(data)
        except Exception as exc:  # noqa: BLE001
            st.error(f"{f.name}: could not read ({exc}).")
            continue
        if not any(t for _, t in pages):
            st.warning(f"{f.name}: no selectable text found (scanned PDF?). OCR is not supported.")
            continue
        names.append(f.name)
        tagged = [(p, t) for p, t in pages if t]
        all_pages += [(f.name, p, t) for p, t in tagged]
        chunks += utils.chunk_pages(tagged, source=f.name)
    if not chunks:
        return None
    return dict(names=names, pages=all_pages, chunks=chunks, retriever=utils.Retriever(chunks))


def _make_notes(rag, style, max_chars, bar):
    texts = [f"[{src} p.{p}]\n{t}" for src, p, t in rag["pages"]]
    total, kept = 0, []
    for t in texts:
        if total + len(t) > max_chars:
            break
        kept.append(t)
        total += len(t)
    groups = utils.group_by_chars(kept, 6500)
    out = []
    for gi, g in enumerate(groups, 1):
        bar.progress(gi / len(groups), text=f"Writing notes… part {gi}/{len(groups)}")
        body = "\n\n".join(kept[i] for i in g)
        txt = llm.single(
            "Expert Note-Taker", "Turn source material into excellent notes",
            "A top student who writes notes that are accurate, complete and easy to revise from.",
            f"Create {NOTE_STYLES[style]} from the source text below. Use Markdown. Be faithful to the text; "
            f"do not add outside facts. Keep page references like (p.4) where helpful.\n\nSOURCE:\n{body}",
            "Markdown notes.", max_tokens=2500)
        out.append(txt)
        if gi < len(groups):
            time.sleep(1)
    bar.empty()
    note = "\n\n---\n\n".join(out)
    if len(kept) < len(texts):
        note += f"\n\n> ⚠️ Only the first {len(kept)} of {len(texts)} pages were used (limit: {max_chars:,} characters)."
    return note


def _make_cards(rag, n, topic):
    if topic.strip():
        ctx = "\n\n".join(c["text"] for c in rag["retriever"].search(topic, 10))
    else:
        ch = rag["chunks"]
        step = max(len(ch) // 12, 1)
        ctx = "\n\n".join(c["text"] for c in ch[::step][:12])
    ctx = ctx[:11000]
    raw = llm.single(
        "Flashcard Designer", "Create effective active-recall flashcards",
        "A learning scientist who writes one atomic idea per card, with unambiguous questions.",
        f"From the material below create exactly {n} flashcards"
        f"{' about: ' + topic if topic.strip() else ''}. Return ONLY a JSON array like "
        '[{"question":"...","answer":"..."}] — no fences, no commentary.\n\nMATERIAL:\n' + ctx,
        "A JSON array.", temperature=0.3, max_tokens=3000)
    data = llm.extract_json(raw)
    if isinstance(data, dict):
        data = data.get("flashcards") or data.get("cards") or []
    cards = [dict(q=str(c.get("question", "")).strip(), a=str(c.get("answer", "")).strip())
             for c in data if isinstance(c, dict)]
    cards = [c for c in cards if c["q"] and c["a"]]
    if not cards:
        raise llm.LLMError("No flashcards were produced. Try again or choose a topic.")
    return cards


def _answer(rag, question):
    hits = rag["retriever"].search(question, 5)
    if not hits:
        return "I couldn't find anything related to that in your PDFs.", []
    ctx = "\n\n".join(f"[{h['source']} p.{h['page']}]\n{h['text']}" for h in hits)
    ans = llm.single(
        "Document Q&A Assistant", "Answer only from the provided excerpts",
        "A careful tutor who cites page numbers and admits when the document doesn't say.",
        f"Answer the question using ONLY these excerpts. Cite pages like (p.3). If the answer isn't there, say so.\n\n"
        f"EXCERPTS:\n{ctx}\n\nQUESTION: {question}", "A concise, cited answer.", temperature=0.2, max_tokens=1200)
    return ans, hits


def render():
    ui.page_header("📚", "PDF Study Lab (RAG)", "Upload PDFs → notes, flashcards, and a chat that answers with page citations.")
    files = st.file_uploader("Upload one or more PDFs", type=["pdf"], accept_multiple_files=True)
    if st.button("📥 Process documents", type="primary", disabled=not files):
        with st.spinner("Reading and indexing…"):
            rag = _load(files)
        if rag:
            st.session_state["rag"] = rag
            for k in ("rag_notes", "rag_cards", "rag_chat", "card_i", "card_show"):
                st.session_state.pop(k, None)
    rag = st.session_state.get("rag")
    if not rag:
        st.info("Upload a text-based PDF and click **Process documents**.")
        return
    n_chars = sum(len(t) for _, _, t in rag["pages"])
    st.success(f"Indexed {len(rag['names'])} file(s) · {len(rag['pages'])} pages · {len(rag['chunks'])} chunks · {n_chars:,} characters")
    t1, t2, t3 = st.tabs(["📝 Notes", "🃏 Flashcards", "💬 Ask your PDF"])

    with t1:
        c1, c2 = st.columns(2)
        style = ui.sticky(c1.selectbox, "Note style", "sr_style", list(NOTE_STYLES)[0], options=list(NOTE_STYLES))
        max_chars = ui.sticky(c2.select_slider, "Max characters to read", "sr_max", 40000,
                              options=[20000, 40000, 60000, 100000],
                              help="Higher = more complete, but uses more of your Groq quota.")
        if st.button("Generate notes", key="gen_notes") and ui.need_key():
            bar = st.progress(0.0, text="Starting…")
            notes = llm.safe_run(_make_notes, rag, style, max_chars, bar)
            bar.empty()
            if notes:
                st.session_state["rag_notes"] = notes
        notes = st.session_state.get("rag_notes")
        if notes:
            st.markdown(notes)
            a, b, c, _ = st.columns([1, 1, 1, 2])
            pdf = utils.safe_pdf(notes, "Study Notes")
            a.download_button("⬇️ PDF", pdf, "notes.pdf", "application/pdf", disabled=not pdf, type="primary")
            b.download_button("⬇️ Markdown", notes, "notes.md", "text/markdown")
            c.download_button("⬇️ Word", utils.md_to_docx(notes, "Study Notes"), "notes.docx",
                              "application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    with t2:
        c1, c2 = st.columns([1, 2])
        n = ui.sticky(c1.slider, "Cards", "sr_n", 15, min_value=5, max_value=40)
        topic = ui.sticky(c2.text_input, "Focus topic (optional)", "sr_topic", "",
                          placeholder="Leave empty to cover the whole document")
        if st.button("Generate flashcards", key="gen_cards") and ui.need_key():
            with st.spinner("Designing flashcards…"):
                cards = llm.safe_run(_make_cards, rag, n, topic)
            if cards:
                st.session_state.update(rag_cards=cards, card_i=0, card_show=False)
        cards = st.session_state.get("rag_cards")
        if cards:
            i = min(st.session_state.get("card_i", 0), len(cards) - 1)
            show = st.session_state.get("card_show", False)
            card = cards[i]
            st.caption(f"Card {i + 1} of {len(cards)}")
            st.markdown(f'<div class="flash {"back" if show else ""}">{html.escape(card["a"] if show else card["q"])}</div>',
                        unsafe_allow_html=True)
            a, b, c, _ = st.columns([1, 1, 1, 3])
            if a.button("⬅️ Prev", disabled=i == 0):
                st.session_state.update(card_i=i - 1, card_show=False)
                st.rerun()
            if b.button("🔄 Flip"):
                st.session_state["card_show"] = not show
                st.rerun()
            if c.button("Next ➡️", disabled=i == len(cards) - 1):
                st.session_state.update(card_i=i + 1, card_show=False)
                st.rerun()
            buf = io.StringIO()
            w = csv.writer(buf, delimiter="\t")
            for cd in cards:
                w.writerow([cd["q"], cd["a"]])
            e1, e2, e3, _ = st.columns([1.3, 1, 1, 1])
            try:
                cards_pdf = utils.flashcards_pdf(cards, "Flashcards")
            except Exception:  # noqa: BLE001
                cards_pdf = b""
            e1.download_button("🖨️ Printable PDF", cards_pdf, "flashcards_print.pdf", "application/pdf",
                               disabled=not cards_pdf, type="primary",
                               help="8 cards per page. Print double-sided (flip on long edge) and cut along the dashed lines.")
            e2.download_button("⬇️ CSV (Quizlet)", utils.flashcards_csv(cards), "flashcards.csv", "text/csv")
            e3.download_button("⬇️ Anki (TSV)", buf.getvalue(), "flashcards.tsv", "text/tab-separated-values")
            with st.expander("See all cards"):
                for k, cd in enumerate(cards, 1):
                    st.markdown(f"**{k}. {cd['q']}**  \n{cd['a']}")

    with t3:
        chat = st.session_state.setdefault("rag_chat", [])
        for m in chat:
            with st.chat_message(m["role"]):
                st.markdown(m["content"])
                if m.get("src"):
                    st.caption("Sources: " + ", ".join(m["src"]))
        q = st.chat_input("Ask something about your PDFs…")
        if q:
            chat.append(dict(role="user", content=q))
            with st.chat_message("user"):
                st.markdown(q)
            if llm.get_api_key():
                with st.chat_message("assistant"), st.spinner("Searching your PDFs…"):
                    res = llm.safe_run(_answer, rag, q)
                if res:
                    ans, hits = res
                    src = sorted({f"{h['source']} p.{h['page']}" for h in hits})
                    chat.append(dict(role="assistant", content=ans, src=src))
                    st.rerun()
            else:
                ui.need_key()
