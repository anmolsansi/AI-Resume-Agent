import json
from pathlib import Path
from typing import Any, Dict, List

BASE_DIR = Path(__file__).resolve().parent
PROJECTS_PATH = BASE_DIR / "projects.json"


def load_projects() -> List[Dict[str, Any]]:
    if not PROJECTS_PATH.exists():
        return []
    with PROJECTS_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)
