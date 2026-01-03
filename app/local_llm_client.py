import json
import os
import re
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

from .jd_schema import REQUIRED_KEYS, is_good_jd_analysis, normalize_jd_analysis
from .openrouter_client import OpenRouterClient

load_dotenv()

# URL for Ollama running locally
OLLAMA_URL = "http://localhost:11434/api/chat"
LOCAL_MODEL_NAME = "mistral"  # or another model you've pulled in Ollama
OPENROUTER_FALLBACK_MODEL = os.getenv("OPENROUTER_STEP1_MODEL", "mistralai/mistral-7b-instruct:free")
DEFAULT_ANALYZE_TEMPLATE = """You are a job description analyzer.
Read the job description and extract the following information.
Return ONLY valid JSON, no extra text.

The JSON format must be exactly:
{
  "must_have": ["skill1", "skill2"],
  "nice_to_have": ["skill"],
  "tech_stack": ["technology"],
  "responsibilities": ["sentence"],
  "keywords": ["word"]
}

Job description:
{jd_text}"""
STRICT_SYSTEM_PROMPT = (
    "You failed to provide valid JSON before. You MUST output strictly valid JSON matching "
    "the schema with double-quoted keys and values. Respond with JSON only."
)

_openrouter_client = OpenRouterClient()
FENCED_BLOCK_RE = re.compile(r"^```(?:[\w-]+)?\s*([\s\S]*?)\s*```$", re.DOTALL)


def _empty_analysis() -> Dict[str, List[str]]:
    return {key: [] for key in REQUIRED_KEYS}


def _call_ollama(messages: List[Dict[str, str]]) -> str:
    body = {
        "model": LOCAL_MODEL_NAME,
        "messages": messages,
        "stream": False,
    }
    response = requests.post(OLLAMA_URL, json=body, timeout=60)
    response.raise_for_status()
    data = response.json()
    return data["message"]["content"]


def _strip_markdown_fences(content: str) -> str:
    stripped = content.strip()
    match = FENCED_BLOCK_RE.match(stripped)
    if match:
        return match.group(1).strip()
    return stripped


def _parse_and_validate(content: str) -> Optional[Dict[str, List[str]]]:
    clean = _strip_markdown_fences(content)
    try:
        raw: Any = json.loads(clean)
    except json.JSONDecodeError:
        raw = {}

    normalized = normalize_jd_analysis(raw)
    if is_good_jd_analysis(normalized):
        return normalized
    return None


def _fallback_to_openrouter(jd_text: str) -> Dict[str, List[str]]:
    user_template = os.getenv("PROMPT_ANALYZE_JD_TEMPLATE", DEFAULT_ANALYZE_TEMPLATE)
    messages = [
        {
            "role": "system",
            "content": "You analyze job descriptions and respond with strict JSON using the provided schema.",
        },
        {"role": "user", "content": user_template.format(jd_text=jd_text)},
    ]
    try:
        content = _openrouter_client.chat(
            OPENROUTER_FALLBACK_MODEL,
            messages,
            temperature=0.1,
            max_tokens=700,
        )
        clean = _strip_markdown_fences(content)
        clean = clean.replace('\r', '').replace('\t', ' ')
        parsed = json.loads(clean)
    except (json.JSONDecodeError, requests.RequestException, RuntimeError):
        return _empty_analysis()

    normalized = normalize_jd_analysis(parsed)
    return normalized if is_good_jd_analysis(normalized) else normalized


def analyze_jd_local(jd_text: str) -> Dict[str, List[str]]:
    """
    Ask the local model (via Ollama) to analyze a job description and
    return a structured JSON dictionary. Retries with a stricter prompt and
    falls back to OpenRouter if validation fails.
    """
    user_template = os.getenv("PROMPT_ANALYZE_JD_TEMPLATE")

    attempts = [
        [
            {
                "role": "system",
                "content": "You analyze job descriptions and output ONLY strict JSON.",
            },
            {"role": "user", "content": user_template.format(jd_text=jd_text)},
        ],
        [
            {
                "role": "system",
                "content": STRICT_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": (
                    "You MUST respond with valid minified JSON that matches the schema exactly.\n"
                    + user_template.format(jd_text=jd_text)
                ),
            },
        ],
    ]

    for messages in attempts:
        try:
            content = _call_ollama(messages)
        except requests.RequestException:
            continue

        parsed = _parse_and_validate(content)
        if parsed:
            return parsed

    return _fallback_to_openrouter(jd_text)
