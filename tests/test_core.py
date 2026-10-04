import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import resume_render as rr  # noqa: E402
from core import scheduler as sc  # noqa: E402
from core import textcheck as tc  # noqa: E402
from core import utils  # noqa: E402

SAMPLE = dict(name="Ada Lovelace", title="Engineer", email="a@b.com", phone="123", location="Lahore",
              links="github.com/ada\nlinkedin.com/in/ada", summary="Builder of things.",
              skills="Languages: Python, C++\nTools: Git", certifications="AWS CCP",
              experience=[dict(role="Dev", company="X", location="Y", start="2023", end="Present",
                               bullets="- Built A\n- Shipped B")],
              education=[dict(degree="BSc CE", school="Example Univ", location="City", year="2026", details="")],
              projects=[dict(name="Proj", link="gh/p", bullets="Did it")])


def test_to_min():
    assert sc.to_min("9:30") == 570 and sc.to_min("09:00 PM") == 1260 and sc.to_min("12am") == 0
    assert sc.to_min("25:00") is None and sc.to_min("abc") is None and sc.to_min(None) is None


def test_greedy_no_overlap():
    fixed = [dict(day="Mon", start=540, end=630, title="Class", cat="class")]
    tasks = [dict(title="A", minutes=240, priority="High", session=60),
             dict(title="B", minutes=120, priority="Low", session=60)]
    days = sc.DAYS[:5]
    new, unplaced = sc.greedy_schedule(fixed, tasks, days, 480, 1320, buffer=10)
    assert not unplaced and sum(b["end"] - b["start"] for b in new) == 360
    assert not sc.find_conflicts(fixed + new)
    assert "<table" in sc.grid_html(fixed + new, days, 480, 1320)
    assert sc.ics_text(fixed + new).count("BEGIN:VEVENT") == len(fixed + new)


def test_unplaced_when_full():
    tasks = [dict(title="Huge", minutes=6000, priority="High", session=60)]
    _, unplaced = sc.greedy_schedule([], tasks, ["Mon"], 480, 600, buffer=0)
    assert unplaced["Huge"] > 0


def test_validate_ai():
    tasks = [dict(title="Study", minutes=120, priority="High", session=60)]
    raw = [dict(day="Monday", start="10:00", end="11:00", title="study"),
           dict(day="Mon", start="10:30", end="11:30", title="Study"),   # overlap
           dict(day="Sun", start="10:00", end="11:00", title="Study"),   # day not allowed
           dict(day="Tue", start="23:00", end="23:50", title="Study")]   # outside window
    ok = sc.validate_ai_blocks(raw, [], tasks, ["Mon", "Tue"], 480, 1320)
    assert len(ok) == 1 and ok[0]["day"] == "Mon"


def test_textcheck():
    t = "this is is a very long text. It was written by me."
    kinds = {i["kind"] for i in tc.find_issues(t)}
    assert {"repeat", "weak", "case", "passive"} <= kinds
    assert tc.analyze(t)["words"] > 5
    assert "<ins>" in tc.diff_html("a b c", "a x c")
    assert "<mark" in tc.highlight_html(t, tc.find_issues(t))


def test_retriever_and_docx():
    chunks = utils.chunk_pages([(1, "Photosynthesis converts light into chemical energy in plants. " * 5),
                                (2, "The French Revolution began in 1789 with the storming of the Bastille. " * 5)])
    hit = utils.Retriever(chunks).search("when did the French Revolution begin", 1)
    assert hit and hit[0]["page"] == 2
    assert utils.md_to_docx("# T\n- **a** b\n1. x\nplain", "Doc")[:2] == b"PK"
    assert utils.group_by_chars(["aa", "bb", "cc"], 4) == [[0, 1], [2]]


def test_resume_outputs():
    for tpl in ("modern", "classic"):
        assert rr.to_pdf(SAMPLE, tpl, "#0ea5e9")[:4] == b"%PDF"
        assert "Ada Lovelace" in rr.to_html(SAMPLE, tpl)
    assert rr.to_docx(SAMPLE)[:2] == b"PK"
    assert rr.to_pdf(dict(name="X <&> Y"), "modern")[:4] == b"%PDF"   # escaping + sparse data


def test_pdf_exports():
    md = ("# Title\n\nSome **bold** and *italic* and `code` text — with “quotes” and emoji 😀 and Urdu اردو.\n\n"
          "- bullet one\n  - nested\n1. first\n> quote\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n```\nprint(1)\n```\n---\n- [ ] task\n"
          "Broken **markup *here\n")
    assert utils.md_to_pdf(md, "My <Doc> & more")[:4] == b"%PDF"
    assert utils.md_to_pdf("")[:4] == b"%PDF"
    cards = [dict(q=f"Question {i}?", a="Answer " * (60 if i == 3 else 3)) for i in range(11)]
    assert utils.flashcards_pdf(cards)[:4] == b"%PDF"
    assert utils.flashcards_pdf([])[:4] == b"%PDF"
    assert utils.flashcards_csv(cards).count("\n") == 11


def test_backup_roundtrip():
    from core import backup
    state = {"rag_notes": "notes", "emails": [dict(subject="s", body="b")], "user_key": "gsk_SECRET123456789",
             "_saved_doc_text": "hello", "junk": 1, "tt": {}}
    raw = backup.to_json(state)
    assert "gsk_" not in raw and "junk" not in raw
    data = backup.parse(raw.encode())
    assert data["rag_notes"] == "notes" and data["_saved_doc_text"] == "hello" and "tt" not in data
    for bad in (b"not json", b'{"app":"other","data":{}}', b'{"app":"student-stack-pro","version":1,"data":{"x":1}}'):
        try:
            backup.parse(bad)
            raise AssertionError("should fail")
        except ValueError:
            pass
    st_new: dict = {}
    assert "Writer's Desk document" in backup.apply(st_new, data)
    assert st_new["doc_text"] == "hello"


def test_scrub_hides_keys(monkeypatch):
    from core import llm
    monkeypatch.setenv("GROQ_API_KEY", "gsk_abcdefghij1234567890")
    out = llm.scrub("boom gsk_abcdefghij1234567890 and gsk_zzzzzzzzzzzzzzzz")
    assert "gsk_" not in out


def test_no_key_field_in_ui():
    import inspect
    from core import llm
    src = inspect.getsource(llm.sidebar_settings)
    assert "password" not in src and "user_key" not in src
