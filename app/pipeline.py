from typing import Any, Dict, List, Optional, Tuple

from .agents import (
    analyze_jd,
    judge_resume,
    rewrite_resume,
    select_projects,
)


def _project_lookup(projects: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {proj.get("id"): proj for proj in projects if proj.get("id")}


def _filter_projects(
    lookup: Dict[str, Dict[str, Any]],
    project_ids: Optional[List[str]],
    fallback_count: int,
) -> List[Dict[str, Any]]:
    if not project_ids:
        return []
    filtered = [lookup[pid] for pid in project_ids if pid in lookup]
    if filtered:
        return filtered
    # fallback to first N projects if provided ids invalid
    return list(lookup.values())[:fallback_count]


def _ensure_projects_available(
    projects: List[Dict[str, Any]],
    project_count: int,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    limited = projects[:project_count]
    return limited, [p.get("id") for p in limited if p.get("id")]


def _pad_projects(
    selected_projects: List[Dict[str, Any]],
    projects: List[Dict[str, Any]],
    project_count: int,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    existing_ids = {p.get("id") for p in selected_projects if p.get("id")}
    padded = list(selected_projects)
    for project in projects:
        if len(padded) >= project_count:
            break
        pid = project.get("id")
        if not pid or pid in existing_ids:
            continue
        padded.append(project)
        existing_ids.add(pid)
    return padded, [p.get("id") for p in padded if p.get("id")]


def run_pipeline_and_get_text(
    jd_text: str,
    base_resume: str,
    project_count: int,
    projects: List[Dict[str, Any]],
    previous_state: Optional[Dict[str, Any]] = None,
    max_loops: int = 5,
) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
    lookup = _project_lookup(projects)
    jd_analysis = (previous_state or {}).get("jd_analysis")
    if not jd_analysis:
        jd_analysis = analyze_jd(jd_text)

    selected_project_ids = (previous_state or {}).get("selected_project_ids") or []
    selected_projects = _filter_projects(lookup, selected_project_ids, project_count)

    if not selected_projects:
        selection_result = select_projects(jd_analysis, project_count, projects)
        selected_project_ids = selection_result.get("selected_project_ids", [])
        selected_projects = _filter_projects(lookup, selected_project_ids, project_count)

    if not selected_projects:
        selected_projects, selected_project_ids = _ensure_projects_available(projects, project_count)
    else:
        selected_projects, selected_project_ids = _pad_projects(selected_projects, projects, project_count)

    current_resume = base_resume
    last_judgement: Optional[Dict[str, Any]] = None
    feedback_notes = ""

    for _ in range(max_loops):
        improved = rewrite_resume(
            jd_analysis=jd_analysis,
            base_resume=current_resume,
            selected_projects=selected_projects,
            project_count=project_count,
            feedback_notes=feedback_notes,
        )

        print("improved--pipeline.py:    ", improved)

        judgement = judge_resume(
            jd_text=jd_text,
            new_resume=improved,
            selected_projects=selected_projects,
            project_count=project_count,
        )

        print("Judgement--pipeline.py:    ",judgement)
        last_judgement = judgement
        score = judgement.get("score", 0)
        project_issue = judgement.get("project_selection_issue", False)

        if score >= 8 and not project_issue:
            state = {
                "jd_analysis": jd_analysis,
                "selected_project_ids": [p.get("id") for p in selected_projects if p.get("id")],
                "selected_projects": selected_projects,
            }
            return improved, judgement, state

        improvements = judgement.get("improvements", []) or []

        if project_issue:
            selection_feedback = judgement.get("summary", "")
            if improvements:
                selection_feedback += "\n" + "\n".join(improvements)
            selection_result = select_projects(jd_analysis, project_count, projects, feedback=selection_feedback)
            selected_project_ids = selection_result.get("selected_project_ids", [])
            selected_projects = _filter_projects(lookup, selected_project_ids, project_count)
            if not selected_projects:
                selected_projects, selected_project_ids = _ensure_projects_available(projects, project_count)
            else:
                selected_projects, selected_project_ids = _pad_projects(selected_projects, projects, project_count)
            current_resume = base_resume
            feedback_notes = ""
            continue

        if improvements:
            formatted = "\n".join(f"- {imp}" for imp in improvements)
            feedback_notes = (feedback_notes + "\n" + formatted).strip()
        current_resume = improved

    fallback_state = {
        "jd_analysis": jd_analysis,
        "selected_project_ids": [p.get("id") for p in selected_projects if p.get("id")],
        "selected_projects": selected_projects,
    }
    return (
        current_resume,
        last_judgement
        or {"score": 0, "summary": "No judgement", "improvements": [], "project_selection_issue": False},
        fallback_state,
    )
