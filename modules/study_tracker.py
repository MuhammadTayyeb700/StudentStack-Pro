import html
import json
from datetime import date, timedelta

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from core import tracker as tk
from core import ui

COLS = ["Done", "Title", "Course", "Due", "Hours", "Priority"]
GPA_COLS = ["Course", "Credits", "Grade"]
GPA_DEFAULT = [dict(Course="Calculus", Credits=3.0, Grade="A-"), dict(Course="Physics", Credits=4.0, Grade="B+"),
               dict(Course="Programming", Credits=3.0, Grade="A")]

POMODORO = """<div style="font-family:Segoe UI,Arial,sans-serif;max-width:420px;margin:auto;text-align:center;color:#1f2937">
<div id="mode" style="font-weight:700;color:#4f46e5;letter-spacing:.08em">FOCUS</div>
<div id="t" style="font-size:72px;font-weight:700;line-height:1.1;margin:6px 0">25:00</div>
<div style="height:8px;background:#e5e7eb;border-radius:8px;overflow:hidden"><div id="bar" style="height:8px;width:0;background:#4f46e5"></div></div>
<div style="margin:14px 0"><button id="go">Start</button> <button id="rs">Reset</button> <button id="skip">Skip</button></div>
<div id="n" style="font-size:14px;opacity:.7">Completed focus sessions: 0</div></div>
<style>button{background:#4f46e5;color:#fff;border:0;border-radius:10px;padding:9px 18px;font-size:15px;font-weight:600;cursor:pointer}
button:nth-child(n+2){background:#e5e7eb;color:#1f2937}@media(prefers-color-scheme:dark){div{color:#e5e7eb!important}}</style>
<script>
const F=__FOCUS__*60,B=__BREAK__*60;let focus=true,left=F,run=false,iv=null,done=0;
const $=id=>document.getElementById(id);
function draw(){const m=String(Math.floor(left/60)).padStart(2,'0'),s=String(left%60).padStart(2,'0');$('t').textContent=m+':'+s;
$('mode').textContent=focus?'FOCUS':'BREAK';$('bar').style.width=(100*(1-left/(focus?F:B)))+'%';$('bar').style.background=focus?'#4f46e5':'#10b981';
$('go').textContent=run?'Pause':'Start';$('n').textContent='Completed focus sessions: '+done;}
function beep(){try{const c=new (window.AudioContext||window.webkitAudioContext)(),o=c.createOscillator();o.connect(c.destination);o.frequency.value=880;o.start();setTimeout(()=>o.stop(),400);}catch(e){}}
function sw(){if(focus)done++;focus=!focus;left=focus?F:B;beep();draw();}
function tick(){left--;if(left<=0)sw();else draw();}
$('go').onclick=()=>{run=!run;if(run)iv=setInterval(tick,1000);else clearInterval(iv);draw();};
$('rs').onclick=()=>{clearInterval(iv);run=false;focus=true;left=F;draw();};$('skip').onclick=()=>sw();draw();
</script>"""


def _table(key, saved_key, init_key, default_rows, columns, dates=(), **cfg):
    """data_editor that keeps its rows when you switch tools (same trick as the Timetable Maker)."""
    if key not in st.session_state:
        saved = st.session_state.get(saved_key)
        df0 = pd.DataFrame(default_rows if saved is None else saved, columns=columns)
        for c in dates:  # DateColumn needs real dates, not strings
            df0[c] = pd.to_datetime(df0[c], errors="coerce").dt.date
        st.session_state[init_key] = df0
    df = st.data_editor(st.session_state[init_key], num_rows="dynamic", use_container_width=True, key=key, **cfg)
    return json.loads(df.to_json(orient="records", date_format="iso"))


def _add_item(title, course, due, hours, prio):
    items = tk.clean_items(st.session_state.get("tr_items") or [])
    items.append(dict(Done=False, Title=title, Course=course, Due=tk.norm_date(due), Hours=hours, Priority=prio))
    st.session_state["tr_items"] = tk.clean_items(items)
    for k in ("tr_editor", "_tr_init"):
        st.session_state.pop(k, None)


def _send_to_timetable(items, today):
    new = tk.to_timetable_tasks(items, today)
    saved = st.session_state.get("_tt_tasks_saved")
    rows = [r for r in (saved or []) if isinstance(r, dict)]
    have = {str(r.get("Title", "")).strip().lower() for r in rows}
    added = [t for t in new if t["Title"].lower() not in have]
    st.session_state["_tt_tasks_saved"] = rows + added
    for k in ("tt_tasks", "_tt_tasks_init"):
        st.session_state.pop(k, None)
    st.session_state["_tr_msg"] = (f"Added {len(added)} task(s) to the Timetable Maker "
                                   f"({len(new) - len(added)} already there). Open it to schedule them.")


