AI Resume Agent

This project is a small web app that takes a job description and your resume,
then rewrites the resume to better match the job. It also picks the most
relevant projects from your project list and generates a new `.docx` file you
can download.

Think of it like a friendly helper that:
- Reads the job post
- Picks your best matching projects
- Rewrites your resume (without making things up)
- Gives you a new resume file and a side-by-side diff

---

## What is inside this project?

- `app/web_app.py` - FastAPI web server (the main app)
- `app/pipeline.py` - The step-by-step resume improvement logic
- `app/agents.py` - Prompts and LLM calls (project selection, rewrite, judge)
- `app/local_llm_client.py` - Uses Ollama locally, falls back to OpenRouter
- `app/openrouter_client.py` - OpenRouter API client and daily usage tracking
- `app/projects.json` - Your project inventory
- `app/style_guide.md` - Resume writing style guide
- `app/static/` - Frontend HTML/CSS/JS files
- `data/usage.json` - Automatically created usage log for OpenRouter calls
- `output/` - Generated `.docx` resume files

---

## How it works (simple version)

1. You paste a job description and your resume.
2. The app analyzes the job description (skills, responsibilities, keywords).
3. It selects the best projects from `app/projects.json`.
4. It rewrites your resume to match the job while staying truthful.
5. It judges the result and may retry a few times to improve the score.
6. It creates a `.docx` file you can download.

---

## What you need before running it

- Python 3.11 (recommended)
- `pip` (Python package installer)
- One of the following LLM options:
  - Option A: **Ollama** running locally (free, no API keys)
  - Option B: **OpenRouter** API keys (requires internet)

---

## Quick start (local Python)

1) Install dependencies:
```bash
pip install -r requirements.txt
```

2) Create a `.env` file in the project root:
```env
# At least one OpenRouter key (if you want cloud fallback)
OPENROUTER_KEY_1=your_key_here

# Optional
OPENROUTER_DAILY_CALL_LIMIT=6
OPENROUTER_STEP1_MODEL=mistralai/mistral-7b-instruct:free
```

3) Start the server:
```bash
uvicorn app.web_app:app --reload --host 0.0.0.0 --port 8000
```

4) Open your browser:
```
http://localhost:8000
```

---

## Option A: Run with Ollama (local model)

This avoids API keys and uses a local model.

1) Install Ollama from https://ollama.com
2) Pull a model:
```bash
ollama pull mistral
```

3) Run the app as usual:
```bash
uvicorn app.web_app:app --reload --host 0.0.0.0 --port 8000
```

The app calls Ollama at:
```
http://localhost:11434
```

---

## Option B: Run with Docker

If you prefer containers:

```bash
docker-compose up --build
```

Then open:
```
http://localhost:8000
```

---

## How to use the web app

1) Open the home page.
2) Paste a job description.
3) Paste your resume text OR upload a `.docx` resume.
4) Choose how many projects to include.
5) Click Generate.
6) Download the new resume and review the diff.

---

## API endpoints (for developers)

- `GET /` - Loads the web UI
- `GET /projects` - Returns projects from `app/projects.json`
- `POST /generate` - Creates a new resume
- `POST /regenerate/{job_id}` - Improve the resume again
- `GET /download/{filename}` - Download the `.docx` file

---

## Customizing your projects

Edit `app/projects.json` with your real projects. Example shape:

```json
[
  {
    "id": "proj-1",
    "name": "Inventory Tracker",
    "intro": "Built a small inventory system for a local shop.",
    "bullets": [
      "Reduced stock errors by 30% with barcode scanning",
      "Built a dashboard for daily sales and restock alerts"
    ],
    "tech_tags": ["Python", "FastAPI", "SQLite"],
    "domain_tags": ["Retail", "Inventory"]
  }
]
```

Keep the data real and honest.

---

## Where outputs go

Generated resumes are stored in:
- `output/`

Each file is named with the company name and a version number.

---

## Common problems and fixes

- **"No available OpenRouter keys"**
  - Add at least one `OPENROUTER_KEY_*` in your `.env`.
- **"Only .docx files are supported"**
  - Upload a `.docx` file, not `.pdf` or `.txt`.
- **Ollama not responding**
  - Make sure Ollama is running and the model is pulled.
  - Check the URL: `http://localhost:11434`

---

## Tips for best results

- Use a clear job description with real requirements.
- Keep your base resume up to date.
- Add strong, measurable project bullets in `projects.json`.

---

## License

No license is specified yet. Add one if you plan to share or publish this.
