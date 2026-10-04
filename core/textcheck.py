"""Local, offline Grammarly-style checks (no AI needed)."""
from __future__ import annotations

import difflib
import html
import re

WEAK = r"\b(very|really|just|quite|actually|basically|literally|totally|simply|extremely|somewhat)\b"
CLICHES = ["at the end of the day", "think outside the box", "low-hanging fruit", "game changer",
           "paradigm shift", "synergy", "circle back", "touch base", "in today's fast-paced world",
           "it goes without saying", "needless to say", "last but not least"]
PASSIVE = r"\b(is|are|was|were|be|been|being)\s+(\w+ed|\w+en)\b"
REPEAT = r"\b(\w+)\s+\1\b"


def sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+|\n{2,}", text.strip()) if s.strip()]


def count_syllables(word: str) -> int:
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return 0
    n = len(re.findall(r"[aeiouy]+", w))
    if w.endswith("e") and not w.endswith("le") and n > 1:
        n -= 1
    return max(n, 1)


def analyze(text: str) -> dict:
    words = re.findall(r"[A-Za-z0-9’'-]+", text)
    sents = sentences(text)
    nw, ns = len(words), max(len(sents), 1)
    syl = sum(count_syllables(w) for w in words)
    if nw:
        flesch = 206.835 - 1.015 * (nw / ns) - 84.6 * (syl / nw)
        flesch = max(0.0, min(100.0, flesch))
    else:
        flesch = 0.0
    label = ("Very easy" if flesch >= 80 else "Easy" if flesch >= 65 else "Standard" if flesch >= 50
             else "Fairly hard" if flesch >= 30 else "Hard") if nw else "—"
    return dict(words=nw, chars=len(text), sentences=len(sents) if nw else 0,
                minutes=max(1, round(nw / 200)) if nw else 0, flesch=round(flesch), label=label)


def find_issues(text: str) -> list[dict]:
    issues: list[dict] = []

    def add(rx, kind, msg, flags=re.I):
        for m in re.finditer(rx, text, flags):
            issues.append(dict(start=m.start(), end=m.end(), kind=kind, msg=msg.format(m.group(0).strip())))

    add(REPEAT, "repeat", "Repeated word: “{}”")
    add(PASSIVE, "passive", "Possible passive voice: “{}”")
    add(WEAK, "weak", "Weak/filler word: “{}” — consider removing")
    for c in CLICHES:
        add(re.escape(c), "cliche", "Cliché: “{}”")
    for s in sentences(text):
        idx = text.find(s)
        if idx == -1:
            continue
        if len(s.split()) > 30:
            issues.append(dict(start=idx, end=idx + len(s), kind="long",
                               msg=f"Long sentence ({len(s.split())} words) — consider splitting"))
        if s[0].isalpha() and s[0].islower():
            issues.append(dict(start=idx, end=idx + 1, kind="case", msg="Sentence should start with a capital letter"))
    issues.sort(key=lambda d: (d["start"], d["end"]))
    return issues


def highlight_html(text: str, issues: list[dict]) -> str:
    out, pos = [], 0
    for it in issues:
        if it["start"] < pos:
            continue
        out.append(html.escape(text[pos:it["start"]]))
        out.append(f'<mark class="i-{it["kind"]}" title="{html.escape(it["msg"])}">'
                   f'{html.escape(text[it["start"]:it["end"]])}</mark>')
        pos = it["end"]
    out.append(html.escape(text[pos:]))
    return "".join(out)


def diff_html(old: str, new: str) -> str:
    a, b = re.findall(r"\s+|\S+", old), re.findall(r"\s+|\S+", new)
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == "equal":
            out.append(html.escape("".join(a[i1:i2])))
        else:
            if i2 > i1:
                out.append(f"<del>{html.escape(''.join(a[i1:i2]))}</del>")
            if j2 > j1:
                out.append(f"<ins>{html.escape(''.join(b[j1:j2]))}</ins>")
    return "".join(out)
