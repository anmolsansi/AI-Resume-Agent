import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from .local_llm_client import analyze_jd_local
from .openrouter_client import OpenRouterClient

load_dotenv()

client = OpenRouterClient()

MISTRAL_MODEL = "xiaomi/mimo-v2-flash:free"
GROK_MODEL = "tngtech/deepseek-r1t2-chimera:free" #"mistralai/mistral-7b-instruct:free"   "x-ai/grok-4.1-fast:free"

BASE_DIR = Path(__file__).resolve().parent
STYLE_GUIDE_PATH = BASE_DIR / "style_guide.md"
FENCED_BLOCK_RE = re.compile(r"^```(?:[\w-]+)?\s*([\s\S]*?)\s*```$", re.DOTALL)


def _strip_markdown_fences(content: str) -> str:
    stripped = content.strip()
    match = FENCED_BLOCK_RE.match(stripped)
    if match:
        return match.group(1).strip()
    return stripped


def _format_projects_for_prompt(projects: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for idx, project in enumerate(projects, 1):
        name = project.get("name", project.get("id", f"Project {idx}"))
        intro = project.get("intro", "")
        bullets = "\n".join(f"  - {b}" for b in project.get("bullets", []))
        tech = ", ".join(project.get("tech_tags", []))
        domain = ", ".join(project.get("domain_tags", []))
        lines.append(
            f"{idx}. {name} (ID: {project.get('id', 'unknown')})\n"
            f"Intro: {intro}\n"
            f"Bullets:\n{bullets}\n"
            f"Tech tags: {tech}\n"
            f"Domain tags: {domain}"
        )
    return "\n\n".join(lines)


def _project_names_list(projects: List[Dict[str, Any]]) -> str:
    return ", ".join(project.get("name", project.get("id", "")) for project in projects if project)

def load_style_guide() -> str:
    if STYLE_GUIDE_PATH.exists():
        return STYLE_GUIDE_PATH.read_text()
    return (
        "# Style Guide\n"
        "- Use short, impact-focused bullet points.\n"
        "- Start bullets with strong verbs.\n"
        "- Include numbers and tech stack where possible.\n"
    )

def analyze_jd(jd_text: str) -> str:
    """
    Use the local model (via Ollama) to analyze the JD,
    but convert its JSON result into a text summary that
    we will feed to the rewrite step.
    """
    parsed = analyze_jd_local(jd_text)

    # Turn the structured JSON into a human-readable summary for Step 2
    summary_lines = []

    summary_lines.append("Must-have skills:")
    for s in parsed.get("must_have", []):
        summary_lines.append(f"- {s}")

    summary_lines.append("\nNice-to-have skills:")
    for s in parsed.get("nice_to_have", []):
        summary_lines.append(f"- {s}")

    summary_lines.append("\nTech stack:")
    for s in parsed.get("tech_stack", []):
        summary_lines.append(f"- {s}")

    summary_lines.append("\nResponsibilities:")
    for s in parsed.get("responsibilities", []):
        summary_lines.append(f"- {s}")

    summary_lines.append("\nImportant keywords:")
    for s in parsed.get("keywords", []):
        summary_lines.append(f"- {s}")

    return "\n".join(summary_lines)


def select_projects(
    jd_analysis: str,
    project_count: int,
    projects: List[Dict[str, Any]],
    feedback: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Choose the best projects for the resume based on JD analysis and inventory.
    Returns dict with selected_project_ids and reasons.
    """
    if not projects:
        return {"selected_project_ids": [], "reasons": []}

    inventory_text = _format_projects_for_prompt(projects)
    feedback_text = f"\n\nFeedback to address when selecting:\n{feedback}" if feedback else ""

    system_prompt = (
        "You are a resume project selector. Choose the most relevant projects for the job, "
        "balancing domain fit, tech overlap, and impact. Return only JSON."
    )
    user_prompt = (
        f"Job analysis summary:\n{jd_analysis}\n\n"
        f"Number of projects required: {project_count}\n"
        f"Available projects:\n{inventory_text}"
        f"{feedback_text}\n\n"
        "Respond in JSON with:\n"
        "{\n"
        '  "selected_project_ids": ["id1", "id2"],\n'
        '  "reasons": [{"id": "id1", "reason": "short justification"}]\n'
        "}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    raw = client.chat(MISTRAL_MODEL, messages, temperature=0.2, max_tokens=100000)
    clean = _strip_markdown_fences(raw)
    try:
        clean = clean.replace('\r', '').replace('\t', ' ')
        parsed = json.loads(clean)
    except json.JSONDecodeError:
        return {"selected_project_ids": [], "reasons": [], "raw": raw}

    selected_ids = parsed.get("selected_project_ids", [])
    reasons = parsed.get("reasons", [])
    return {
        "selected_project_ids": selected_ids,
        "reasons": reasons,
    }

# def analyze_jd_openrouter(jd_text: str) -> str:
#     messages = [
#         {
#             "role": "system",
#             "content": "You analyze job descriptions and extract core requirements."
#         },
#         {
#             "role": "user",
#             "content": (
#                 "Analyze this job description. Summarize:\n"
#                 "- must-have skills\n"
#                 "- nice-to-have skills\n"
#                 "- tech stack\n"
#                 "- core responsibilities\n"
#                 "- important keywords\n\n"
#                 f"JD:\n{jd_text}"
#             ),
#         },
#     ]
#     return client.chat(MISTRAL_MODEL, messages, temperature=0.1, max_tokens=700)

def rewrite_resume(
    jd_analysis: str,
    base_resume: str,
    selected_projects: List[Dict[str, Any]],
    project_count: int,
    feedback_notes: str = "",
) -> str:
    style_text = load_style_guide()
    user_template = os.getenv("PROMPT_REWRITE_USER_TEMPLATE")
    selected_text = _format_projects_for_prompt(selected_projects)
    guidance = (
        f"\n\nYou must include ONLY the following {len(selected_projects)} projects "
        f"in the rewritten resume. Do not mention other projects.\n{selected_text}\n"
        "Each project should have a short intro and impactful bullet points.\n"
    )
    if feedback_notes.strip():
        guidance += f"\nIncorporate this recruiter feedback:\n{feedback_notes.strip()}\n"
    guidance += (
        "\nEnsure the final resume highlights the selected projects explicitly and keeps all facts truthful."
    )
    msg_content = user_template.format(
                style_text=style_text,
                jd_analysis=jd_analysis + guidance,
                base_resume=base_resume,
            )
    messages = [
        {
            "role": "system",
            "content": (
                "You rewrite resumes to better match a job description. "
                "You follow the provided writing style but never invent fake experience."
            ),
        },
        {
            "role": "user",
            "content": msg_content,
        },
    ]
    res = client.chat(MISTRAL_MODEL, messages, temperature=0.3, max_tokens=100000)
    try:
        parsed = _strip_markdown_fences(res)
        parsed = parsed.replace('\r', '').replace('\t', ' ')
        return json.loads(parsed)
    except Exception as err:
        print(err)
        return json.loads(res)

def judge_resume(
    jd_text: str,
    new_resume: str,
    selected_projects: List[Dict[str, Any]],
    project_count: int,
    previous_agent_output: str
) -> dict:
    try:
        user_template = os.getenv("PROMPT_JUDGE_TEMPLATE")
        msg_content = user_template.format(
                    jd_text=jd_text,
                    new_resume=new_resume,
                )
        project_names = _project_names_list(selected_projects)
        project_guidance = (
            "\n\nProjects that MUST appear (and no others): "
            f"{project_names or 'None provided.'}\n"
            "Add a boolean field project_selection_issue: true if the resume chose the wrong projects, else false."
        )
        messages = [
            {
                "role": "system",
                "content": "You are a strict recruiter. You rate resume fit and give clear feedback."
            },
            {
                "role": "user",
                "content":  msg_content + project_guidance + "\n\n Previous agent response = " + previous_agent_output,
            },
        ]
        raw = client.chat(GROK_MODEL, messages, temperature=0.1, max_tokens=100000)
        clean = _strip_markdown_fences(raw)
        try:
            clean = clean.replace('\r', '').replace('\t', ' ')
            parsed = json.loads(clean)
        except json.JSONDecodeError:
            parsed = {
                "score": 0,
                "summary": "Could not parse JSON",
                "improvements": [raw],
            }
        parsed.setdefault("project_selection_issue", False)
        return parsed
    except Exception as e:
        print(e)
        return None