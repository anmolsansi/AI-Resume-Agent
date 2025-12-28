import json
from pathlib import Path
from .local_llm_client import analyze_jd_local

from .openrouter_client import OpenRouterClient

client = OpenRouterClient()

MISTRAL_MODEL = "mistralai/mistral-7b-instruct:free"
GROK_MODEL = "mistralai/mistral-7b-instruct:free"#"x-ai/grok-4.1-fast:free"

BASE_DIR = Path(__file__).resolve().parent
STYLE_GUIDE_PATH = BASE_DIR / "style_guide.md"

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

def analyze_jd_openrouter(jd_text: str) -> str:
    messages = [
        {
            "role": "system",
            "content": "You analyze job descriptions and extract core requirements."
        },
        {
            "role": "user",
            "content": (
                "Analyze this job description. Summarize:\n"
                "- must-have skills\n"
                "- nice-to-have skills\n"
                "- tech stack\n"
                "- core responsibilities\n"
                "- important keywords\n\n"
                f"JD:\n{jd_text}"
            ),
        },
    ]
    return client.chat(MISTRAL_MODEL, messages, temperature=0.1, max_tokens=700)

def rewrite_resume(jd_analysis: str, base_resume: str) -> str:
    style_text = load_style_guide()

    messages = [
        {
            "role": "system",
            "content": (
                "You rewrite resumes to better match a job. "
                "You follow the provided writing style but never invent fake experience."
            ),
        },
        {
            "role": "user",
            "content": (
                "Here is a resume writing style guide.\n"
                "It shows the tone and structure I want. "
                "Only copy the style, not the specific content.\n\n"
                f"{style_text}\n\n"
                "Here is the job analysis:\n"
                f"{jd_analysis}\n\n"
                "Here is my current resume:\n"
                f"{base_resume}\n\n"
                "Rewrite the resume to align with the job and follow the style guide. "
                "Keep all facts true. Do not copy any exact sentences from the style guide. "
                "Emphasize relevant skills and impact. Return only the full resume text."
            ),
        },
    ]
    return client.chat(MISTRAL_MODEL, messages, temperature=0.3, max_tokens=1400)

def judge_resume(jd_text: str, new_resume: str) -> dict:
    messages = [
        {
            "role": "system",
            "content": "You are a strict recruiter. You rate resume fit and give clear feedback."
        },
        {
            "role": "user",
            "content": (
                "Job description:\n"
                f"{jd_text}\n\n"
                "Resume:\n"
                f"{new_resume}\n\n"
                "Rate how well this resume fits the job on a scale from 1 to 10. "
                "If the score is below 8, list 3 to 5 specific improvements.\n\n"
                "Respond in JSON like this:\n"
                "{\n"
                '  "score": number,\n'
                '  "summary": "short text",\n'
                '  "improvements": ["bullet", "bullet"]\n'
                "}"
            ),
        },
    ]
    raw = client.chat(GROK_MODEL, messages, temperature=0.1, max_tokens=600)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"score": 0, "summary": "Could not parse JSON", "improvements": [raw]}
