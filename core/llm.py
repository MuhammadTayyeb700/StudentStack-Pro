"""Groq + CrewAI plumbing. The API key comes ONLY from server secrets (never typed in the UI),
and is never shown, logged, stored on disk or put in os.environ."""
from __future__ import annotations

import json
import os
import re
import time
from typing import Any

import streamlit as st

from core import guard

# Privacy: switch off CrewAI telemetry/tracing before crewai is ever imported.
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")

MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
]
CUSTOM = "Custom…"


class LLMError(RuntimeError):
    """Friendly, key-free error message safe to show to the user."""


# ------------------------------------------------------------------ keys
def _server_key() -> str:
    """Key from Streamlit secrets or the environment. There is no key field in the UI."""
    try:
        val = st.secrets.get("GROQ_API_KEY", "")
    except Exception:  # no secrets file
        val = ""
    return str(val or os.getenv("GROQ_API_KEY", "")).strip()


def get_api_key() -> str:
    return _server_key()


def scrub(msg: Any) -> str:
    text = str(msg)
    key = _server_key()
    if key:
        text = text.replace(key, "[hidden]")
    return re.sub(r"gsk_[A-Za-z0-9]{10,}", "[hidden]", text)


def current_model() -> str:
    choice = st.session_state.get("model_choice", MODELS[0])
    if choice == CUSTOM:
        choice = (st.session_state.get("custom_model") or "").strip() or MODELS[0]
    return choice.removeprefix("groq/")


def make_llm(temperature: float | None = None, max_tokens: int = 3000):
    key = get_api_key()
    if not key:
        raise LLMError("AI features are not configured yet: the app owner must add GROQ_API_KEY "
                       "to the server secrets.")
    try:
        from crewai import LLM
    except Exception as exc:  # noqa: BLE001
        raise LLMError(f"CrewAI is not installed correctly: {scrub(exc)}") from None
    temp = st.session_state.get("temperature", 0.4) if temperature is None else temperature
    return LLM(model=f"groq/{current_model()}", api_key=key, temperature=float(temp), max_tokens=max_tokens)


def sidebar_settings() -> None:
    with st.sidebar.expander("⚙️ AI settings", expanded=False):
        st.selectbox("Model", MODELS + [CUSTOM], key="model_choice")
        if st.session_state.get("model_choice") == CUSTOM:
            st.text_input("Custom model id", key="custom_model", placeholder="e.g. llama-3.3-70b-versatile")
        st.slider("Creativity", 0.0, 1.0, 0.4, 0.05, key="temperature")
        if st.button("Test connection", use_container_width=True):
            try:
                llm_ = make_llm(max_tokens=20)
                guard.consume_request()
                llm_.call("Reply with the single word OK.")
                st.success("Connected ✅")
            except (LLMError, guard.LimitReached) as exc:
                st.error(str(exc))
            except Exception as exc:  # noqa: BLE001
                st.error(_friendly(scrub(exc)))
        st.caption(guard.usage_caption())
        st.caption(f"AI: {'ready' if _server_key() else 'not configured'} · model `{current_model()}`")


# ------------------------------------------------------------------ errors
def _friendly(msg: str) -> str:
    low = msg.lower()
    if "401" in low or "invalid api key" in low or "authentication" in low:
        return "Groq rejected the server's API key. The app owner needs to update it."
    if "429" in low or "rate limit" in low or "rate_limit" in low:
        return "Groq rate limit reached. Wait a minute, pick a smaller model, or reduce the input size."
    if "413" in low or "too large" in low or "context length" in low or "maximum context" in low:
        return "The input is too large for this model. Use a shorter document or lower 'Max characters'."
    if "model" in low and ("not found" in low or "decommissioned" in low or "does not exist" in low):
        return "That model isn't available on Groq any more. Choose another one in AI settings."
    return f"AI request failed: {msg[:300]}"


# ------------------------------------------------------------------ crew runner
def run_crew(steps: list[dict], temperature: float | None = None, max_tokens: int = 3000) -> str:
    """Run agents sequentially. Each step: role, goal, backstory, task, expected."""
    llm = make_llm(temperature, max_tokens)
    try:
        guard.consume_request()
    except guard.LimitReached as exc:
        raise LLMError(str(exc)) from None
    try:
        from crewai import Agent, Crew, Process, Task
    except Exception as exc:  # noqa: BLE001
        raise LLMError(f"CrewAI is not installed correctly: {scrub(exc)}") from None

    for attempt in range(4):
        try:
            agents, tasks = [], []
            for s in steps:
                agent = Agent(role=s["role"], goal=s["goal"], backstory=s["backstory"], llm=llm,
                              allow_delegation=False, verbose=False)
                agents.append(agent)
                tasks.append(Task(description=s["task"], expected_output=s["expected"], agent=agent))
            crew = Crew(agents=agents, tasks=tasks, process=Process.sequential, verbose=False)
            result = crew.kickoff()
            text = (getattr(result, "raw", None) or str(result)).strip()
            if not text:
                raise LLMError("The model returned an empty answer. Please try again.")
            return text
        except LLMError:
            raise
        except Exception as exc:  # noqa: BLE001
            msg = scrub(exc)
            transient = any(k in msg.lower() for k in ("429", "rate limit", "rate_limit", "timeout", "503"))
            if transient and attempt < 3:
                time.sleep(10 * (attempt + 1))
                continue
            raise LLMError(_friendly(msg)) from None
    raise LLMError("The AI service is busy. Please try again shortly.")


def single(role: str, goal: str, backstory: str, task: str, expected: str,
           temperature: float | None = None, max_tokens: int = 3000) -> str:
    return run_crew([dict(role=role, goal=goal, backstory=backstory, task=task, expected=expected)],
                    temperature, max_tokens)


def strip_fences(text: str) -> str:
    t = text.strip()
    t = re.sub(r"^```[a-zA-Z]*\s*\n?", "", t)
    t = re.sub(r"\n?```\s*$", "", t)
    return t.strip()


def extract_json(text: str) -> Any:
    t = strip_fences(text)
    try:
        return json.loads(t)
    except Exception:  # noqa: BLE001
        pass
    for open_c, close_c in (("{", "}"), ("[", "]")):
        a, b = t.find(open_c), t.rfind(close_c)
        if a != -1 and b > a:
            try:
                return json.loads(t[a:b + 1])
            except Exception:  # noqa: BLE001
                continue
    raise LLMError("The AI answer was not in the expected format. Please click generate again.")


def safe_run(fn, *args, **kwargs):
    """Call fn and show a friendly Streamlit error instead of crashing. Returns None on failure."""
    try:
        return fn(*args, **kwargs)
    except LLMError as exc:
        st.error(str(exc))
    except Exception as exc:  # noqa: BLE001
        st.error(_friendly(scrub(exc)))
    return None
