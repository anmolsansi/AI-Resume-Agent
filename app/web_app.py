from pathlib import Path
import uuid
from typing import Dict, List, Union
from fastapi import FastAPI, Form, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .pipeline import run_pipeline_and_get_text
from .file_utils import (
    create_resume_docx,
    extract_text_from_docx_bytes,
    load_master_resume_text,
)
from .diff_utils import make_side_by_side_diff_html
from .projects_utils import load_projects

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "output"
STATIC_DIR = BASE_DIR / "app" / "static"

app = FastAPI()

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

SESSIONS = {}

@app.get("/", response_class=HTMLResponse)
def index():
    return (STATIC_DIR / "index.html").read_text()


@app.get("/projects")
def get_projects():
    projects = load_projects()
    return {"count": len(projects), "projects": projects}


def _project_display_names(projects):
    names: List[str] = []
    for project in projects:
        if not project:
            continue
        name = project.get("name") or project.get("id")
        if name:
            names.append(name)
    return names

@app.post("/generate")
async def generate_resume(
    jd: str = Form(...),
    company: str = Form(...),
    project_count: int = Form(3),
    resume_mode: str = Form("paste"),
    base_resume: str = Form(""),
    resume_file: Union[UploadFile, None] = File(None),
):
    resume_source = "paste"
    base_resume_text = ""

    if resume_mode == "upload":
        resume_source = "upload"
        if resume_file:
            filename = (resume_file.filename or "").lower()
            if not filename.endswith(".docx"):
                raise HTTPException(status_code=400, detail="Only .docx files are supported")
            docx_bytes = await resume_file.read()
            base_resume_text = extract_text_from_docx_bytes(docx_bytes)
        else:
            resume_source = "master"
            base_resume_text = load_master_resume_text()
    else:
        base_resume_text = (base_resume or "").strip()
        if not base_resume_text:
            resume_source = "master"
            base_resume_text = load_master_resume_text()

    if not base_resume_text:
        raise HTTPException(status_code=400, detail="Resume content is empty (including master resume)")

    projects = load_projects()
    resume_text, judgement, pipeline_state = run_pipeline_and_get_text(
        jd_text=jd,
        base_resume=base_resume_text,
        project_count=project_count,
        projects=projects,
    )
    diff_html = make_side_by_side_diff_html(base_resume_text, resume_text)

    job_id = str(uuid.uuid4())

    # version starts at 1 for a new job
    version = 1
    docx_path = create_resume_docx(company, resume_text, version)

    selected_project_ids = pipeline_state.get("selected_project_ids", [])
    selected_projects_detail = pipeline_state.get("selected_projects", [])
    selected_project_names = _project_display_names(selected_projects_detail)

    SESSIONS[job_id] = {
        "jd": jd,
        "company": company,
        "base_resume": base_resume_text,
        "jd_analysis": pipeline_state.get("jd_analysis", ""),
        "selected_project_ids": selected_project_ids,
        "resume_source": resume_source,
        "project_count": project_count,
        "version": version,
        "files": [docx_path.name],
    }

    response_payload = {
        "job_id": job_id,
        "version": version,
        "resume_source": resume_source,
        "project_count": project_count,
        "score": judgement.get("score"),
        "summary": judgement.get("summary"),
        "docx_file": docx_path.name,
        "download_url": f"/download/{docx_path.name}",
        "all_versions": SESSIONS[job_id]["files"],
        "new_resume_text": resume_text,
        "diff_html": diff_html,
        "selected_projects": selected_project_names,
    }
    print("judgement-----", judgement)
    print("response_payload-----")
    print(JSONResponse(response_payload))
    return JSONResponse(response_payload)

@app.post("/regenerate/{job_id}")
def regenerate_resume(job_id: str):
    session = SESSIONS.get(job_id)
    if not session:
        raise HTTPException(status_code=404, detail="Unknown job_id")

    jd = session["jd"]
    company = session["company"]
    base_resume = session["base_resume"]
    project_count = session.get("project_count", 3)
    resume_source = session.get("resume_source", "redo")
    previous_state = {
        "jd_analysis": session.get("jd_analysis"),
        "selected_project_ids": session.get("selected_project_ids"),
    }
    projects = load_projects()

    resume_text, judgement, pipeline_state = run_pipeline_and_get_text(
        jd_text=jd,
        base_resume=base_resume,
        project_count=project_count,
        projects=projects,
        previous_state=previous_state,
        max_loops=3,
    )
    diff_html = make_side_by_side_diff_html(base_resume, resume_text)

    # initialize session state if missing (for backwards compatibility)
    session.setdefault("version", 1)
    session.setdefault("files", [])

    # increment version
    session["version"] += 1
    version = session["version"]

    docx_path = create_resume_docx(company, resume_text, version)

    selected_project_ids = pipeline_state.get("selected_project_ids", [])
    selected_projects_detail = pipeline_state.get("selected_projects", [])
    selected_project_names = _project_display_names(selected_projects_detail)

    session["files"].append(docx_path.name)
    session["jd_analysis"] = pipeline_state.get("jd_analysis", session.get("jd_analysis", ""))
    session["selected_project_ids"] = selected_project_ids

    response_payload = {
        "job_id": job_id,
        "version": version,
        "resume_source": resume_source,
        "project_count": project_count,
        "score": judgement.get("score"),
        "summary": judgement.get("summary"),
        "docx_file": docx_path.name,
        "download_url": f"/download/{docx_path.name}",
        "all_versions": session["files"],
        "new_resume_text": resume_text,
        "diff_html": diff_html,
        "selected_projects": selected_project_names,
    }
    print("judgement-----", judgement)
    print("response_payload-----")
    print(JSONResponse(response_payload))
    return JSONResponse(response_payload)

@app.get("/download/{filename}")
def download_file(filename: str):
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, filename=filename)
