import json
import threading
from datetime import date

import pandas as pd
import pytest

from core import deck as dk
from core import guard, tracker as tk, utils

TODAY = date(2026, 10, 3)


# ------------------------------------------------------------------ guard
def test_check_code():
    assert guard.check_code("abc", "abc") and not guard.check_code("abd", "abc") and not guard.check_code("", "")


def test_consume_limits_and_rollover():
    store, sess = {}, {}
    for _ in range(3):
        guard.consume(sess, store, 3, 10, "d1")
    with pytest.raises(guard.LimitReached):
        guard.consume(sess, store, 3, 10, "d1")
    other = {}
    for _ in range(7):
        guard.consume(other, store, 100, 10, "d1")
    with pytest.raises(guard.LimitReached):          # 10 used today across visitors
        guard.consume({}, store, 100, 10, "d1")
    guard.consume({}, store, 100, 10, "d2")           # new day resets the shared counter
    assert store["count"] == 1
    guard.consume({}, store, 0, 0, "d2")              # 0 = unlimited


def test_consume_thread_safe():
    store, errs = {}, []

    def work():
        for _ in range(50):
            try:
                guard.consume({}, store, 0, 100, "d")
            except guard.LimitReached:
                errs.append(1)
    ts = [threading.Thread(target=work) for _ in range(4)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert store["count"] == 100 and len(errs) == 100


# ------------------------------------------------------------------ tracker
def test_norm_date():
    assert tk.norm_date("2026-10-05") == "2026-10-05" and tk.norm_date("05/10/2026") == "2026-10-05"
    assert tk.norm_date(pd.Timestamp("2026-10-05 13:00")) == "2026-10-05" and tk.norm_date(date(2026, 10, 5)) == "2026-10-05"
    assert tk.norm_date(pd.NaT) == "" and tk.norm_date(None) == "" and tk.norm_date("soon") == ""
    assert tk.norm_date("2026-10-05T00:00:00.000") == "2026-10-05"


def test_clean_items_and_urgency():
    rows = [dict(Title="Lab", Due="2026-10-02", Hours="x", Done=float("nan"), Priority="Urgent"), dict(Title=" "),
            dict(Title="Exam", Due="2026-10-03", Hours=5, Done=True), dict(Title="Essay", Due="2026-10-20", Hours=3)]
    items = tk.clean_items(rows)
    assert [i["Title"] for i in items] == ["Lab", "Exam", "Essay"]
    assert items[0]["Hours"] == 1.0 and items[0]["Priority"] == "Medium" and items[0]["Done"] is False
    assert tk.urgency(items[0], TODAY)[0] == "Overdue by 1 day" and tk.urgency(items[1], TODAY)[0] == "Done"
    assert tk.urgency(items[2], TODAY)[0] == "17 days left"
    s = tk.summary(items, TODAY)
    assert (s["open"], s["overdue"], s["done"], s["hours"]) == (2, 1, 1, 4.0)
    assert [i["Title"] for i in tk.sort_items(items, TODAY)] == ["Lab", "Essay", "Exam"]


def test_timetable_bridge_and_ics():
    items = tk.clean_items([dict(Title="Lab", Course="PHY", Due="2026-10-04", Hours=2, Priority="Low"),
                            dict(Title="Done one", Done=True, Hours=2), dict(Title="Read", Due="2027-01-01", Hours=1)])
    tasks = tk.to_timetable_tasks(items, TODAY)
    assert [t["Title"] for t in tasks] == ["Lab (PHY)", "Read"] and tasks[0]["Priority"] == "High" and tasks[1]["Priority"] == "Medium"
    ics = tk.ics_deadlines(items)
    assert ics.count("BEGIN:VEVENT") == 2 and "DTSTART;VALUE=DATE:20261004" in ics and "Done one" not in ics


def test_gpa_math():
    g, c = tk.gpa([dict(Credits=3, Grade="A"), dict(Credits=4, Grade="B+"), dict(Credits=2, Grade="??"), dict(Credits=-1, Grade="A")])
    assert (g, c) == (3.6, 7.0) and tk.gpa([]) == (None, 0.0)
    assert round(tk.required_gpa(3.0, 30, 3.5, 15), 2) == 4.5 and tk.required_gpa(3.0, 30, 3.0, 0) is None


# ------------------------------------------------------------------ deck
DECK = {"title": "AI <b>basics</b>", "subtitle": "Intro", "slides": [
    {"layout": "bullets", "title": "Why", "bullets": ["- Fast", "• Cheap"], "notes": "Say hello"},
    {"layout": "two_column", "title": "Pros/cons", "bullets": ["A"], "right": ["B"]},
    {"layout": "two_column", "title": "No right col", "bullets": ["A"]},
    {"layout": "weird", "title": "", "bullets": []}, "junk"]}


def test_deck_normalize():
    d = dk.normalize(DECK)
    assert [s["layout"] for s in d["slides"]] == ["bullets", "two_column", "bullets"] and d["slides"][0]["bullets"] == ["Fast", "Cheap"]
    for bad in ({}, {"slides": []}, "x", None):
        with pytest.raises(ValueError):
            dk.normalize(bad)


@pytest.mark.parametrize("theme", list(dk.THEMES))
def test_deck_pptx_roundtrip(theme):
    out = utils.read_pptx(dk.to_pptx(DECK, theme))
    assert [s["title"] for s in out] == ["AI <b>basics</b>", "Why", "Pros/cons", "No right col"]
    assert out[1]["notes"] == "Say hello" and "Fast" in out[1]["text"]
    assert utils.read_pptx(dk.to_pptx(DECK, theme, notes=False))[1]["notes"] == ""


def test_deck_html_escapes():
    h = dk.to_html(DECK)
    assert "&lt;b&gt;basics" in h and "<b>basics" not in h and h.count('class="s') >= 4


# ------------------------------------------------------------------ essay / cover letter
def test_essay_feedback_normalised():
    from modules import essay
    fb = essay.normalize_feedback(dict(overall=250, criteria=[dict(name="A", score=99, comment="c"), dict(score="x"), "bad"],
                                       strengths="not a list", priority_fixes=[dict(issue="i")], line_edits=[dict(improved="x")]))
    assert fb["overall"] == 100 and [c["score"] for c in fb["criteria"]] == [10, 0] and fb["strengths"] == [] and fb["edits"] == []
    assert "Essay feedback — 100/100" in essay.to_markdown(fb)
    assert essay.normalize_feedback(dict(criteria=[dict(name="A", score=7), dict(name="B", score=5)]))["overall"] == 60
    for bad in (None, {}, {"criteria": []}, {"criteria": ["x"]}):
        with pytest.raises(ValueError):
            essay.normalize_feedback(bad)


def test_resume_context():
    from modules import cover_letter as cl
    assert cl.resume_context(None) == "" and cl.resume_context({"experience": "oops"}) == ""
    ctx = cl.resume_context(dict(name="Sam", title="Dev", skills="Python", experience=[dict(role="Intern", company="X", bullets="a\nb")]))
    assert "Sam · Dev" in ctx and "Skills: Python" in ctx and "Intern; X; a / b" in ctx


# ------------------------------------------------------------------ backup
def test_backup_new_keys_roundtrip():
    from core import backup
    state = {"deck": {"title": "t", "slides": []}, "tr_items": [dict(Title="a")], "gpa_rows": [dict(Course="c")],
             "cover_letter": "Dear", "_essay_text_saved": "essay", "essay_fb": {"overall": 5}, "_used": 3}
    raw = backup.to_json(state)
    assert "_used" not in raw
    data = backup.parse(raw.encode())
    new = {"cl_edit": "old", "tr_editor": 1, "_tr_init": 1}
    labels = backup.apply(new, data)
    assert {"Slideshow", "Deadlines", "GPA courses", "Cover letter", "Essay draft", "Essay feedback"} <= set(labels)
    assert new["es_text"] == "essay" and "cl_edit" not in new and "tr_editor" not in new and new["deck_ver"] == 1
