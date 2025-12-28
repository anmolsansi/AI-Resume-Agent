import json
from pathlib import Path
import os
from dotenv import load_dotenv
load_dotenv()
import requests

# URL for Ollama running locally
OLLAMA_URL = "http://localhost:11434/api/chat"
LOCAL_MODEL_NAME = "mistral"  # or another model you've pulled in Ollama

def analyze_jd_local(jd_text: str) -> dict:
    """
    Ask the local model (via Ollama) to analyze a job description and
    return a structured JSON dictionary.
    """
    user_template = os.getenv("PROMPT_ANALYZE_JD_TEMPLATE")
    body = {
        "model": LOCAL_MODEL_NAME,
        "messages": [
            {"role": "system", "content": "You output only strict JSON."},
            {"role": "user", "content": user_template.format(jd_text=jd_text)},
        ],
        "stream": False,
    }

    response = requests.post(OLLAMA_URL, json=body, timeout=60)
    response.raise_for_status()
    data = response.json()

    # Ollama returns something like: {"message": {"content": "..."}, ...}
    content = data["message"]["content"]

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        # If the model did not return valid JSON, fallback to an empty structure
        parsed = {
            "must_have": [],
            "nice_to_have": [],
            "tech_stack": [],
            "responsibilities": [],
            "keywords": [],
        }

    # Ensure all keys exist
    for key in ["must_have", "nice_to_have", "tech_stack", "responsibilities", "keywords"]:
        parsed.setdefault(key, [])

    return parsed
