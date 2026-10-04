from datetime import time

import pandas as pd
import streamlit as st

from core import llm, ui
from core import scheduler as sc

FIXED_DEFAULT = pd.DataFrame([
    dict(Title="Software Engineering", Day="Mon", Start="09:00", End="10:30"),
    dict(Title="Digital Logic", Day="Tue", Start="11:00", End="12:30"),
    dict(Title="Software Engineering", Day="Thu", Start="09:00", End="10:30"),
])
TASKS_DEFAULT = pd.DataFrame([
    dict(Title="Study Data Structures", Hours=4.0, Priority="High", Session=60),
    dict(Title="Project work", Hours=5.0, Priority="Medium", Session=90),
    dict(Title="Exercise", Hours=2.0, Priority="Low", Session=45),
])


def _editor(key, saved_key, init_key, default, **cfg):
    """data_editor that keeps its rows when you switch tools and returns a JSON-friendly copy for backups."""
    import json
    if key not in st.session_state:  # fresh widget: first visit, or we came back from another tool
        saved = st.session_state.get(saved_key)
        st.session_state[init_key] = default.copy() if saved is None else pd.DataFrame(saved, columns=default.columns)
    df = st.data_editor(st.session_state[init_key], num_rows="dynamic", use_container_width=True, key=key, **cfg)
    st.session_state[saved_key] = json.loads(df.to_json(orient="records"))
    return df


def _clean(v):
    return "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v).strip()


def _parse_fixed(df, days, errors):
    out = []
    for i, r in df.iterrows():
        title, day = _clean(r.get("Title")), sc.norm_day(_clean(r.get("Day")))
        s, e = sc.to_min(_clean(r.get("Start"))), sc.to_min(_clean(r.get("End")))
        if not title and not _clean(r.get("Day")):
            continue
        if not (title and day and s is not None and e is not None and e > s):
            errors.append(f"Fixed row {i + 1} ignored (check title, day and HH:MM times).")
            continue
        if day not in days:
            errors.append(f"“{title}” on {day} is outside your selected days — ignored.")
            continue
        out.append(dict(day=day, start=s, end=e, title=title, cat="class"))
    return out


def _parse_tasks(df, errors):
    out = []
    for i, r in df.iterrows():
        title = _clean(r.get("Title"))
        if not title:
            continue
        try:
            hrs = float(r.get("Hours"))
            sess = int(float(r.get("Session") or 60))
        except (TypeError, ValueError):
            errors.append(f"Task row {i + 1} ignored (hours/session must be numbers).")
            continue
        pr = _clean(r.get("Priority")) or "Medium"
        out.append(dict(title=title, minutes=int(round(hrs * 60)), priority=pr if pr in sc.PRIO else "Medium",
                        session=max(sess, 20)))
    return out


def _ai_plan(fixed, tasks, days, ws, we, buffer, prefs):
    fixed_txt = "\n".join(f"- {b['day']} {sc.fmt(b['start'])}-{sc.fmt(b['end'])} {b['title']}" for b in fixed) or "none"
    task_txt = "\n".join(f"- \"{t['title']}\": {t['minutes'] / 60:.1f} h/week, priority {t['priority']}, "
                         f"sessions of about {t['session']} min" for t in tasks)
    raw = llm.single(
        "Academic Schedule Planner", "Build a realistic, balanced weekly plan",
        "A planner who respects fixed commitments, spreads effort, avoids burnout and keeps hard tasks in peak hours.",
        f"Schedule the flexible tasks into free time. Days: {', '.join(days)}. Waking window {sc.fmt(ws)}-{sc.fmt(we)}. "
        f"Keep at least {buffer} min gap between blocks. Never overlap fixed commitments.\n"
        f"FIXED:\n{fixed_txt}\nTASKS:\n{task_txt}\nPREFERENCES: {prefs or 'none'}\n"
        'Return ONLY a JSON array, no fences: [{"day":"Mon","start":"16:00","end":"17:00","title":"exact task title"}]',
        "A JSON array of blocks.", temperature=0.2, max_tokens=3000)
    data = llm.extract_json(raw)
    return data.get("blocks", []) if isinstance(data, dict) else data


