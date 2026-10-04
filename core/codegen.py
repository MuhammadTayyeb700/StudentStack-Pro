"""Code Studio helpers - pure functions, no Streamlit imports (unit-testable).

Code is never executed on the server: Python/JS run inside the visitor's browser
(see static/ide_runner), so a public deployment cannot leak secrets through it."""
from __future__ import annotations

import io
import re
import zipfile

# extension -> (display language, ace editor mode)
EXT = {
    ".py": ("Python", "python"),
    ".js": ("JavaScript", "javascript"),
    ".html": ("HTML", "html"),
    ".css": ("CSS", "css"),
    ".json": ("JSON", "json"),
    ".md": ("Markdown", "markdown"),
    ".txt": ("Text", "text"),
    ".cpp": ("C++", "c_cpp"),
    ".sql": ("SQL", "sql"),
}
RUNNABLE = {".py": "python", ".js": "javascript"}
MODES = ["Generate", "Edit", "Explain", "Fix / Debug", "Refactor", "Add tests", "Add comments"]
REPLACE_MODES = {"Generate", "Edit", "Fix / Debug", "Refactor", "Add comments"}
MAX_FILES = 12
STARTER = {"main.py": '# Welcome to Code Studio - press Run (Ctrl+Enter)\nname = input("Your name? ") or "world"\nprint(f"Hello, {name}!")\n'}

_FENCE_RULE = "Return ONLY one fenced code block, no prose."
_NAME_RE = re.compile(r"^[A-Za-z0-9_][\w .-]{0,40}$")


# ------------------------------------------------------------------ files
def ext_of(name: str) -> str:
    i = name.rfind(".")
    return name[i:].lower() if i > 0 else ""


def lang_for(name: str) -> str:
    return EXT.get(ext_of(name), ("Text", "text"))[0]


def ace_mode(name: str) -> str:
    return EXT.get(ext_of(name), ("Text", "text"))[1]


def run_kind(name: str) -> str | None:
    """'python' / 'javascript' if the file can run in the browser runner, else None."""
    return RUNNABLE.get(ext_of(name))


def valid_name(name: str, existing: dict | None = None) -> str | None:
    """Return an error message, or None if *name* is a usable new file name."""
    name = (name or "").strip()
    if not _NAME_RE.match(name) or ".." in name:
        return "Use letters, numbers, _ . - only (max 40 characters)."
    if ext_of(name) not in EXT:
        return "Supported types: " + ", ".join(EXT)
    if existing is not None and name in existing:
        return "A file with that name already exists."
    if existing is not None and len(existing) >= MAX_FILES:
        return f"Maximum {MAX_FILES} files."
    return None


def make_zip(files: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for n, c in files.items():
            z.writestr(n, c)
    return buf.getvalue()


def inline_assets(html: str, files: dict) -> str:
    """Inline <link href=x.css> and <script src=x.js> from the workspace so HTML previews work."""
    def css(m):
        n = m.group(1)
        return f"<style>{files[n]}</style>" if n in files else m.group(0)

    def js(m):
        n = m.group(1)
        return f"<script>{files[n]}</script>" if n in files else m.group(0)

    html = re.sub(r"""<link[^>]*href=["']([^"']+\.css)["'][^>]*>""", css, html, flags=re.I)
    return re.sub(r"""<script[^>]*src=["']([^"']+\.js)["'][^>]*>\s*</script>""", js, html, flags=re.I)


# ------------------------------------------------------------------ prompts
def build_prompt(mode: str, lang: str, request: str, code: str = "", selection: str = "") -> str:
    """Build the prompt for the chosen mode (only the needed code is sent, to save tokens)."""
    target = selection or code
    base = f"Language: {lang}.\n{_FENCE_RULE}\n"
    if mode == "Generate":
        return base + f"Write code for: {request}"
    if mode == "Edit":
        return base + f"Apply this change and return the full updated code: {request}\n```\n{target}\n```"
    if mode == "Explain":
        return (f"Language: {lang}.\nExplain this code concisely in plain Markdown "
                f"(do not repeat the code):\n```\n{target}\n```")
    if mode == "Fix / Debug":
        return base + f"Fix/debug this code. Error context: {request}\n```\n{target}\n```"
    if mode == "Refactor":
        return base + f"Refactor this code for clarity and efficiency:\n```\n{target}\n```"
    if mode == "Add tests":
        return (f"Language: {lang}.\nWrite unit tests for this code. "
                f"Return ONLY one fenced code block with the tests.\n```\n{target}\n```")
    if mode == "Add comments":
        return base + f"Add clear comments to this code and return the full code:\n```\n{target}\n```"
    return base + request


def clamp(code: str, max_chars: int = 8000) -> str:
    """Trim code to *max_chars* to keep LLM context manageable."""
    return code[:max_chars]
