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
def generate_resume(
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
            docx_bytes = resume_file.read()
            base_resume_text = extract_text_from_docx_bytes(docx_bytes)
        else:
            resume_source = "master"
            base_resume_text = load_master_resume_text()
    else:
        # base_resume_text = (base_resume or "").strip()
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
    print("response_payload-----", response_payload)
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

if __name__ == "__main__":
    jd="""
    Software Engineer, Schemas & Object Framework
San Francisco, CA
Biotechnology is rewriting life as we know it, from the medicines we take, to the crops we grow, the materials we wear, and the household goods that we rely on every day. But moving at the new speed of science requires better technology.

Benchling’s mission is to unlock the power of biotechnology. The world’s most innovative biotech companies use Benchling’s R&D Cloud to power the development of breakthrough products and accelerate time to milestone and market. 

Come help us bring modern software to modern science.

ROLE OVERVIEW
As a software engineer on the Schemas and Object Framework team, you will design, build, and operate platform systems that are fundamental to how Benchling models complex science. Not only will your work enable Benchling to scale its product offerings and accelerate scientific discovery for our customers by providing a cohesive and extensible data modeling foundation, but you will also have the opportunity to help shape technical strategy and establish best practices for Benchling product and platform teams.

The richness and variety of our customers’ work means that Benchling cannot provide out-of-the-box support for all the concepts in biotech. So, the Schemas system enables our internal application teams to introduce new “schema types,” which are natively integrated with our platform. Our customers can then extend and customize these schema types to represent their unique science. As an engineer on the Schemas team, you will own the evolution of these customizable schemas, ensuring optimal handling of data “at rest” and shaping the data within Schemas to maintain data integrity and optimize the performance of the datastore that backs all data records in the Benchling Data Platform.

This team also owns the Object Framework which enables Benchling’s internal platform to be consistent by default by providing both a source of truth for the shape of Benchling domain models and also internal APIs for accessing them. Team members regularly define best practices for other platform and product teams to ensure modeling consistency, as well as define interfaces to adjacent systems that persist data and generate change events. 

RESPONSIBILITIES
Lead high-impact projects from design through to deployment and operation.
Work closely with product managers, designers, and other engineers across Platform and Applications teams to translate business needs into effective solutions.
Collaborate with technical leaders and teammates to contribute to team growth, drive improvements in engineering processes and tools, and foster a culture of excellence.
Improve the maintainability, consistency, scalability, and developer experience of high-impact internal data modeling APIs.
QUALIFICATIONS
You have 1+ years of experience in a fulltime software engineering role, backend or full stack. Ideally in SaaS with platform development experience.
Strong problem-solving skills with a proven ability to iterate on feedback and deliver high-impact solutions.
Proficiency in backend development, API design, data management. Experience in Web Application development is highly desirable.
Experience leading & delivering projects from start to finish, independently or as a part of a larger team.
Excellent interpersonal skills and experience working in a collaborative, cross-functional environment. Willing to work out of our SF office 3 days a week.
Enthusiasm for diving into complex technical challenges and a keen interest in the life sciences domain, with a willingness to learn and adapt.
HOW WE WORK
Flexible Hybrid Work: We offer a flexible hybrid work arrangement that prioritizes in-office collaboration. Employees are expected to be on-site 3 days per week (Monday, Tuesday, and Thursday).

SALARY RANGE
Benchling takes a market-based approach to pay.  The candidate's starting pay will be determined based on job-related skills, experience, qualifications, interview performance, and work location. For this role the base salary range is $129,938 to $190,906.

To help you determine which zone applies to your location, please see this resource. If you have questions regarding a specific location's zone designation, please contact a recruiter for additional information.

Total Compensation includes the following:
Competitive total rewards package
Broad range of medical, dental, and vision plans for employees and their dependents
Fertility healthcare and family-forming benefits
Four months of fully paid parental leave
401(k) + Employer Match
Commuter benefits for in-office employees and a generous home office set up stipend for remote employees
Mental health benefits, including therapy and coaching, for employees and their dependents
Monthly Wellness stipend
Learning and development stipend
Generous and flexible vacation
Company-wide Winter holiday shutdown
Sabbaticals for 5-year and 10-year anniversaries
#LI-Hybrid
#BI-Hybrid
#LI-KW1

Benchling welcomes everyone. 
We believe diversity enriches our team so we hire people with a wide range of identities, backgrounds, and experiences. 

We are an equal opportunity employer. That means we don’t discriminate on the basis of race, religion, color, national origin, gender, sexual orientation, age, marital status, veteran status, or disability status. We also consider for employment qualified applicants with arrest and conviction records, consistent with applicable federal, state and local law, including but not limited to the San Francisco Fair Chance Ordinance.
 

Please be aware that Benchling will never request personal information, payment, or sensitive details outside of Greenhouse or via email. All official communications will come from an @benchling.com email address or from an approved vendor alias. If you are contacted by someone claiming to represent Benchling and are unsure of their legitimacy, please reach out to us at recruiting-fraud-alert@benchling.com to verify the communication.
    """
    company="Bnech"

    generate_resume(jd=jd, company=company, project_count=3)