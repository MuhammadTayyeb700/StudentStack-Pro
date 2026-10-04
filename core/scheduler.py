"""Deterministic timetable engine (used directly, and as validator/fallback for the AI planner)."""
from __future__ import annotations

import html
import math
import re
import uuid
from datetime import date, datetime, timedelta, timezone

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
FULL = {d.lower(): d for d in DAYS}
FULL.update({n.lower(): d for n, d in zip(
    ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"], DAYS)})
PRIO = {"High": 0, "Medium": 1, "Low": 2}
COLORS = {"class": "#3b82f6", "High": "#ef4444", "Medium": "#f59e0b", "Low": "#10b981", "break": "#94a3b8"}


def to_min(v) -> int | None:
    if v is None:
        return None
    if hasattr(v, "hour") and hasattr(v, "minute"):
        return v.hour * 60 + v.minute
    s = str(v).strip().lower()
    m = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?(?::\d{2})?\s*(am|pm)?", s)
    if not m:
        return None
    h, mi, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3)
    if ap:
        if not 1 <= h <= 12:
            return None
        h = h % 12 + (12 if ap == "pm" else 0)
    if h > 23 or mi > 59:
        return None
    return h * 60 + mi


def fmt(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


def norm_day(v) -> str | None:
    return FULL.get(str(v).strip().lower())


def _ceil5(x: int) -> int:
    return -(-x // 5) * 5


def find_slot(day_blocks, length, ws, we, buffer, prefer="morning") -> int | None:
    busy = sorted((b["start"] - buffer, b["end"] + buffer) for b in day_blocks)
    merged: list[list[int]] = []
    for s, e in busy:
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    gaps, cur = [], ws
    for s, e in merged:
        if s > cur:
            gaps.append((cur, min(s, we)))
        cur = max(cur, e)
        if cur >= we:
            break
    if cur < we:
        gaps.append((cur, we))
    for gs, ge in (gaps if prefer == "morning" else reversed(gaps)):
        if prefer == "morning":
            s = _ceil5(gs)
            if s + length <= ge:
                return s
        else:
            s = (ge - length) // 5 * 5
            if s >= gs:
                return s
    return None


def greedy_schedule(existing, tasks, days, ws, we, buffer=10, prefer="morning"):
    """tasks: [{title, minutes, priority, session}] -> (new_blocks, {title: unplaced_minutes})."""
    blocks = list(existing)
    new: list[dict] = []
    queues = []
    for t in sorted(tasks, key=lambda x: (PRIO.get(x["priority"], 1), -x["minutes"])):
        sess, remaining, L = [], int(t["minutes"]), max(int(t.get("session", 60)), 20)
        while remaining > 0:
            part = min(L, remaining)
            if part < 20 and sess:
                sess[-1] += part
            else:
                sess.append(part)
            remaining -= part
        queues.append([t, sess])
    unplaced: dict[str, int] = {}
    while any(q[1] for q in queues):
        for t, sess in queues:
            if not sess:
                continue
            length = sess.pop(0)
            order = sorted(days, key=lambda d: (
                sum(1 for b in new if b["day"] == d and b["title"] == t["title"]),
                sum(b["end"] - b["start"] for b in blocks if b["day"] == d), days.index(d)))
            for d in order:
                s = find_slot([b for b in blocks if b["day"] == d], length, ws, we, buffer, prefer)
                if s is not None:
                    blk = dict(day=d, start=s, end=s + length, title=t["title"], cat=t["priority"])
                    blocks.append(blk)
                    new.append(blk)
                    break
            else:
                unplaced[t["title"]] = unplaced.get(t["title"], 0) + length
    return new, unplaced


def validate_ai_blocks(raw, existing, tasks, days, ws, we):
    """Keep only AI blocks that are valid, inside the window and conflict-free."""
    by_title = {t["title"].strip().lower(): t for t in tasks}
    accepted: list[dict] = []
    if not isinstance(raw, list):
        return accepted
    for it in raw:
        if not isinstance(it, dict):
            continue
        d, s, e = norm_day(it.get("day")), to_min(it.get("start")), to_min(it.get("end"))
        task = by_title.get(str(it.get("title", "")).strip().lower())
        if not (d and d in days and s is not None and e is not None and task) or e <= s or s < ws or e > we:
            continue
        if any(b["day"] == d and s < b["end"] and b["start"] < e for b in existing + accepted):
            continue
        accepted.append(dict(day=d, start=s, end=e, title=task["title"], cat=task["priority"]))
    return accepted


def remaining_tasks(tasks, placed):
    done: dict[str, int] = {}
    for b in placed:
        done[b["title"]] = done.get(b["title"], 0) + b["end"] - b["start"]
    out = []
    for t in tasks:
        left = int(t["minutes"]) - done.get(t["title"], 0)
        if left >= 20:
            out.append(dict(t, minutes=left))
    return out


def find_conflicts(blocks) -> list[str]:
    msgs = []
    for i, a in enumerate(blocks):
        for b in blocks[i + 1:]:
            if a["day"] == b["day"] and a["start"] < b["end"] and b["start"] < a["end"]:
                msgs.append(f'{a["day"]}: “{a["title"]}” overlaps “{b["title"]}”')
    return msgs


def grid_html(blocks, days, ws, we, step=30) -> str:
    for b in blocks:
        ws, we = min(ws, b["start"]), max(we, b["end"])
    ws = ws // step * step
    rows = list(range(ws, -(-we // step) * step, step))
    by_day = {d: sorted((b for b in blocks if b["day"] == d), key=lambda b: b["start"]) for d in days}
    skip = {d: 0 for d in days}
    css = ("<style>.tt{border-collapse:collapse;width:100%;font-size:.8rem;table-layout:fixed}"
           ".tt th{background:#4f46e5;color:#fff;padding:6px}.tt td{border:1px solid rgba(128,128,128,.25);"
           "height:26px;padding:2px 4px;vertical-align:top}.tt td.tm{width:52px;font-size:.7rem;opacity:.7;"
           "text-align:right}.tt td.b{color:#fff;border-radius:6px;font-weight:600;line-height:1.15}</style>")
    out = [css, "<div style='overflow-x:auto'><table class='tt' style='min-width:620px'><tr><th></th>" + "".join(f"<th>{d}</th>" for d in days) + "</tr>"]
    for ri, t in enumerate(rows):
        tr = [f"<td class='tm'>{fmt(t) if t % 60 == 0 else ''}</td>"]
        for d in days:
            if skip[d] > 0:
                skip[d] -= 1
                continue
            blk = next((x for x in by_day[d] if t <= x["start"] < t + step), None)
            if blk:
                span = max(1, min(math.ceil((blk["end"] - t) / step), len(rows) - ri))
                skip[d] = span - 1
                col = COLORS.get(blk["cat"], "#6366f1")
                tr.append(f"<td class='b' rowspan='{span}' style='background:{col}'>"
                          f"{html.escape(blk['title'])}<br><span style='font-weight:400;font-size:.68rem'>"
                          f"{fmt(blk['start'])}–{fmt(blk['end'])}</span></td>")
            else:
                tr.append("<td></td>")
        out.append("<tr>" + "".join(tr) + "</tr>")
    out.append("</table></div>")
    return "".join(out)


def _ics_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def ics_text(blocks, weeks: int = 16, today: date | None = None) -> str:
    today = today or date.today()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    codes = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//StudentStackPro//Timetable//EN", "CALSCALE:GREGORIAN"]
    for b in blocks:
        idx = DAYS.index(b["day"])
        first = today + timedelta(days=(idx - today.weekday()) % 7)
        ds = datetime.combine(first, datetime.min.time()) + timedelta(minutes=b["start"])
        de = datetime.combine(first, datetime.min.time()) + timedelta(minutes=b["end"])
        lines += ["BEGIN:VEVENT", f"UID:{uuid.uuid4()}@studentstackpro", f"DTSTAMP:{stamp}",
                  f"DTSTART:{ds:%Y%m%dT%H%M%S}", f"DTEND:{de:%Y%m%dT%H%M%S}",
                  f"RRULE:FREQ=WEEKLY;BYDAY={codes[idx]};COUNT={weeks}",
                  f"SUMMARY:{_ics_escape(b['title'])}", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
