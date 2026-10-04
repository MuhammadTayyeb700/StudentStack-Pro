"""Run: python scripts/check_env.py  -> verifies every dependency imports."""
import importlib
import sys
from importlib import metadata

PKGS = ["crewai", "streamlit", "pypdf", "python-pptx", "python-docx",
        "reportlab", "scikit-learn", "pandas"]
MODS = ["crewai", "streamlit", "pypdf", "pptx", "docx", "reportlab", "sklearn", "pandas"]

print(f"Python {sys.version.split()[0]}")
bad = 0
for pkg, mod in zip(PKGS, MODS):
    try:
        importlib.import_module(mod)
        print(f"  OK   {pkg:<14} {metadata.version(pkg)}")
    except Exception as exc:  # noqa: BLE001
        bad += 1
        print(f"  FAIL {pkg:<14} {exc}")
try:
    from crewai import LLM, Agent, Crew, Process, Task  # noqa: F401
    print("  OK   crewai API (Agent, Task, Crew, Process, LLM)")
except Exception as exc:  # noqa: BLE001
    bad += 1
    print(f"  FAIL crewai API: {exc}")
sys.exit(1 if bad else 0)
