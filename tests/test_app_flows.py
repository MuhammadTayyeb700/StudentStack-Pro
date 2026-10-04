"""End-to-end UI flows with a fake LLM (no network, no API key needed)."""
import json

import pytest
from streamlit.testing.v1 import AppTest

from core import guard, llm

ESSAY = "This essay argues that renewable energy matters. " * 8
FB = dict(overall=82, grade_band="B+", summary="Solid.", criteria=[dict(name="Thesis", score=8, comment="Clear", fix="Sharpen")],
          strengths=["Clear"], priority_fixes=[dict(issue="Evidence", where="renewable energy", suggestion="Cite")],
          line_edits=[dict(original="matters", improved="is vital", why="Stronger")], next_steps=["Add sources"])
DECK = dict(title="Energy", subtitle="Intro", slides=[dict(layout="bullets", title="Why", bullets=["A", "B"], notes="n"),
                                                      dict(layout="bullets", title="Takeaways", bullets=["C"])])


def _app(monkeypatch, reply=None):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_testtesttesttesttest")
    if reply is not None:
        monkeypatch.setattr(llm, "run_crew", lambda steps, **kw: reply if isinstance(reply, str) else json.dumps(reply))
    at = AppTest.from_file("app.py", default_timeout=60).run()
    assert not at.exception
    return at


def _go(at, label):
    at.sidebar.radio[0].set_value(label).run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def test_essay_flow(monkeypatch):
    at = _go(_app(monkeypatch, FB), "🧾 Essay Feedback")
    at.text_area(key="es_text").set_value(ESSAY).run()
    next(b for b in at.button if "Get feedback" in b.label).click().run()
    assert not at.exception and not at.error
    assert any("82/100" in m.value for m in at.metric)
    assert at.session_state["essay_fb"]["overall"] == 82


def test_cover_letter_flow(monkeypatch):
    at = _app(monkeypatch, "Dear Hiring Manager,\n\nI build things.\n\nSam")
    at.session_state["resume"] = dict(name="Sam", title="Dev", skills="Python", experience=[], education=[], projects=[])
    at = _go(at, "💌 Cover Letter")
    at.text_area(key="cl_ad").set_value("We need a Python developer who loves building AI tools and shipping fast.").run()
    next(b for b in at.button if "Write cover letter" in b.label).click().run()
    assert not at.exception and at.text_area(key="cl_edit").value.startswith("Dear Hiring Manager")


def test_cover_letter_blocked_without_facts(monkeypatch):
    at = _go(_app(monkeypatch, "x"), "💌 Cover Letter")
    at.text_area(key="cl_ad").set_value("We need a Python developer who loves building AI tools and shipping fast.").run()
    assert next(b for b in at.button if "Write cover letter" in b.label).disabled


def test_slideshow_flow_and_edit(monkeypatch):
    at = _go(_app(monkeypatch, DECK), "🎞️ Slideshow Maker")
    at.text_input(key="ss_topic").set_value("Energy").run()
    next(b for b in at.button if "Create slideshow" in b.label).click().run()
    assert not at.exception and len(at.session_state["deck"]["slides"]) == 2
    v = at.session_state["deck_ver"]
    at.text_input(key=f"dk{v}_0_t").set_value("Why it matters").run()
    assert at.session_state["deck"]["slides"][0]["title"] == "Why it matters"
    next(b for b in at.button if (b.key or "") == f"dk{v}_0_dn").click().run()      # move down
    assert at.session_state["deck"]["slides"][1]["title"] == "Why it matters"
    next(b for b in at.button if (b.key or "").endswith("_rm")).click().run()        # delete first
    assert len(at.session_state["deck"]["slides"]) == 1
    assert any("PowerPoint" in d.label for d in at.get("download_button"))


def test_slideshow_bad_ai_output(monkeypatch):
    at = _go(_app(monkeypatch, "sorry, I can't"), "🎞️ Slideshow Maker")
    at.text_input(key="ss_topic").set_value("Energy").run()
    next(b for b in at.button if "Create slideshow" in b.label).click().run()
    assert not at.exception and at.error and not at.session_state.filtered_state.get("deck")


def test_tracker_add_and_send_to_timetable(monkeypatch):
    at = _go(_app(monkeypatch), "📅 Study Tracker")
    at.text_input[0].set_value("Lab report").run()
    next(b for b in at.button if "Add" in b.label).click().run()
    assert not at.exception and at.session_state["tr_items"][0]["Title"] == "Lab report"
    next(b for b in at.button if "Send open tasks" in b.label).click().run()
    assert at.session_state["_tt_tasks_saved"][0]["Title"] == "Lab report"
    _go(at, "🗓️ Timetable Maker")        # the timetable must accept the injected task
    assert not at.exception


def test_access_gate(monkeypatch):
    monkeypatch.setenv("ACCESS_CODE", "letmein")
    at = AppTest.from_file("app.py", default_timeout=60).run()
    assert not at.sidebar.radio and at.text_input[0].label == "Access code"
    at.text_input[0].set_value("nope").run()
    next(b for b in at.button if b.label == "Unlock").click().run()
    assert at.error and not at.sidebar.radio
    for _ in range(guard.MAX_FAILS):
        at.text_input[0].set_value("nope").run()
        next(b for b in at.button if b.label == "Unlock").click().run()
    at.text_input[0].set_value("letmein").run()                      # locked out: even the right code waits
    next(b for b in at.button if b.label == "Unlock").click().run()
    assert "Too many attempts" in at.error[0].value and not at.sidebar.radio
    at.session_state["_lock_until"] = 0
    at.text_input[0].set_value("letmein").run()
    next(b for b in at.button if b.label == "Unlock").click().run()
    assert at.sidebar.radio and at.session_state["_auth_ok"] is True
    assert "letmein" not in json.dumps({k: str(v) for k, v in at.session_state.filtered_state.items()})


def test_real_run_crew_respects_limits(monkeypatch):
    """Uses the real run_crew: the cap must trigger before any network call is made."""
    pytest.importorskip("crewai")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_testtesttesttesttest")
    monkeypatch.setenv("SESSION_LIMIT", "0")
    monkeypatch.setenv("DAILY_LIMIT", "1")
    guard._store.clear()
    guard._store()["day"], guard._store()["count"] = guard.date.today().isoformat(), 1
    at = AppTest.from_file("app.py", default_timeout=60).run()
    at.sidebar.radio[0].set_value("✉️ Email Writer").run()
    at.text_area[0].set_value("Ask for an extension").run()
    next(b for b in at.button if "Generate emails" in b.label).click().run()
    assert any("quota is used up" in e.value for e in at.error), [e.value for e in at.error]
    guard._store.clear()
