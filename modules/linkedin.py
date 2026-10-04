import html

import streamlit as st

from core import llm, ui

STYLES = ["Personal story", "Lessons learned", "Listicle / tips", "Announcement", "Hot take / opinion",
          "Achievement / milestone", "Question to spark discussion"]


def _run(topic, goal, audience, style, tone, length, emojis, tags, cta, name, headline, n):
    steps = [
        dict(role="LinkedIn Content Strategist", goal="Pick hooks and angles that earn engagement",
             backstory="A growth strategist who knows what stops the scroll on LinkedIn without sounding fake.",
             task=f"Plan {n} different post angles for: {topic}\nAuthor: {name or 'the author'} — {headline or 'professional'}\n"
                  f"Goal: {goal}\nAudience: {audience}\nStyle: {style}\nFor each angle give a scroll-stopping first line and a short outline.",
             expected="Hooks and outlines."),
        dict(role="LinkedIn Copywriter", goal="Write authentic, high-performing posts and return strict JSON",
             backstory="A copywriter with a human voice: short lines, white space, zero buzzword soup.",
             task=f"Write {n} complete LinkedIn posts from the angles. Tone: {tone}. Length: {length}. Emoji use: {emojis}. "
                  f"Hashtags: {tags}. Call to action: {cta}. Keep each post under 2800 characters. "
                  'Return ONLY valid JSON, no fences: {"posts":[{"post":"full text with \\n line breaks",'
                  '"hashtags":["#tag"]}]}. Put hashtags only in the hashtags list.',
             expected="Valid JSON."),
    ]
    return llm.run_crew(steps, max_tokens=3000)


def render():
    ui.page_header("💼", "LinkedIn Post Studio", "Tailor-made posts in your voice — hooks, structure, hashtags and a live preview.")
    c1, c2 = st.columns(2)
    with c1:
        topic = ui.sticky(st.text_area, "What's the post about?", "li_topic", "", height=110,
                          placeholder="e.g. I just finished my first internship project: a RAG chatbot for university notes")
        goal = ui.sticky(st.selectbox, "Goal", "li_goal", "Build personal brand",
                         options=["Build personal brand", "Get job opportunities", "Share knowledge",
                                  "Promote a project/product", "Celebrate a win", "Start a conversation"])
        audience = ui.sticky(st.text_input, "Audience", "li_aud", "recruiters and engineers")
        c3, c4 = st.columns(2)
        name = ui.sticky(c3.text_input, "Your name", "li_name", "")
        headline = ui.sticky(c4.text_input, "Your headline", "li_head", "", placeholder="CE student | AI enthusiast")
    with c2:
        style = ui.sticky(st.selectbox, "Post style", "li_style", STYLES[0], options=STYLES)
        tone = ui.sticky(st.selectbox, "Tone", "li_tone", "Authentic & conversational",
                         options=["Authentic & conversational", "Professional", "Inspirational", "Witty", "Analytical"])
        length = ui.sticky(st.select_slider, "Length", "li_len", "Medium", options=["Short", "Medium", "Long"])
        emojis = ui.sticky(st.select_slider, "Emojis", "li_emo", "Few", options=["None", "Few", "Moderate"])
        tags = ui.sticky(st.slider, "Hashtags", "li_tags", 4, min_value=0, max_value=8)
        cta = ui.sticky(st.text_input, "Call to action", "li_cta", "Ask a question to invite comments")
        n = ui.sticky(st.slider, "Variants", "li_n", 2, min_value=1, max_value=3)
    if st.button("✨ Create posts", type="primary", disabled=not topic.strip()):
        if ui.need_key():
            with st.spinner("Strategist and copywriter are working…"):
                raw = llm.safe_run(_run, topic.strip(), goal, audience, style, tone, length, emojis, tags, cta,
                                   name.strip(), headline.strip(), n)
            if raw:
                try:
                    posts = llm.extract_json(raw)["posts"]
                    st.session_state["li_posts"] = [dict(post=str(p.get("post", "")), hashtags=[str(h) for h in p.get("hashtags", [])])
                                                    for p in posts][:3]
                    st.session_state["li_meta"] = (name.strip() or "Your Name", headline.strip())
                except Exception:  # noqa: BLE001
                    st.session_state["li_posts"] = [dict(post=raw, hashtags=[])]
                    st.session_state["li_meta"] = (name.strip() or "Your Name", headline.strip())
    posts = st.session_state.get("li_posts")
    if posts:
        who, sub = st.session_state.get("li_meta", ("Your Name", ""))
        tabs = st.tabs([f"Variant {i + 1}" for i in range(len(posts))])
        for i, (tab, p) in enumerate(zip(tabs, posts)):
            with tab:
                default = p["post"] + ("\n\n" + " ".join(p["hashtags"]) if p["hashtags"] else "")
                text = st.text_area("Edit your post", default, height=280, key=f"li_t_{i}_{hash(default)}")
                st.caption(f"{len(text)} / 3000 characters" + (" ⚠️ too long" if len(text) > 3000 else ""))
                st.markdown(f'<div class="lcard"><div class="who">{html.escape(who)}</div><div class="sub">{html.escape(sub)} · now · 🌐</div>'
                            f'{html.escape(text)}</div>', unsafe_allow_html=True)
                st.download_button("⬇️ Save .txt", text, f"linkedin_post_{i + 1}.txt", key=f"li_d_{i}")
