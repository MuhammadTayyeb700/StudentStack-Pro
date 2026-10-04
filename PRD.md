# Student Stack Pro: Product Requirements Document

**Owners:** Muhammad Abdullah, Muhammad Faizan Amjad, Muhammad Tayyab, Muhammad Abdullah
**Last updated:** October 4, 2026

## Contents

1. [Overview](#1-overview)
2. [Goals](#2-goals)
3. [Non-goals](#3-non-goals)
4. [Target users](#4-target-users)
5. [Tech stack](#5-tech-stack)
6. [Information architecture](#6-information-architecture)
7. [Feature requirements](#7-feature-requirements)
8. [Cross-cutting requirements](#8-cross-cutting-requirements)
9. [Success metrics](#9-success-metrics)
10. [Milestones](#10-milestones)
11. [Open questions](#11-open-questions)
12. [Risks](#12-risks)

---

## 1. Overview

Student Stack Pro is a single Streamlit web app that bundles thirteen AI-powered tools for students into one interface. A home screen and a sidebar switch between the tools. The AI runs on Groq's free-tier hosted models through CrewAI agents, and the app is deployed from GitHub to Streamlit Community Cloud.

> One app, every tool a student needs: research, emails, LinkedIn posts, PDF study notes, timetables, essay feedback, resumes, slides and code, all free and all in one tab.

The project grew from three standalone scripts (email generator, LinkedIn post generator, PDF reader) into a platform. Ten more tools were added around a shared core (`core/`) that owns the API key, usage limits, exports and error handling, so each tool is only its own screen and prompts.

## 2. Goals

1. Give a student one place for everyday academic and career writing, studying, planning and coding tasks, so they do not need a different website for each.
2. Run entirely on Groq's free developer tier, with no paid model or paid hosting required.
3. Deploy publicly and for free from GitHub to Streamlit Community Cloud.
4. Never expose the Groq API key in the UI, the browser, logs, backups or the repository.
5. Protect a shared key from abuse with an access code and request caps.
6. Make every result usable outside the app: PDF, Word, Markdown, CSV, `.ics`, `.pptx` and Anki/Quizlet exports.
7. Keep behaviour that does not need AI (timetable scheduling, deadlines, GPA, grammar checks, code execution) deterministic and offline.

## 3. Non-goals

- No user accounts, login or server-side database in v1. State lives in the browser session, with a downloadable workspace backup.
- No paid or premium model tiers.
- No native mobile app. The responsive web layout from Streamlit is the target.
- No OCR. Scanned or image-only PDFs are not supported.
- No server-side code execution. Code Studio runs code in the visitor's own browser only.

## 4. Target users

Students (high school, university, early graduate school) who need fast, free help with writing and study tasks: emails to professors, LinkedIn presence for internships, digesting PDF readings and slide decks, planning study time, getting feedback on essays, building a resume and cover letter, making presentations, and learning to code.

**Secondary user:** the app owner, who deploys one instance with their own key and needs to control who can use it and how much.

## 5. Tech stack

| Layer | Choice |
|---|---|
| Language | Python 3.11 (3.11 and 3.12 tested) |
| UI framework | Streamlit 1.40 to 1.49 |
| LLM orchestration | CrewAI (0.130 up to 1.0), multi-agent crews per tool |
| LLM provider | Groq API, free tier only, reached through CrewAI's LLM (LiteLLM) |
| Retrieval (PDF Study Lab) | TF-IDF with scikit-learn, with page citations |
| Document I/O | pypdf (read PDF), python-pptx, python-docx, reportlab (write PDF), pandas |
| Code editor | streamlit-ace, with a plain text area as fallback |
| In-browser code runner | Pyodide 0.29.5 for Python and a Web Worker for JavaScript, loaded from the jsDelivr CDN |
| Deployment | GitHub repo to Streamlit Community Cloud; Dockerfile for self-hosting |
| Secrets | `GROQ_API_KEY` from Streamlit secrets or an environment variable. There is no key field in the UI |
| CI | GitHub Actions: secret scan, import check, pytest |

### 5.1 Model policy

One shared model list (`MODELS` in `core/llm.py`) drives the dropdown for every tool, with the default `llama-3.3-70b-versatile` and a **Custom...** option for any other Groq model id. The list currently holds:

- `llama-3.3-70b-versatile` (quality, default)
- `llama-3.1-8b-instant` (speed)
- `openai/gpt-oss-120b`
- `openai/gpt-oss-20b`

> **Needs verification.** Groq's models page (checked October 4, 2026) lists these four as production models, plus the preview models `minimaxai/minimax-m2.7`, `openai/gpt-oss-safeguard-20b` and `qwen/qwen3.8-27b`. The team has reported that some listed models are not available on its Groq API key. Which ones, and why, has not been confirmed. See requirement FR-M1 in [section 8.4](#84-model-selection-and-errors) and open question Q1.

**Requirement:** no tool may hard-code a model id. The list lives in one place so it can be changed in one edit when Groq changes availability.

## 6. Information architecture

One entry point, `app.py`, owns page config, shared styling, the access gate, sidebar settings, navigation and an error shield. Each tool is a module in `modules/` exposing `render()` and is imported on demand. A home screen shows a card grid; the sidebar radio switches tools at any time.

```text
Student Stack Pro
├─ Write & communicate
│  ├─ Email Writer
│  ├─ LinkedIn Posts
│  ├─ Cover Letter
│  ├─ Writer's Desk
│  └─ Resume Studio
├─ Research & study
│  ├─ Research Agents
│  ├─ PDF Study Lab
│  ├─ Slide Reader
│  └─ Essay Feedback
├─ Present
│  └─ Slideshow Maker
├─ Plan
│  ├─ Timetable Maker
│  └─ Study Tracker
└─ Build
   └─ Code Studio
```

## 7. Feature requirements

All thirteen tools are built. The status chip shows what is verified today; requirements marked **Check** still need a live test on the deployed app.

### 7.1 Research Agents `Shipped`

| | |
|---|---|
| **Inputs** | Topic; deliverable type (detailed report, executive summary, briefing, literature-style overview, pros and cons, study guide, or custom); audience; length (about 400, 900 or 1800 words); optional live web snippets. |
| **Output** | A finished document produced by a three-agent crew (Researcher, Reviewer, Writer). Download as PDF, Markdown or Word. |
| **Notes** | The Reviewer step removes or flags unsupported claims. Web search is optional and needs the packages in `requirements-optional.txt`. |

### 7.2 Email Writer `Shipped`

| | |
|---|---|
| **Inputs** | Quick-start template; what the email should achieve; recipient and sender names; key points; tone; length (very short to detailed); language (English, Urdu, Roman Urdu, Arabic, French, Spanish, German); 1 to 3 options. An original email can be pasted to write a reply. |
| **Output** | Up to three editable drafts with subject and body, written by a Writer and a Proofreader agent. Save as `.txt` or open in the mail app. |

### 7.3 LinkedIn Posts `Shipped`

| | |
|---|---|
| **Inputs** | What the post is about; goal; audience; name and headline; post style (personal story, lessons learned, listicle, announcement, hot take, and others); tone; length; emoji level; 0 to 8 hashtags; call to action; 1 to 3 variants. |
| **Output** | A post with a strong hook, a live preview, an editable text area and a `.txt` download. Built by a Strategist and a Copywriter agent. |

### 7.4 PDF Study Lab `Shipped`

| | |
|---|---|
| **Inputs** | One or more PDFs; note style; maximum characters to read (default 40,000); number of flashcards (5 to 40); questions. |
| **Pipeline** | Extract text per page with pypdf, chunk with overlap, index with TF-IDF, retrieve the top chunks for each question, and answer from those chunks with page citations. |
| **Output** | Three tabs: Notes (PDF, Markdown, Word), Flashcards (printable double-sided PDF, Quizlet CSV, Anki TSV) and Ask your PDF (chat with sources). |
| **Limits** | Scanned PDFs with no extractable text show a clear message and are not processed. |

### 7.5 Slide Reader `Shipped`

| | |
|---|---|
| **Inputs** | A `.pptx` or PDF slide deck. |
| **Output** | Slide-by-slide notes, a summary, a glossary, practice questions and a cheat sheet. Download as PDF, Markdown or Word. |

### 7.6 Timetable Maker `Shipped`

| | |
|---|---|
| **Inputs** | Fixed commitments (classes, work) and tasks with time estimates and deadlines, in editable tables; working window; break length (0 to 30 minutes). |
| **Output** | A clash-free weekly plan from a deterministic scheduler, with an optional AI planner. Export as CSV or `.ics` calendar. |
| **Notes** | AI output is parsed and validated in Python (`core/scheduler.py`) before it is shown. Raw model text is never trusted for the table. |

### 7.7 Study Tracker `Shipped`

| | |
|---|---|
| **Inputs** | Deadlines (title, course, due date, hours, priority); GPA courses and grades. |
| **Output** | Deadlines with urgency colours and an `.ics` export; one-click send to Timetable Maker; a focus timer; a GPA calculator. No AI is used. |

### 7.8 Writer's Desk `Shipped`

| | |
|---|---|
| **Inputs** | Markdown text, optionally from a template. AI actions with a tone setting. |
| **Output** | Write, Preview and Proofread tabs. Offline grammar and style checks with a readability score. AI rewrites are shown as a diff to accept or discard. Download as Word, PDF, Markdown or plain text. |

### 7.9 Resume Studio `Shipped`

| | |
|---|---|
| **Inputs** | Form tabs: You, Experience, Education, Skills and more, Design and AI. Optional pasted old resume to import and a job ad to tailor to. |
| **Output** | Live preview with selectable template and accent colour; AI polish; download as PDF or Word. |
| **Notes** | The resume facts are reused by Cover Letter, so the letter is built only from what the student entered. |

### 7.10 Cover Letter `Shipped`

| | |
|---|---|
| **Inputs** | A pasted job ad and the facts saved in Resume Studio. |
| **Output** | An editable tailored letter, written only from the student's real details. Download as PDF, Word or text. |

### 7.11 Essay Feedback `Shipped`

| | |
|---|---|
| **Inputs** | An essay pasted or uploaded (`.docx`, `.pdf`, `.txt`, up to 12,000 characters); level (high school, undergraduate, postgraduate); essay kind; strictness (lenient, balanced, strict); optional rubric. |
| **Output** | A score out of 100, per-criterion marks, priority fixes and sentence-level suggestions. Download as PDF, Markdown or Word. |
| **Notes** | The model's JSON is normalised and clamped (`normalize_feedback`) so odd values never break the page. |

### 7.12 Slideshow Maker `Shipped`

| | |
|---|---|
| **Inputs** | Topic; audience; slide count; tone; optional source notes; speaker notes on or off. |
| **Output** | An editable deck (bullets, two-column and section layouts) that can be presented in the browser or downloaded as `.pptx`, `.html` or a Markdown outline. |

### 7.13 Code Studio `Shipped` `Check CDN on deploy`

| | |
|---|---|
| **Editor** | Multi-file workspace (up to 12 files) with syntax highlighting, line numbers, autocomplete, themes and VS Code, Vim or Emacs keybindings. New, rename, delete, open files or a `.zip` project from the computer, and download everything as a `.zip`. |
| **Run** | Python (Pyodide, with `input()` from a stdin box and imports between files) and JavaScript run inside the visitor's browser in a Web Worker. A run is stopped after 20 seconds, so an infinite loop cannot freeze the page. HTML files get a live preview with linked CSS and JS inlined. |
| **AI** | Generate, Edit, Explain, Fix and debug, Refactor, Add tests and Add comments. Generate, Edit, Fix, Refactor and Add comments replace the file; Explain and Add tests show their answer beside the editor. After a failed run, Fix with AI sends the error message to the model. |
| **Limits** | 200 KB per imported file. C++, SQL and other types can be edited and downloaded but not run. Python packages beyond the standard library come from Pyodide's own set (numpy, pandas, matplotlib and others). |
| **Safety** | No code ever runs on the server, so it cannot read secrets, files or the API key. |

## 8. Cross-cutting requirements

### 8.1 Navigation and state

- The home screen shows a card for every tool; the sidebar radio is available on every screen.
- Inputs and results are kept in `st.session_state` per tool (`ui.sticky` and `ui.keep`), so switching tools and returning does not wipe work.
- Tools are imported only when opened, so a failure in one tool does not stop the others.

### 8.2 API key handling

- The key is read only from Streamlit secrets or the `GROQ_API_KEY` environment variable. There is no key field in the UI, so nobody can type, view or reveal a key.
- The key is never shown, logged, written to disk, saved in a backup or put into `os.environ` by the app. Error text passes through `scrub()`, which removes the key and any `gsk_…` pattern.
- `.env` and `.streamlit/secrets.toml` are in `.gitignore` and `.dockerignore`; CI runs `scripts/check_secrets.py`.
- CrewAI telemetry and tracing are disabled in code.

### 8.3 Usage protection

All settings are optional, set in secrets or the environment (`core/guard.py`).

| Setting | Effect | Default |
|---|---|---|
| `ACCESS_CODE` | Visitors must enter the code before using any tool. Five wrong tries lock the session for 60 seconds. The code itself is never stored in session state. | Off |
| `SESSION_LIMIT` | Maximum AI requests per browser session (0 means unlimited) | 60 |
| `DAILY_LIMIT` | Maximum AI requests per day across all visitors. This is the real protection for a shared key. | 500 |

### 8.4 Model selection and errors

- **FR-M1** `Planned` Fill the model dropdown from Groq's live models endpoint for the deployed key, filtered to chat models, and fall back to the static list when the call fails. This removes the dependence on a hand-maintained list.
- **FR-M2** `Planned` Label each model with a short speed or quality note and a reminder that free-tier rate limits apply.
- **FR-M3** `Shipped` A **Test connection** button in AI settings sends a one-word request and reports success or a friendly error.
- **FR-E1** `Shipped` One shared error translator (`_friendly` in `core/llm.py`) turns raw API errors into plain messages for: missing or rejected key, rate limit (429), input too large (413), and a model that no longer exists.
- **FR-E2** `Shipped` Rate-limited requests are retried automatically. A global error shield in `app.py` shows a readable startup error instead of a blank page.
- **FR-E3** `Shipped` Model JSON is extracted and repaired (`extract_json`, `strip_fences`) and then validated by each tool before display.

### 8.5 Exports

Every tool that produces a document offers a download. Formats in use: PDF, Word (`.docx`), Markdown, plain text, CSV, `.ics` calendar, `.pptx`, standalone `.html` slideshow, Quizlet CSV, Anki TSV, printable flashcard PDF, and `.zip` for Code Studio projects.

### 8.6 Privacy and data

- Nothing is stored on the server. Documents live in the browser session.
- The sidebar **Save / restore my work** backup is a JSON file holding documents, resume, notes, cards and timetable. It never includes the API key or uploaded files.
- Uploaded files are processed in memory for the session only.

### 8.7 Code execution safety

- Code runs only in the visitor's browser, inside a Web Worker. The earlier design that ran code in a server subprocess was removed because a text filter cannot stop a determined user from reading server files or environment.
- The component loads the Python runtime from `cdn.jsdelivr.net`. If that host is blocked, Run reports an error and the rest of the app is unaffected.

### 8.8 Styling

One shared CSS block (`core/ui.py`) and one set of page and hero helpers give every tool the same look: an indigo gradient accent, card layouts and consistent buttons.

### 8.9 Testing and CI

- Offline test suite with a fake LLM, so no API key or network is needed: scheduler, retrieval, text checks, resume rendering, end-to-end page flows and Code Studio helpers.
- GitHub Actions runs the secret scan, the import check (`scripts/check_env.py`) and pytest on every push and pull request.
- Code Studio was also exercised in a real browser: Python with `input()`, tracebacks, Fix with AI, infinite-loop stop, a new JavaScript file, and importing a multi-file project.

### 8.10 File structure

```text
app.py                 navigation, home, error shield
core/
  llm.py               Groq + CrewAI runner, key handling, retries, JSON parsing
  guard.py             access code + request caps
  ui.py                shared CSS, headers, sticky widget state
  utils.py             PDF/PPTX readers, chunking, TF-IDF retriever, markdown to docx
  scheduler.py         timetable engine + AI-output validator + .ics
  tracker.py           deadlines, urgency, .ics, GPA maths
  textcheck.py         offline grammar/style checks, diff
  deck.py              slideshow engine (.pptx + web presenter)
  resume_render.py     resume HTML / PDF / DOCX
  backup.py            workspace backup and restore
  codegen.py           Code Studio helpers (files, zip, prompts)
modules/               one file per tool (UI + agents)
static/ide_runner/     in-browser Python/JS runner component
tests/                 offline unit + end-to-end UI tests
scripts/               check_env.py, check_secrets.py
.github/workflows/     ci.yml
Dockerfile             self-hosting
```

## 9. Success metrics

- All 13 tools work end to end on Streamlit Community Cloud using only free Groq models.
- No API key is visible in the UI, the browser's network tab or the GitHub repository. The CI secret scan passes on every commit.
- Every model offered in the dropdown works with the deployed key (FR-M1 and Q1).
- No unhandled traceback reaches a visitor: failures show a friendly message.
- A first-time visitor completes one result (for example a timetable or a set of flashcards) without help.
- The daily request cap holds: heavy use by one visitor cannot exhaust the key for everyone else.

## 10. Milestones

| Stage | Scope | Status |
|---|---|---|
| 1. Merge and refactor | Combine the three original scripts into one app with shared navigation, styling, key handling and error handling | Done |
| 2. New tools | Research Agents, Slide Reader, Timetable Maker, Study Tracker, Writer's Desk, Cover Letter, Essay Feedback, Slideshow Maker, Resume Studio | Done |
| 3. Code Studio | Multi-file editor, in-browser Python and JavaScript runner, AI assistant, file import and export | Done |
| 4. Hardening | Access code, request caps, key scrubbing, secret scan in CI, offline tests | Done |
| 5. Model availability | Find which listed models fail on the deployed key; implement FR-M1 and FR-M2 | Open |
| 6. Deploy | Push to GitHub, configure Community Cloud with Python 3.11 and secrets, smoke-test every tool live, confirm Code Studio's runtime loads | In progress |
| 7. Submit | Make the repo public if required, add the app link and access code to the submission, wake the app before judging | Next |

## 11. Open questions

- **Q1.** Which listed models are rejected by the Groq API for the team's key, and with what error? Groq's documentation lists all four as production models, so the cause may be account-level access, a rate limit or a naming difference. Confirm by calling the models endpoint with the deployed key.
- **Q2.** Should the public demo be protected with `ACCESS_CODE`, or left open and protected only by the request caps?
- **Q3.** Should generated content (resumes, schedules, notes) be saved beyond the browser session, given there is no login or database in v1?
- **Q4.** Is the jsDelivr CDN reachable from the deployment and from the judges' networks, so Code Studio's Python runner loads? If not, the runtime files would need to be bundled with the app.
- **Q5.** Should OCR be added so scanned PDFs work in PDF Study Lab and Slide Reader?

## 12. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Model availability changes or differs by account | A tool fails with a model error | One shared list, Custom... field, friendly error text, FR-M1 live list, Test connection button |
| Free-tier rate limits | Heavy use of one tool, such as PDF chat, blocks others | Automatic retry, session and daily caps, and error text that suggests the faster model |
| Public demo uses the owner's key | Strangers consume the quota | `ACCESS_CODE`, `DAILY_LIMIT`, a separate key used only for the demo, and revocation after the event |
| CDN blocked for Code Studio | Run does not work for some visitors | Clear error message; other features unaffected; bundle the runtime if needed (Q4) |
| Scanned or image-only PDFs | No text can be extracted | Clear message instead of a silent failure; OCR is a future option |
| AI output is wrong or malformed | Bad schedules, invalid JSON, inaccurate notes | Python-side validation, clamped fields, retry prompts, and a visible reminder to review output before use |
| Dependency drift (CrewAI, Streamlit) | A new release breaks the app | Pinned version ranges, `check_env.py` in CI; CrewAI 1.0 and later needs `crewai[litellm]` |
| Cold start on free hosting | The first visit after idle time is slow; the first CrewAI build takes minutes | Open the app before judging; keep dependencies lean |

---

*Student Stack Pro, PRD. Prepared October 4, 2026.*
