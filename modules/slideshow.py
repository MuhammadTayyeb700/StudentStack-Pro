import streamlit as st
import streamlit.components.v1 as components

from core import deck as dk
from core import llm, ui

TONES = ["Professional", "Engaging", "Academic", "Simple & friendly", "Persuasive"]
PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


def _make(topic, audience, n, tone, source, want_notes):
    src = f"\nBase the content ONLY on this material:\n{source[:8000]}\n" if source.strip() else ""
    steps = [dict(
        role="Presentation Designer", goal="Create clear, well-structured slide decks",
        backstory="A presentation coach who writes short, punchy bullets and a logical story arc.",
        task=f"Create a slideshow about: {topic}\nAudience: {audience or 'general'}. Tone: {tone}.{src}\n"
             f"Return ONLY valid JSON (no fences): "
             '{"title":"...","subtitle":"...","slides":[{"layout":"bullets|two_column|section","title":"...",'
             '"bullets":["..."],"right":["..."],"notes":"..."}]}\n'
             f"Rules: exactly {n} slides after the title slide (the title slide is added automatically); "
             "max 5 bullets per slide, each under 14 words; use two_column (bullets + right) for comparisons; "
             "use section sparingly; the last slide is 'Key takeaways'. "
             + ("notes = 2-3 sentence speaker script per slide." if want_notes else 'notes must be "".') +
             " Never invent statistics or quotes.",
        expected="Valid JSON deck.")]
    return llm.run_crew(steps, temperature=0.5, max_tokens=3500)


def _val(key, fallback):
    return st.session_state.get(key, fallback)


def _collect():
    """Read the edit widgets back into a deck dict (works in callbacks too)."""
    deck, v = st.session_state.get("deck"), st.session_state.get("deck_ver", 0)
    if not deck:
        return None
    slides = []
    for i, s in enumerate(deck["slides"]):
        k = f"dk{v}_{i}_"
        slides.append(dict(layout=_val(k + "l", s["layout"]), title=_val(k + "t", s["title"]),
                           bullets=_val(k + "b", "\n".join(s["bullets"])), right=_val(k + "r", "\n".join(s["right"])),
                           notes=_val(k + "n", s["notes"])))
    try:
        return dk.normalize(dict(title=_val(f"dk{v}_title", deck["title"]), subtitle=_val(f"dk{v}_sub", deck["subtitle"]),
                                 slides=slides))
    except ValueError:
        return deck


def _bump(deck):
    st.session_state["deck"] = deck
    st.session_state["deck_ver"] = st.session_state.get("deck_ver", 0) + 1


def _move(i, d):
    deck = _collect()
    j = i + d
    if deck and 0 <= j < len(deck["slides"]):
        deck["slides"][i], deck["slides"][j] = deck["slides"][j], deck["slides"][i]
        _bump(deck)


def _delete(i):
    deck = _collect()
    if deck and len(deck["slides"]) > 1:
        deck["slides"].pop(i)
        _bump(deck)


def _add():
    deck = _collect()
    if deck and len(deck["slides"]) < dk.MAX_SLIDES:
        deck["slides"].append(dict(layout="bullets", title="New slide", bullets=["Add your point here"], right=[], notes=""))
        _bump(deck)


def render():
    ui.page_header("🎞️", "Slideshow Maker", "Describe a topic → an editable slideshow you can present in the browser or download as PowerPoint.")
    c1, c2 = st.columns([3, 2])
    with c1:
        topic = ui.sticky(st.text_input, "Topic", "ss_topic", "", placeholder="e.g. How neural networks learn")
        source = ui.sticky(st.text_area, "Source notes (optional — the slides will use only this)", "ss_src", "", height=110)
    with c2:
        audience = ui.sticky(st.text_input, "Audience", "ss_aud", "", placeholder="e.g. first-year students")
        n = ui.sticky(st.slider, "Slides (after the title slide)", "ss_n", 6, min_value=3, max_value=15)
        tone = ui.sticky(st.selectbox, "Tone", "ss_tone", "Engaging", options=TONES)
        want_notes = ui.sticky(st.checkbox, "Write speaker notes", "ss_notes", True)
    if st.button("🎞️ Create slideshow", type="primary", disabled=not topic.strip()) and ui.need_key():
        with st.spinner("Designing your slides…"):
            raw = llm.safe_run(_make, topic.strip(), audience.strip(), n, tone, source, want_notes)
        if raw:
            try:
                _bump(dk.normalize(llm.extract_json(raw)))
            except (ValueError, llm.LLMError) as exc:
                st.error(str(exc))
    try:
        deck = dk.normalize(st.session_state["deck"]) if st.session_state.get("deck") else None
    except ValueError:
        deck = None
    if not deck:
        st.info("Tip: paste your notes under **Source notes** to turn them into slides without any invented facts.")
        return
    st.session_state["deck"] = deck
    v = st.session_state.get("deck_ver", 0)
    st.divider()
    theme = ui.sticky(st.radio, "Theme", "ss_theme", "Indigo", options=list(dk.THEMES), horizontal=True)
    t1, t2 = st.columns([3, 2])
    t1.text_input("Presentation title", deck["title"], key=f"dk{v}_title")
    t2.text_input("Subtitle", deck["subtitle"], key=f"dk{v}_sub")
    for i, s in enumerate(deck["slides"]):
        k = f"dk{v}_{i}_"
        with st.expander(f"{i + 2}. {s['title']}", expanded=False):
            a, b = st.columns([3, 1])
            a.text_input("Slide title", s["title"], key=k + "t")
            b.selectbox("Layout", dk.LAYOUTS, index=dk.LAYOUTS.index(s["layout"]), key=k + "l")
            st.text_area("Bullets (one per line)", "\n".join(s["bullets"]), key=k + "b", height=120)
            if _val(k + "l", s["layout"]) == "two_column":
                st.text_area("Right column (one per line)", "\n".join(s["right"]), key=k + "r", height=100)
            st.text_area("Speaker notes", s["notes"], key=k + "n", height=80)
            x, y, z, _ = st.columns([1, 1, 1, 3])
            x.button("⬆️", key=k + "up", on_click=_move, args=(i, -1), help="Move up")
            y.button("⬇️", key=k + "dn", on_click=_move, args=(i, 1), help="Move down")
            z.button("🗑️", key=k + "rm", on_click=_delete, args=(i,), help="Delete slide")
    st.button("➕ Add a slide", on_click=_add)
    final = _collect() or deck
    if len(final["slides"]) != len(deck["slides"]):
        _bump(final)
        st.rerun()
    st.session_state["deck"] = final
    st.markdown("#### ▶️ Present")
    components.html(dk.to_html(final, theme), height=560)
    st.caption("Arrow keys or ◀ ▶ to move · N shows speaker notes · F goes fullscreen.")
    a, b, c, _ = st.columns([1, 1, 1, 2])
    a.download_button("⬇️ PowerPoint (.pptx)", dk.to_pptx(final, theme), "slideshow.pptx", PPTX, type="primary")
    b.download_button("⬇️ Web slideshow (.html)", dk.to_html(final, theme), "slideshow.html", "text/html")
    c.download_button("⬇️ Outline (.md)", "\n\n".join(
        [f"# {final['title']}\n{final['subtitle']}"] + [f"## {s['title']}\n" + "\n".join(f"- {x}" for x in s["bullets"] + s["right"])
                                                       + (f"\n\n_Notes: {s['notes']}_" if s["notes"] else "") for s in final["slides"]]),
                     "slideshow_outline.md", "text/markdown")
