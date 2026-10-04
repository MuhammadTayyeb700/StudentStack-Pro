"""Tests for core.codegen - offline, no API key needed."""
import io
import zipfile

from core.codegen import (build_prompt, clamp, ext_of, inline_assets, lang_for, make_zip, run_kind, valid_name,
                          ace_mode)


def test_build_prompt_fence_rule():
    for mode in ("Generate", "Edit", "Fix / Debug", "Refactor", "Add tests", "Add comments"):
        p = build_prompt(mode, "Python", "hello world", code="x=1")
        assert "ONLY one fenced code block" in p, mode


def test_explain_prompt_allows_prose():
    assert "ONLY one fenced" not in build_prompt("Explain", "Python", "", code="x=1")


def test_clamp_trims():
    assert len(clamp("a" * 10000, max_chars=100)) == 100
    assert clamp("short") == "short"


def test_file_types():
    assert ext_of("a.PY") == ".py" and ext_of("Makefile") == ""
    assert lang_for("x.py") == "Python" and lang_for("x.unknown") == "Text"
    assert ace_mode("a.cpp") == "c_cpp"
    assert run_kind("a.py") == "python" and run_kind("a.js") == "javascript" and run_kind("a.html") is None


def test_valid_name():
    files = {"main.py": ""}
    assert valid_name("utils.py", files) is None
    assert valid_name("main.py", files)          # duplicate
    assert valid_name("../evil.py", files)       # path traversal
    assert valid_name("a/b.py", files)           # no folders
    assert valid_name("noext", files)            # unsupported type
    assert valid_name("x.exe", files)
    assert valid_name("f.py", {f"{i}.py": "" for i in range(12)})  # file cap


def test_zip_roundtrip():
    z = zipfile.ZipFile(io.BytesIO(make_zip({"a.py": "print(1)", "b.js": "1"})))
    assert sorted(z.namelist()) == ["a.py", "b.js"] and z.read("a.py") == b"print(1)"


def test_inline_assets():
    html = '<link rel="stylesheet" href="s.css"><script src="a.js"></script><script src="https://x/y.js"></script>'
    out = inline_assets(html, {"s.css": "p{}", "a.js": "go()"})
    assert "<style>p{}</style>" in out and "<script>go()</script>" in out and "https://x/y.js" in out
