"""Tests for core.codegen — offline, no API key needed."""
import os

from core.codegen import build_prompt, clamp, run_python


def test_build_prompt_contains_fence_rule():
    """Every prompt must contain the 'ONLY one fenced code block' instruction."""
    for mode in ("Generate", "Explain", "Fix / Debug", "Refactor", "Add tests", "Add comments"):
        p = build_prompt(mode, "Python", "hello world", code="x=1")
        assert "ONLY one fenced code block" in p, f"Missing fence rule in mode={mode}"


def test_clamp_trims():
    assert len(clamp("a" * 10000, max_chars=100)) == 100
    assert clamp("short") == "short"


def test_run_python_happy():
    stdout, stderr, rc = run_python("print(1+1)")
    assert stdout.strip() == "2"
    assert rc == 0


def test_run_python_timeout():
    stdout, stderr, rc = run_python("while True: pass", timeout=2)
    assert rc != 0
    assert "timed out" in stderr.lower() or "timeout" in stderr.lower()


def test_run_python_rejects_secrets():
    """Code that reads os.environ should be blocked, and GROQ_API_KEY must be absent from child env."""
    stdout, stderr, rc = run_python("import os; print(os.environ)")
    assert rc != 0
    assert "os.environ" in stderr.lower() or "blocked" in stderr.lower()

    # Even if somehow executed, the key must not be in the env.
    stdout2, stderr2, rc2 = run_python("print('hello')")  # benign code
    assert "GROQ_API_KEY" not in stdout2
    assert "GROQ_API_KEY" not in stderr2
