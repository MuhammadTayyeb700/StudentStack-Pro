"""Workspace backup: export/restore your work as one JSON file.
Privacy: the API key, uploaded files and indexed documents are NEVER included."""
from __future__ import annotations

import json
from datetime import datetime, timezone

APP = "student-stack-pro"
VERSION = 1
MAX_BYTES = 8 * 1024 * 1024
# session-state key -> expected python type
PLAIN = {"research_out": dict, "rag_notes": str, "rag_cards": list, "rag_chat": list, "slide_out": dict,
         "tt": dict, "emails": list, "li_posts": list, "li_meta": (list, tuple), "resume": dict,
         "_saved_doc_text": str, "_saved_doc_title": str, "_tt_fixed_saved": list, "_tt_tasks_saved": list,
         "essay_fb": dict, "_essay_text_saved": str, "_essay_prompt_saved": str, "cover_letter": str, "deck": dict,
         "tr_items": list, "gpa_rows": list}
LABELS = {"resume": "Resume", "_saved_doc_text": "Writer's Desk document", "research_out": "Research report",
          "rag_notes": "PDF notes", "rag_cards": "Flashcards", "rag_chat": "PDF chat", "slide_out": "Slide notes",
          "tt": "Timetable", "emails": "Emails", "li_posts": "LinkedIn posts", "essay_fb": "Essay feedback",
          "_essay_text_saved": "Essay draft", "cover_letter": "Cover letter", "deck": "Slideshow",
          "tr_items": "Deadlines", "gpa_rows": "GPA courses"}


def collect(state) -> dict:
    data = {}
    for key, typ in PLAIN.items():
        val = state.get(key)
        if val and isinstance(val, typ):
            data[key] = val
    return data


def to_json(state) -> str:
    payload = dict(app=APP, version=VERSION, created=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   data=collect(state))
    return json.dumps(payload, ensure_ascii=False, indent=1, default=str)


def parse(raw: bytes) -> dict:
    """Validate an uploaded backup; returns only whitelisted keys of the right type. Raises ValueError."""
    if len(raw) > MAX_BYTES:
        raise ValueError("Backup file is too large.")
    try:
        obj = json.loads(raw.decode("utf-8"))
    except Exception:  # noqa: BLE001
        raise ValueError("This isn't a valid backup file.") from None
    if not isinstance(obj, dict) or obj.get("app") != APP or not isinstance(obj.get("data"), dict):
        raise ValueError("This file wasn't created by Student Stack Pro.")
    if int(obj.get("version", 0)) > VERSION:
        raise ValueError("Backup was made by a newer version of the app.")
    out = {}
    for key, typ in PLAIN.items():
        val = obj["data"].get(key)
        if val and isinstance(val, typ):
            out[key] = val
    if not out:
        raise ValueError("The backup contains no data.")
    return out


def apply(state, data: dict) -> list[str]:
    """Write validated data into session state. Call BEFORE widgets are created in the current run."""
    restored = []
    for key, val in data.items():
        if key == "resume":
            from modules import resume as rs
            state["resume_pending"] = rs._with_ids(rs._coerce(val))
        elif key == "_saved_doc_text":
            state[key] = val
            state["doc_text"] = val
        elif key == "_saved_doc_title":
            state[key] = val
            state["doc_title"] = val
        elif key in ("_tt_fixed_saved", "_tt_tasks_saved"):
            state[key] = val
            for k in ("tt_fixed", "tt_tasks", "_tt_fixed_init", "_tt_tasks_init"):
                state.pop(k, None)
        elif key in ("_essay_text_saved", "_essay_prompt_saved"):
            state[key] = val
            state["es_text" if key == "_essay_text_saved" else "es_prompt"] = val
        elif key == "cover_letter":
            state[key] = val
            state.pop("cl_edit", None)
        elif key == "deck":
            state[key] = val
            state["deck_ver"] = state.get("deck_ver", 0) + 1
        elif key in ("tr_items", "gpa_rows"):
            state[key] = val
            for k in (("tr_editor", "_tr_init") if key == "tr_items" else ("gpa_editor", "_gpa_init")):
                state.pop(k, None)
        else:
            state[key] = val
        if key in LABELS:
            restored.append(LABELS[key])
    return restored


def sidebar_backup() -> None:
    import streamlit as st
    with st.sidebar.expander("💾 Save / restore my work"):
        has = bool(collect(st.session_state))
        st.download_button("⬇️ Download workspace backup", to_json(st.session_state), "student_stack_pro_backup.json",
                           "application/json", disabled=not has, use_container_width=True)
        st.caption("Includes your documents, resume, notes, cards and timetable. Never your API key or uploaded files.")
        up = st.file_uploader("Restore from backup (.json)", type=["json"], key="backup_file")
        if up is not None and st.button("♻️ Restore", use_container_width=True):
            try:
                restored = apply(st.session_state, parse(up.getvalue()))
                st.session_state["_restore_msg"] = "Restored: " + (", ".join(restored) or "workspace") + " ✅"
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
        msg = st.session_state.pop("_restore_msg", None)
        if msg:
            st.success(msg)
