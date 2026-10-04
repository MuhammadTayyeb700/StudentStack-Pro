# 🎓 Student Stack Pro

An all-in-one AI workspace built with **Python · CrewAI · Groq · Streamlit**.

| Tool | What it does |
|---|---|
| 🔎 Research Agents | 3-agent crew (Researcher → Reviewer → Writer): reports, summaries, briefings, study guides. Optional live web search. |
| ✉️ Email Writer | Writer + Proofreader agents, multiple options, tone/language control, “open in mail app”. |
| 💼 LinkedIn Posts | Strategist + Copywriter agents, hooks, hashtags, live post preview. |
| 📚 PDF Study Lab | RAG (TF-IDF retrieval) over PDFs: notes, flashcards (Anki export), Q&A with page citations. |
| 🖼️ Slide Reader | `.pptx`/PDF decks → slide-by-slide notes, summary, glossary, practice questions, cheat-sheet. |
| 🗓️ Timetable Maker | Deterministic clash-free scheduler + optional AI planner (AI output is validated), `.ics` + CSV export. |
| 📝 Writer's Desk | Markdown editor, offline Grammarly-style checks, readability score, AI rewrite with diff, `.docx` export. |
| 💌 Cover Letter | Paste a job ad → tailored letter built only from your Resume Studio facts; PDF / Word / text. |
| 🧾 Essay Feedback | Upload or paste an essay (+ optional rubric) → score out of 100, per-criterion marks, priority fixes, sentence suggestions. |
| 🎞️ Slideshow Maker | Topic (or your notes) → editable slides with speaker notes; present in the browser or download `.pptx` / `.html`. |
| 📅 Study Tracker | Deadlines with urgency colours, `.ics` export, one-click send to the Timetable Maker, focus timer, GPA calculator (no AI needed). |
| 📄 Resume Studio | Form → live preview → PDF / Word; AI polish, tailor to a job ad, import from pasted text. |
| 💻 Code Studio | AI code generator + mini IDE: generate, explain, fix, refactor in Python/JS/HTML/C++/SQL. |

Code Studio runs Python in an isolated subprocess with a scrubbed environment (no secrets, no `GROQ_API_KEY`), a 5-second timeout, and 256 MB memory cap. HTML/CSS/JS gets a sandboxed browser preview; other languages are edit/download only.

## 📥 Downloads
PDF, Word and Markdown for research, notes, slide notes and the editor · printable double-sided **flashcard PDF**, Quizlet CSV and Anki TSV · timetable CSV/.ics · resume PDF/Word ·
**💾 Workspace backup (JSON)** in the sidebar saves and restores your documents, resume, notes, cards and timetable. It never contains your API key or uploaded files.

## Run locally
```bash
git clone https://github.com/<you>/student-stack-pro.git && cd student-stack-pro
python3.11 -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python scripts/check_env.py          # confirms every package imports
streamlit run app.py
```
Get a free key at <https://console.groq.com> and put it in `.env` or `.streamlit/secrets.toml` (see the `.example` files). There is no key field in the app. Optional: `pip install -r requirements-optional.txt` for web search.

## 🔒 API-key privacy
* **There is no key field in the UI.** Nobody can type, view or reveal a key in the app.
* The key is read only from server secrets (`GROQ_API_KEY` in `.streamlit/secrets.toml`, Streamlit Cloud Secrets, or the environment) and passed straight to CrewAI's `LLM` object. It is never shown, logged, written to disk or backups.
* Error messages are scrubbed so the key can't leak. `.env` and `.streamlit/secrets.toml` are in `.gitignore` and `.dockerignore`. **Never commit a real key.** If you ever do, revoke it in the Groq console.
* CrewAI telemetry/tracing is disabled in code.
* **Usage protection** (`core/guard.py`): set `ACCESS_CODE` to put the whole app behind a code (5 wrong tries lock the session for 60 s; the code is never kept in session state). `SESSION_LIMIT` and `DAILY_LIMIT` cap AI requests. The daily cap is shared by all visitors and is the real protection; the per-session cap resets when someone reloads the page.
* **Public deployments:** every visitor uses *your* key and quota. Set `ACCESS_CODE` and/or `DAILY_LIMIT`, or keep the app private (Streamlit Cloud → Sharing).

## 🚀 Deploy from GitHub (Streamlit Community Cloud — free)
1. Push this folder to a GitHub repo (`git init && git add . && git commit -m "init" && git push`). Check `git status` shows no `.env`/`secrets.toml`.
2. Go to <https://share.streamlit.io> → **New app** → pick the repo, branch `main`, file `app.py`.
3. **Advanced settings → Python version: 3.11.**
4. **Secrets (required for AI):** add `GROQ_API_KEY = "gsk_..."`. Optional: `ACCESS_CODE`, `SESSION_LIMIT`, `DAILY_LIMIT` (see `.streamlit/secrets.toml.example`).
5. Deploy. First build takes a few minutes (CrewAI is large).

Docker: `docker build -t student-stack-pro . && docker run -p 8501:8501 student-stack-pro`

## Project layout
```
app.py                 navigation, home, error shield
core/llm.py            Groq+CrewAI runner, key handling, retries, JSON parsing
core/guard.py          access code + request caps
core/tracker.py        deadlines, urgency, .ics, GPA maths
core/deck.py           slideshow engine (.pptx + web presenter)
core/utils.py          PDF/PPTX readers, chunking, TF-IDF retriever, md→docx
core/scheduler.py      timetable engine + AI-output validator + .ics
core/textcheck.py      offline grammar/style checks, diff
core/resume_render.py  resume HTML / PDF / DOCX
modules/*.py           one file per tool (UI + agents)
tests/                 offline unit + end-to-end UI tests (fake LLM, no API key needed)
```

## Notes & limits
* Groq's free tier has token-per-minute limits; the app retries on rate limits. Use `llama-3.1-8b-instant` for speed, `llama-3.3-70b-versatile` for quality. Model ids can change — use **Custom…** in ⚙️ AI settings.
* Scanned PDFs/images need OCR, which isn't included. PDF resumes use standard Latin fonts.
* If you use CrewAI ≥ 1.0, install `pip install "crewai[litellm]"` (Groq goes through LiteLLM) and re-run `check_env.py`.
* AI output can be wrong — review before sending or submitting.

## Tests
`pip install pytest && pytest -q` (offline; covers scheduler, retrieval, text checks, resume PDF/DOCX).
