"""Code Studio helpers — pure functions, no Streamlit imports (unit-testable)."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from typing import Tuple

LANGS = {
    "Python": ".py",
    "JavaScript": ".js",
    "HTML/CSS/JS": ".html",
    "C++": ".cpp",
    "SQL": ".sql",
}

MODES = [
    "Generate",
    "Explain",
    "Fix / Debug",
    "Refactor",
    "Add tests",
    "Add comments",
]

_FENCE_RULE = "Return ONLY one fenced code block, no prose."

# Patterns that must never appear in user code before execution.
_SECRET_PATTERNS = re.compile(
    r"st\.secrets|os\.environ|os\.getenv|GROQ|API_KEY|subprocess|importlib",
    re.IGNORECASE,
)


def build_prompt(mode: str, lang: str, request: str,
                 code: str = "", selection: str = "") -> str:
    """Build the system+user prompt for the chosen mode."""
    target = selection or code
    base = f"Language: {lang}.\n{_FENCE_RULE}\n"
    if mode == "Generate":
        return base + f"Write code for: {request}"
    if mode == "Explain":
        return base + f"Explain this code concisely:\n```\n{target}\n```"
    if mode == "Fix / Debug":
        return base + f"Fix/debug this code. Error context: {request}\n```\n{target}\n```"
    if mode == "Refactor":
        return base + f"Refactor this code for clarity and efficiency:\n```\n{target}\n```"
    if mode == "Add tests":
        return base + f"Write unit tests for this code:\n```\n{target}\n```"
    if mode == "Add comments":
        return base + f"Add clear comments to this code:\n```\n{target}\n```"
    return base + request


def clamp(code: str, max_chars: int = 8000) -> str:
    """Trim code to *max_chars* to keep LLM context manageable."""
    return code[:max_chars]


def trim_history(msgs: list[dict], keep: int = 4) -> list[dict]:
    """Keep only the last *keep* messages to cap context."""
    return msgs[-keep:] if len(msgs) > keep else list(msgs)


# ------------------------------------------------------------------ execution
_MAX_OUTPUT = 10_240  # 10 KB


def _check_forbidden(code: str) -> str | None:
    """Return a rejection reason if the code tries to access secrets/env."""
    m = _SECRET_PATTERNS.search(code)
    if m:
        return (f"Blocked: code contains '{m.group()}' which could access "
                "secrets or spawn processes. Remove it and try again.")
    return None


def run_python(code: str, timeout: int = 5) -> Tuple[str, str, int]:
    """Execute *code* in an isolated subprocess. Returns (stdout, stderr, exit_code).

    Security: scrubbed env (only PATH), no network-credential leak,
    resource limits (where OS supports it), temp dir cleaned up.
    """
    reason = _check_forbidden(code)
    if reason:
        return ("", reason, 1)

    tmp = tempfile.mkdtemp(prefix="codestudio_")
    script = os.path.join(tmp, "run.py")
    try:
        with open(script, "w", encoding="utf-8") as f:
            f.write(code)

        # Scrubbed environment: only PATH, no secrets.
        safe_env = {"PATH": os.environ.get("PATH", "")}

        # Build preexec_fn for resource limits (Unix only).
        preexec = None
        if sys.platform != "win32":
            def _limits():  # noqa: ANN202
                import resource  # noqa: PLC0415
                # CPU: 5 seconds hard limit
                resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
                # Memory: ~256 MB
                resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
                # No fork bombs
                try:
                    resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
                except (ValueError, AttributeError):
                    pass
            preexec = _limits

        result = subprocess.run(
            [sys.executable, "-I", "-S", script],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=tmp,
            env=safe_env,
            preexec_fn=preexec,
        )
        stdout = result.stdout[:_MAX_OUTPUT]
        stderr = result.stderr[:_MAX_OUTPUT]
        return (stdout, stderr, result.returncode)
    except subprocess.TimeoutExpired:
        return ("", "Execution timed out (limit: {} s).".format(timeout), 1)
    except Exception as exc:  # noqa: BLE001
        return ("", f"Runner error: {exc}", 1)
    finally:
        # Clean up temp dir.
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
