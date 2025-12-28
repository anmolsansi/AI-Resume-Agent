from .agents import analyze_jd, rewrite_resume, judge_resume

def run_pipeline_and_get_text(jd_text: str, base_resume: str, max_loops: int = 2):
    jd_analysis = analyze_jd(jd_text)
    current_resume = base_resume
    last_judgement = None

    for _ in range(max_loops):
        improved = rewrite_resume(jd_analysis, current_resume)
        judgement = judge_resume(jd_text, improved)
        last_judgement = judgement
        score = judgement.get("score", 0)

        if score >= 8:
            return improved, last_judgement

        improvements = judgement.get("improvements", [])
        improvements_text = "\n".join(f"- {imp}" for imp in improvements)

        feedback_block = (
            f"\n\nAdditional feedback from recruiter:\n{improvements_text}\n"
            "Use this feedback to improve the resume further."
        )

        jd_analysis = jd_analysis + feedback_block
        current_resume = improved

    return current_resume, last_judgement or {
        "score": 0,
        "summary": "No judgement",
        "improvements": [],
    }
