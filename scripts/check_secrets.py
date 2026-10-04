"""Run: python scripts/check_secrets.py -> fails if a real-looking Groq key is in the repo."""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PATTERN = re.compile(r"gsk_[A-Za-z0-9]{20,}")
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache"}
ALLOW = {"gsk_SECRET123456789", "gsk_abcdefghij1234567890", "gsk_testtesttesttesttest"}  # fake test values  # fake value used in tests

bad = []
for path in ROOT.rglob("*"):
    if path.is_dir() or SKIP_DIRS & set(path.parts):
        continue
    if path.name in {".env", "secrets.toml"}:
        bad.append(f"{path.relative_to(ROOT)}: real secrets file present (must stay out of git/Docker)")
        continue
    try:
        text = path.read_text(errors="ignore")
    except OSError:
        continue
    for m in PATTERN.findall(text):
        if m not in ALLOW:
            bad.append(f"{path.relative_to(ROOT)}: looks like an API key")
print("\n".join(bad) or "No secrets found.")
sys.exit(1 if bad else 0)