def render():
    ui.page_header("🗓️", "Timetable & Schedule Maker",
                   "Add your fixed classes and flexible tasks — get a clash-free weekly plan with calendar export.")
    st.markdown("**1 · Fixed commitments** (classes, work, prayer, gym …)")
    fixed_df = _editor("tt_fixed", "_tt_fixed_saved", "_tt_fixed_init", FIXED_DEFAULT,
                       column_config=dict(Day=st.column_config.SelectboxColumn(options=sc.DAYS, required=True),
                                          Start=st.column_config.TextColumn(help="HH:MM, 24h (or 9:00 AM)"),
                                          End=st.column_config.TextColumn(help="HH:MM")))
    st.markdown("**2 · Flexible tasks** (hours per week to place)")
    task_df = _editor("tt_tasks", "_tt_tasks_saved", "_tt_tasks_init", TASKS_DEFAULT,
                      column_config=dict(Hours=st.column_config.NumberColumn("Hours/week", min_value=0.5, max_value=40, step=0.5),
                                         Priority=st.column_config.SelectboxColumn(options=list(sc.PRIO)),
                                         Session=st.column_config.NumberColumn("Session (min)", min_value=20, max_value=240, step=5)))
    st.markdown("**3 · Preferences**")
    c1, c2, c3 = st.columns(3)
    days = ui.sticky(c1.multiselect, "Days", "tt_days", sc.DAYS[:6], options=sc.DAYS)
    ws_t = ui.sticky(c2.time_input, "Day starts", "tt_ws", time(8, 0))
    we_t = ui.sticky(c3.time_input, "Day ends", "tt_we", time(22, 0))
    c4, c5, c6 = st.columns(3)
    buffer = ui.sticky(c4.slider, "Break between blocks (min)", "tt_buf", 10, min_value=0, max_value=30, step=5)
    prefer = ui.sticky(c5.radio, "Best focus time", "tt_pref", "morning", options=["morning", "evening"], horizontal=True)
    lunch = ui.sticky(c6.toggle, "Add daily lunch break", "tt_lunch", True)
    if lunch:
        l1, l2 = st.columns(2)
        ls_t = ui.sticky(l1.time_input, "Lunch from", "tt_ls", time(13, 0))
        le_t = ui.sticky(l2.time_input, "Lunch to", "tt_le", time(14, 0))
    mode = ui.sticky(st.radio, "Planner", "tt_mode", "⚡ Smart planner (instant, no AI)",
                     options=["⚡ Smart planner (instant, no AI)", "🤖 AI-optimised (Groq)"], horizontal=True)
    prefs = ui.sticky(st.text_input, "Extra wishes for the AI planner", "tt_prefs", "",
                      placeholder="e.g. hard subjects before noon, free Friday evening") if mode.startswith("🤖") else ""

    if st.button("🗓️ Build my timetable", type="primary"):
        errors: list[str] = []
        ws, we = sc.to_min(ws_t), sc.to_min(we_t)
        if not days:
            st.error("Pick at least one day.")
            return
        if we <= ws:
            st.error("Day must end after it starts.")
            return
        fixed = _parse_fixed(fixed_df, days, errors)
        tasks = _parse_tasks(task_df, errors)
        if lunch:
            a, b = sc.to_min(ls_t), sc.to_min(le_t)
            if b > a:
                fixed += [dict(day=d, start=a, end=b, title="Lunch", cat="break") for d in days]
        clash = sc.find_conflicts(fixed)
        placed: list[dict] = []
        todo = tasks
        notes = []
        if mode.startswith("🤖") and tasks and llm.get_api_key():
            with st.spinner("AI is planning your week…"):
                raw = llm.safe_run(_ai_plan, fixed, tasks, days, ws, we, buffer, prefs)
            if raw:
                placed = sc.validate_ai_blocks(raw, fixed, tasks, days, ws, we)
                todo = sc.remaining_tasks(tasks, placed)
                notes.append(f"AI placed {len(placed)} blocks; the smart planner filled in anything it missed.")
            else:
                notes.append("AI planning failed — used the smart planner instead.")
        elif mode.startswith("🤖") and not llm.get_api_key():
            notes.append("No API key — used the smart planner instead.")
        extra, unplaced = sc.greedy_schedule(fixed + placed, todo, days, ws, we, buffer, prefer)
        st.session_state["tt"] = dict(blocks=fixed + placed + extra, unplaced=unplaced, ws=ws, we=we, days=days,
                                      errors=errors, clash=clash, notes=notes)

    tt = st.session_state.get("tt")
    if not tt:
        return
    for m in tt["errors"] + tt["clash"]:
        st.warning(m)
    for m in tt["notes"]:
        st.info(m)
    if tt["unplaced"]:
        st.error("Couldn't fit: " + ", ".join(f"{k} ({v} min)" for k, v in tt["unplaced"].items()) +
                 " — widen the day window, add days, or reduce hours.")
    blocks = sorted(tt["blocks"], key=lambda b: (sc.DAYS.index(b["day"]), b["start"]))
    study = sum(b["end"] - b["start"] for b in blocks if b["cat"] in sc.PRIO)
    m1, m2, m3 = st.columns(3)
    m1.metric("Blocks", len(blocks))
    m2.metric("Flexible hours placed", f"{study / 60:.1f}")
    m3.metric("Class/fixed hours", f"{sum(b['end'] - b['start'] for b in blocks if b['cat'] in ('class', 'break')) / 60:.1f}")
    st.markdown(sc.grid_html(blocks, tt["days"], tt["ws"], tt["we"]), unsafe_allow_html=True)
    st.caption("Colours: 🟦 fixed  🟥 high  🟧 medium  🟩 low  ⬜ break")
    df = pd.DataFrame([dict(Day=b["day"], Start=sc.fmt(b["start"]), End=sc.fmt(b["end"]), Title=b["title"], Type=b["cat"])
                       for b in blocks])
    a, b, _ = st.columns([1, 1, 3])
    a.download_button("⬇️ CSV", df.to_csv(index=False), "timetable.csv", "text/csv")
    b.download_button("📅 Calendar (.ics)", sc.ics_text(blocks), "timetable.ics", "text/calendar")
    with st.expander("Table view"):
        st.dataframe(df, use_container_width=True, hide_index=True)
