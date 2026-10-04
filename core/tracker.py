"""Pure helpers for the Study Tracker: deadlines, urgency, .ics export, GPA maths."""
from __future__ import annotations

import math
import uuid
from datetime import date, datetime, timedelta, timezone

PRIORITIES = ["High", "Medium", "Low"]
_RANK = {p: i for i, p in enumerate(PRIORITIES)}
GRADES = {"A+": 4.0, "A": 4.0, "A-": 3.7, "B+": 3.3, "B": 3.0, "B-": 2.7, "C+": 2.3, "C": 2.0, "C-": 1.7,
          "D+": 1.3, "D": 1.0, "F": 0.0}


# ------------------------------------------------------------------ values
def norm_date(v) -> str:
    """Any date-like value -> 'YYYY-MM-DD', or '' when it isn't a usable date."""
    try:
        if v is None or v != v or v == "":
            return ""
    except Exception:  # noqa: BLE001
        return ""
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    s = str(v).strip()
    if not s or s.lower() in ("nat", "nan", "none"):
        return ""
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        pass
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%b %d %Y", "%d %b %Y", "%B %d %Y", "%d %B %Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return ""


def _num(v, default: float, lo: float, hi: float) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return default
    return default if math.isnan(x) else max(lo, min(hi, x))


def _bool(v) -> bool:
    return v is True or str(v).strip().lower() in ("true", "1", "yes")


def _txt(v, limit: int = 120) -> str:
    return "" if v is None or v != v else str(v).strip()[:limit]


def clean_items(rows) -> list[dict]:
    """Sanitise table rows (also used on restored backups). Rows without a title are dropped."""
    out = []
    for r in rows or []:
        if not isinstance(r, dict) or not _txt(r.get("Title")):
            continue
        prio = _txt(r.get("Priority"))
        out.append(dict(Done=_bool(r.get("Done")), Title=_txt(r.get("Title")), Course=_txt(r.get("Course"), 60),
                        Due=norm_date(r.get("Due")), Hours=round(_num(r.get("Hours"), 1.0, 0.0, 200.0), 2),
                        Priority=prio if prio in PRIORITIES else "Medium"))
    return out[:300]


# ------------------------------------------------------------------ deadlines
def days_left(due: str, today: date) -> int | None:
    d = norm_date(due)
    return (date.fromisoformat(d) - today).days if d else None


def urgency(item: dict, today: date) -> tuple[str, str]:
    """(label, colour) for a deadline card."""
    if item.get("Done"):
        return "Done", "#10b981"
    n = days_left(item.get("Due", ""), today)
    if n is None:
        return "No date", "#94a3b8"
    if n < 0:
        return f"Overdue by {-n} day{'s' if n != -1 else ''}", "#ef4444"
    if n == 0:
        return "Due today", "#ef4444"
    if n == 1:
        return "Due tomorrow", "#f97316"
    return f"{n} days left", "#f59e0b" if n <= 7 else "#10b981"


def sort_items(items: list[dict], today: date) -> list[dict]:
    def key(it):
        n = days_left(it.get("Due", ""), today)
        return (bool(it.get("Done")), n is None, n if n is not None else 0, _RANK.get(it.get("Priority"), 1))
    return sorted(items, key=key)


def summary(items: list[dict], today: date) -> dict:
    open_ = [i for i in items if not i.get("Done")]
    left = [days_left(i.get("Due", ""), today) for i in open_]
    return dict(total=len(items), open=len(open_), done=len(items) - len(open_),
                overdue=sum(1 for n in left if n is not None and n < 0),
                week=sum(1 for n in left if n is not None and 0 <= n <= 7),
                hours=round(sum(float(i.get("Hours") or 0) for i in open_), 1))


def auto_priority(due: str, today: date) -> str:
    n = days_left(due, today)
    return "Medium" if n is None else "High" if n <= 2 else "Medium" if n <= 7 else "Low"


def to_timetable_tasks(items: list[dict], today: date) -> list[dict]:
    """Open items -> rows for the Timetable Maker task table (urgency can raise, never lower, priority)."""
    out = []
    for it in sort_items([i for i in items if not i.get("Done")], today):
        hrs = float(it.get("Hours") or 0)
        if hrs <= 0:
            continue
        prio = min(it.get("Priority", "Medium"), auto_priority(it.get("Due", ""), today),
                   key=lambda p: _RANK.get(p, 1)) if it.get("Due") else it.get("Priority", "Medium")
        title = f"{it['Title']} ({it['Course']})" if it.get("Course") else it["Title"]
        out.append(dict(Title=title, Hours=hrs, Priority=prio, Session=60))
    return out


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def ics_deadlines(items: list[dict]) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//StudentStackPro//Deadlines//EN", "CALSCALE:GREGORIAN"]
    for it in items:
        d = norm_date(it.get("Due"))
        if not d or it.get("Done"):
            continue
        start = date.fromisoformat(d)
        name = f"Due: {it['Title']}" + (f" ({it['Course']})" if it.get("Course") else "")
        lines += ["BEGIN:VEVENT", f"UID:{uuid.uuid4()}@studentstackpro", f"DTSTAMP:{stamp}",
                  f"DTSTART;VALUE=DATE:{start:%Y%m%d}", f"DTEND;VALUE=DATE:{start + timedelta(days=1):%Y%m%d}",
                  f"SUMMARY:{_esc(name)}", "BEGIN:VALARM", "TRIGGER:-P1D", "ACTION:DISPLAY",
                  f"DESCRIPTION:{_esc(name)} is due tomorrow", "END:VALARM", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


# ------------------------------------------------------------------ GPA (4.0 scale)
def gpa(rows) -> tuple[float | None, float]:
    """(GPA, total credits) over rows with a valid grade and positive credits."""
    pts = cr = 0.0
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        grade = _txt(r.get("Grade")).upper()
        c = _num(r.get("Credits"), 0.0, 0.0, 60.0)
        if grade in GRADES and c > 0:
            pts += GRADES[grade] * c
            cr += c
    return (round(pts / cr, 2) if cr else None), cr


def required_gpa(current_gpa: float, current_credits: float, target: float, new_credits: float) -> float | None:
    """Average GPA needed over `new_credits` to reach `target` overall (may be <0 or >4)."""
    if new_credits <= 0:
        return None
    return (target * (current_credits + new_credits) - current_gpa * current_credits) / new_credits
