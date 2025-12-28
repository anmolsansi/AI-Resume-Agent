from pathlib import Path
import uuid

from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .pipeline import run_pipeline_and_get_text
from .file_utils import create_resume_docx

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "output"
STATIC_DIR = BASE_DIR / "app" / "static"

app = FastAPI()

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

SESSIONS = {}

@app.get("/", response_class=HTMLResponse)
def index():
    return (STATIC_DIR / "index.html").read_text()

@app.post("/generate")
def generate_resume(
    jd: str = Form(...),
    company: str = Form(...),
    base_resume: str = Form(...),
):
    resume_text, judgement = run_pipeline_and_get_text(
        jd_text=jd,
        base_resume=base_resume,
    )

    docx_path = create_resume_docx(company, resume_text)

    job_id = str(uuid.uuid4())
    SESSIONS[job_id] = {
        "jd": jd,
        "company": company,
        "base_resume": base_resume,
    }

    return JSONResponse({
        "job_id": job_id,
        "score": judgement.get("score"),
        "summary": judgement.get("summary"),
        "docx_file": docx_path.name,
        "download_url": f"/download/{docx_path.name}",
    })

@app.post("/regenerate/{job_id}")
def regenerate_resume(job_id: str):
    session = SESSIONS.get(job_id)
    if not session:
        raise HTTPException(status_code=404, detail="Unknown job_id")

    jd = session["jd"]
    company = session["company"]
    base_resume = session["base_resume"]

    resume_text, judgement = run_pipeline_and_get_text(
        jd_text=jd,
        base_resume=base_resume,
    )

    docx_path = create_resume_docx(company, resume_text)

    return JSONResponse({
        "job_id": job_id,
        "score": judgement.get("score"),
        "summary": judgement.get("summary"),
        "docx_file": docx_path.name,
        "download_url": f"/download/{docx_path.name}",
    })

@app.get("/download/{filename}")
def download_file(filename: str):
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, filename=filename)
