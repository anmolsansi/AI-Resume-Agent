from pathlib import Path
import uuid

from fastapi import FastAPI, Form, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .pipeline import run_pipeline_and_get_text
from .file_utils import create_resume_docx, extract_text_from_docx_bytes
from .diff_utils import make_side_by_side_diff_html

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
async def generate_resume(
    jd: str = Form(...),
    company: str = Form(...),
    resume_mode: str = Form("paste"),
    base_resume: str = Form(""),
    resume_file: UploadFile | None = File(None),
):
    if resume_mode == "upload":
        if not resume_file:
            raise HTTPException(status_code=400, detail="resume_file is required for upload mode")
        filename = (resume_file.filename or "").lower()
        if not filename.endswith(".docx"):
            raise HTTPException(status_code=400, detail="Only .docx files are supported")
        docx_bytes = await resume_file.read()
        base_resume_text = extract_text_from_docx_bytes(docx_bytes)
    else:
        base_resume_text = (base_resume or "").strip()

    if not base_resume_text:
        raise HTTPException(status_code=400, detail="Resume content is empty")

    resume_text, judgement = run_pipeline_and_get_text(
        jd_text=jd,
        base_resume=base_resume_text,
    )
    diff_html = make_side_by_side_diff_html(base_resume_text, resume_text)

    job_id = str(uuid.uuid4())

    # version starts at 1 for a new job
    version = 1
    docx_path = create_resume_docx(company, resume_text, version)

    SESSIONS[job_id] = {
        "jd": jd,
        "company": company,
        "base_resume": base_resume_text,
        "version": version,
        "files": [docx_path.name],
    }

    return JSONResponse({
        "job_id": job_id,
        "version": version,
        "score": judgement.get("score"),
        "summary": judgement.get("summary"),
        "docx_file": docx_path.name,
        "download_url": f"/download/{docx_path.name}",
        "all_versions": SESSIONS[job_id]["files"],
        "new_resume_text": resume_text,
        "diff_html": diff_html,
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
        max_loops=3
    )
    diff_html = make_side_by_side_diff_html(base_resume, resume_text)

    # initialize session state if missing (for backwards compatibility)
    session.setdefault("version", 1)
    session.setdefault("files", [])

    # increment version
    session["version"] += 1
    version = session["version"]

    docx_path = create_resume_docx(company, resume_text, version)

    session["files"].append(docx_path.name)

    return JSONResponse({
        "job_id": job_id,
        "version": version,
        "score": judgement.get("score"),
        "summary": judgement.get("summary"),
        "docx_file": docx_path.name,
        "download_url": f"/download/{docx_path.name}",
        "all_versions": session["files"],
        "new_resume_text": resume_text,
        "diff_html": diff_html,
    })

@app.get("/download/{filename}")
def download_file(filename: str):
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, filename=filename)