def _deadlines(today):
    items = tk.clean_items(st.session_state.get("tr_items") or [])
    s = tk.summary(items, today)
    c = st.columns(5)
    c[0].metric("Open", s["open"])
    c[1].metric("Overdue", s["overdue"])
    c[2].metric("Due in 7 days", s["week"])
    c[3].metric("Hours left", s["hours"])
    c[4].metric("Completed", f"{round(100 * s['done'] / s['total'])}%" if s["total"] else "—")
    with st.form("tr_add", clear_on_submit=True):
        a, b, c2, d, e = st.columns([3, 2, 2, 1, 1])
        title = a.text_input("Assignment / exam", placeholder="e.g. Lab report 3")
        course = b.text_input("Course")
        due = c2.date_input("Due date", value=today + timedelta(days=7))
        hours = d.number_input("Hours", 0.5, 100.0, 2.0, 0.5)
        prio = e.selectbox("Priority", tk.PRIORITIES, index=1)
        if st.form_submit_button("➕ Add", type="primary") and title.strip():
            _add_item(title.strip(), course.strip(), due, hours, prio)
            st.rerun()
    rows = _table("tr_editor", "tr_items", "_tr_init", [], COLS, dates=("Due",), column_config={
        "Done": st.column_config.CheckboxColumn("Done", default=False),
        "Title": st.column_config.TextColumn("Title", required=True),
        "Due": st.column_config.DateColumn("Due", format="YYYY-MM-DD"),
        "Hours": st.column_config.NumberColumn("Hours", min_value=0.0, max_value=200.0, step=0.5, default=1.0),
        "Priority": st.column_config.SelectboxColumn("Priority", options=tk.PRIORITIES, default="Medium")})
    items = tk.clean_items(rows)
    st.session_state["tr_items"] = items
    if not items:
        st.info("No deadlines yet — add your first one above.")
        return
    st.markdown("#### Coming up")
    for it in tk.sort_items(items, today)[:12]:
        label, color = tk.urgency(it, today)
        due = html.escape(it["Due"]) if it["Due"] else "no date"
        course = f" · {html.escape(it['Course'])}" if it["Course"] else ""
        strike = "text-decoration:line-through;opacity:.55;" if it["Done"] else ""
        st.markdown(f'<div style="display:flex;justify-content:space-between;align-items:center;padding:.55rem .9rem;margin-bottom:.4rem;'
                    f'border-radius:12px;border:1px solid rgba(128,128,128,.25);border-left:6px solid {color}">'
                    f'<span style="{strike}"><b>{html.escape(it["Title"])}</b>{course}<br>'
                    f'<small style="opacity:.7">{due} · {it["Hours"]:g} h · {it["Priority"]}</small></span>'
                    f'<span style="color:{color};font-weight:700">{label}</span></div>', unsafe_allow_html=True)
    a, b, c3 = st.columns(3)
    a.button("➡️ Send open tasks to Timetable Maker", on_click=_send_to_timetable, args=(items, today), use_container_width=True)
    b.download_button("📆 Deadlines (.ics)", tk.ics_deadlines(items), "deadlines.ics", "text/calendar", use_container_width=True)
    if c3.button("🧹 Clear completed", use_container_width=True):
        st.session_state["tr_items"] = [i for i in items if not i["Done"]]
        for k in ("tr_editor", "_tr_init"):
            st.session_state.pop(k, None)
        st.rerun()
    msg = st.session_state.pop("_tr_msg", None)
    if msg:
        st.success(msg)


def _timer():
    a, b, _ = st.columns([1, 1, 2])
    focus = ui.sticky(a.number_input, "Focus minutes", "pm_focus", 25, min_value=5, max_value=90, step=5)
    brk = ui.sticky(b.number_input, "Break minutes", "pm_break", 5, min_value=1, max_value=30, step=1)
    components.html(POMODORO.replace("__FOCUS__", str(int(focus))).replace("__BREAK__", str(int(brk))), height=300)
    st.caption("Runs in your browser, so it keeps counting while you work in another tab. Keep this tab open.")


def _gpa():
    rows = _table("gpa_editor", "gpa_rows", "_gpa_init", GPA_DEFAULT, GPA_COLS, column_config={
        "Credits": st.column_config.NumberColumn("Credits", min_value=0.0, max_value=60.0, step=0.5, default=3.0),
        "Grade": st.column_config.SelectboxColumn("Grade", options=list(tk.GRADES))})
    st.session_state["gpa_rows"] = [r for r in rows if isinstance(r, dict)][:60]
    g, credits = tk.gpa(rows)
    a, b = st.columns(2)
    a.metric("Semester GPA (4.0 scale)", f"{g:.2f}" if g is not None else "—")
    b.metric("Credits counted", f"{credits:g}")
    st.markdown("#### What do I need next semester?")
    c1, c2, c3, c4 = st.columns(4)
    cur = c1.number_input("Current cumulative GPA", 0.0, 4.0, float(g or 3.0), 0.01)
    cur_c = c2.number_input("Credits so far", 0.0, 400.0, max(credits, 30.0), 1.0)
    target = c3.number_input("Target cumulative GPA", 0.0, 4.0, 3.5, 0.05)
    new_c = c4.number_input("Credits to come", 1.0, 200.0, 15.0, 1.0)
    need = tk.required_gpa(cur, cur_c, target, new_c)
    if need is None:
        return
    if need > 4.0:
        st.error(f"Not reachable in {new_c:g} credits: you'd need {need:.2f}, above the 4.0 maximum.")
    elif need <= 0:
        st.success("You'll stay above your target even with a 0.0 — keep going!")
    else:
        st.info(f"You need an average of **{need:.2f}** across the next {new_c:g} credits to finish on {target:.2f}.")
    st.caption("Uses a standard 4.0 scale (A+ = 4.0). Your university's scale may differ.")


def render():
    ui.page_header("📅", "Study Tracker", "Deadlines with urgency alerts, a focus timer and a GPA calculator — no AI key needed.")
    today = date.today()
    t1, t2, t3 = st.tabs(["📅 Deadlines", "⏱️ Focus timer", "🎓 GPA calculator"])
    with t1:
        _deadlines(today)
    with t2:
        _timer()
    with t3:
        _gpa()
