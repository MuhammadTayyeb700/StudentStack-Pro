<div align="center">

# 🎓 Student Stack Pro

### Thirteen AI-powered tools for study, work and career, in one Streamlit app.

Research crews · PDF study lab · resume builder · mini IDE · timetable maker · and more.<br>
Built with **CrewAI**, **Groq** and **Streamlit**.

<br>

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.40+-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)
![CrewAI](https://img.shields.io/badge/CrewAI-Multi--Agent-6366F1?style=for-the-badge)
![Groq](https://img.shields.io/badge/Groq-LLaMA%203.3-F55036?style=for-the-badge)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![CI](https://img.shields.io/badge/CI-GitHub%20Actions-2088FF?style=for-the-badge&logo=githubactions&logoColor=white)

[**Quick Start**](#-quick-start) · [**Features**](#-features) · [**Privacy**](#-privacy-and-api-key-safety) · [**Deploy**](#-deploy) · [**Project Layout**](#-project-layout)

</div>

---

## ✨ Why Student Stack Pro?

Most student tools are scattered across a dozen tabs and subscriptions. Student Stack Pro puts the essentials in one place, with a focus on three things:

| | |
|---|---|
| 🤖 **Real multi-agent workflows** | Tools like Research and Email use small CrewAI crews (e.g. Researcher → Reviewer → Writer) instead of a single prompt. |
| 🔒 **Privacy by design** | There is no API key field in the UI. The key lives only in server secrets and is never shown, logged or saved. |
| 🧰 **Works without AI too** | The timetable, study tracker, editor checks and GPA calculator run fully offline, so they work even with no key. |

---

## 🧩 Features

### 📚 Study

| Tool | What it does |
|---|---|
| 🔎 **Research Agents** | A 3-agent crew (Researcher → Reviewer → Writer) produces reports, summaries, briefings and study guides. Optional live web search. |
| 📚 **PDF Study Lab** | RAG over your PDFs using TF-IDF retrieval: notes, flashcards (Anki export) and Q&A with page citations. |
| 🖼️ **Slide Reader** | Turn `.pptx` or PDF decks into slide-by-slide notes, a summary, glossary, practice questions and a cheat-sheet. |
| 🧾 **Essay Feedback** | Upload or paste an essay (plus an optional rubric) and get a score out of 100, per-criterion marks, priority fixes and sentence suggestions. |
| 📝 **Writer's Desk** | Markdown editor with offline grammar and style checks, a readability score, AI rewrite with diff view and `.docx` export. |

### 🗓️ Organize

| Tool | What it does |
|---|---|
| 🗓️ **Timetable Maker** | A deterministic, clash-free scheduler with an optional AI planner (its output is validated). Exports `.ics` and CSV. |
| 📅 **Study Tracker** | Deadlines with urgency colours, `.ics` export, one-click send to the Timetable Maker, a focus timer and a GPA calculator. No AI needed. |
| 🎞️ **Slideshow Maker** | Give it a topic or your notes and get editable slides with speaker notes. Present in the browser or download `.pptx` / `.html`. |

### 💼 Career

| Tool | What it does |
|---|---|
| 📄 **Resume Studio** | Form → live preview → PDF or Word. AI polish, tailor to a job ad, import from pasted text. |
| 💌 **Cover Letter** | Paste a job ad and get a tailored letter built only from the facts in your Resume Studio. Export to PDF, Word or text. |
| ✉️ **Email Writer** | Writer and Proofreader agents give multiple options with tone and language control, plus an "open in mail app" button. |
| 💼 **LinkedIn Posts** | Strategist and Copywriter agents craft hooks, hashtags and a live post preview. |

### 💻 Build

| Tool | What it does |
|---|---|
| 💻 **Code Studio** | A multi-file mini IDE with syntax highlighting. AI can generate, edit, explain, fix, refactor and add tests. Includes a Run button for Python and JavaScript. |

> **🛡️ Code Studio runs in your browser, not on the server.** Python runs via Pyodide and JavaScript in a Web Worker, so your code can never reach the API key. Runs stop after 20 seconds. HTML/CSS/JS files get a live preview, and Python can import the standard library plus anything Pyodide provides (numpy, pandas, matplotlib, ...).

---

## 📥 Export Everything

| Format | Available for |
|---|---|
| **PDF · Word · Markdown** | Research, notes, slide notes, the editor |
| **Flashcard PDF** (printable, double-sided) · **Quizlet CSV** · **Anki TSV** | PDF Study Lab |
| **CSV · `.ics`** | Timetable, deadlines |
| **PDF · Word** | Resume, cover letter |
| **`.pptx` · `.html`** | Slideshow Maker |
| **💾 Workspace backup (JSON)** | Sidebar. Saves and restores your documents, resume, notes, cards and timetable. It never contains your API key or uploaded files. |

---

## 🚀 Quick Start

```bash
# 1. Clone
git clone https://github.com/SilentSoul8R/StudentStack-Pro.git
cd StudentStack-Pro

# 2. Create a virtual environment (Python 3.11 recommended)
python3.11 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. Install
pip install -r requirements.txt

# 4. Verify every package imports
python scripts/check_env.py

# 5. Run
streamlit run app.py
```

Then open **http://localhost:8501**.

### 🔑 Add your Groq API key

Get a free key at **[console.groq.com](https://console.groq.com)**, then use **one** of these:

<table>
<tr>
<td width="50%">

**Option A: `.env`**

```bash
cp .env.example .env
```
```ini
GROQ_API_KEY=gsk_your_key_here
```

</td>
<td width="50%">

**Option B: Streamlit secrets**

```bash
cp .streamlit/secrets.toml.example \
   .streamlit/secrets.toml
```
```toml
GROQ_API_KEY = "gsk_your_key_here"
```

</td>
</tr>
</table>

> 💡 Want live web search in Research Agents? Run `pip install -r requirements-optional.txt`.

---

## ⚙️ Configuration

| Variable | Required | Default | Description |
|---|:---:|:---:|---|
| `GROQ_API_KEY` | For AI tools | none | Your Groq API key. Server-side only. |
| `ACCESS_CODE` | No | none | Puts the whole app behind a passphrase. 5 wrong tries lock the session for 60 s. |
| `SESSION_LIMIT` | No | `60` | Max AI requests per browser session (`0` = unlimited). |
| `DAILY_LIMIT` | No | `500` | Max AI requests per day across **all** visitors (`0` = unlimited). |

**Models:** pick one in the sidebar's ⚙️ AI settings.

- `llama-3.3-70b-versatile` for quality (default)
- `llama-3.1-8b-instant` for speed
- **Custom…** for any other Groq model id, since ids change over time

---

## 🔒 Privacy and API-Key Safety

- **No key field in the UI.** Nobody can type, view or reveal a key in the app.
- The key is read only from server secrets or the environment and passed straight to CrewAI's `LLM` object. It is never shown, logged, or written to disk or backups.
- **Error messages are scrubbed** so a key can't leak through a stack trace.
- `.env` and `.streamlit/secrets.toml` are in both `.gitignore` and `.dockerignore`.
- **CrewAI telemetry is disabled** in code.
- Uploaded files and text are processed **in memory** and discarded when you close the tab. Only the text needed for a request is sent to Groq.

> ⚠️ **Never commit a real key.** If you ever do, revoke it in the Groq console right away. CI runs `scripts/check_secrets.py` to help catch this.

### 🛡️ Usage protection for public deployments

Every visitor of a public deployment uses *your* key and quota. Protect it with `core/guard.py`:

1. Set **`ACCESS_CODE`** to require a passphrase.
2. Set **`DAILY_LIMIT`**. This is the real safeguard, because it is shared by all visitors. (The per-session cap resets on page reload.)
3. Or keep the app private via Streamlit Cloud → Sharing.

---

## ☁️ Deploy

### Streamlit Community Cloud (free)

1. Push the project to a GitHub repo and check that `git status` shows no `.env` or `secrets.toml`.
2. Go to **[share.streamlit.io](https://share.streamlit.io)** → **New app** → choose your repo, branch `main`, file `app.py`.
3. Under **Advanced settings → Python version**, choose **3.11**.
4. Under **Secrets**, add your config (see `.streamlit/secrets.toml.example`):
   ```toml
   GROQ_API_KEY = "gsk_..."
   # ACCESS_CODE = "choose-a-long-passphrase"
   # DAILY_LIMIT = 500
   ```
5. Click **Deploy**. The first build takes a few minutes because CrewAI is large.

### 🐳 Docker

```bash
docker build -t student-stack-pro .
docker run -p 8501:8501 -e GROQ_API_KEY=gsk_your_key_here student-stack-pro
```

---

## 🗂️ Project Layout

```text
StudentStack-Pro/
├── app.py                  # navigation, home page, error shield
├── core/
│   ├── llm.py              # Groq + CrewAI runner, key handling, retries, JSON parsing
│   ├── guard.py            # access code + request caps
│   ├── backup.py           # workspace backup / restore
│   ├── tracker.py          # deadlines, urgency, .ics, GPA maths
│   ├── deck.py             # slideshow engine (.pptx + web presenter)
│   ├── scheduler.py        # timetable engine + AI-output validator + .ics
│   ├── textcheck.py        # offline grammar/style checks, diff
│   ├── resume_render.py    # resume HTML / PDF / DOCX
│   ├── codegen.py          # code generation helpers
│   ├── utils.py            # PDF/PPTX readers, chunking, TF-IDF retriever, md → docx
│   └── ui.py               # shared styling and components
├── modules/                # one file per tool (UI + agents)
├── static/ide_runner/      # in-browser sandbox for Code Studio
├── tests/                  # offline unit + end-to-end UI tests
├── scripts/                # check_env.py, check_secrets.py
├── .github/workflows/      # CI pipeline
└── Dockerfile
```

---

## 🧪 Tests

The test suite is fully offline. It uses a fake LLM, so **no API key is needed**.

```bash
pip install pytest
pytest -q
```

It covers the scheduler, retrieval, text checks, resume PDF/DOCX output, code generation and end-to-end UI flows. CI runs on every push and pull request.

---

## 📝 Notes and Limits

- Groq's free tier has token-per-minute limits. The app automatically retries on rate limits.
- **Scanned PDFs and images need OCR**, which isn't included.
- PDF resumes use standard Latin fonts.
- On **CrewAI ≥ 1.0**, run `pip install "crewai[litellm]"` (Groq goes through LiteLLM), then re-run `check_env.py`.
- AI output can be wrong. **Review it before sending or submitting.**

---

## 🤝 Contributing

Issues and pull requests are welcome.

1. Fork the repo and create a branch: `git checkout -b feature/my-idea`
2. Make your changes and run `pytest -q`
3. Open a pull request

Adding a new tool is simple: create `modules/your_tool.py` with a `render()` function, then register it in the `PAGES` dict in `app.py`.

---

<div align="center">

**Built with 💜 for students everywhere.**

If this project helps you, consider giving it a ⭐

</div>
