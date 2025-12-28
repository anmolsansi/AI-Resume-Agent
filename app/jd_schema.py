from __future__ import annotations

from typing import Any, Dict, List


REQUIRED_KEYS = ["must_have", "nice_to_have", "tech_stack", "responsibilities", "keywords"]


def _to_list_of_strings(value: Any) -> List[str]:
    """
    Converts unknown model output into a clean list[str].
    - If it's a string, tries to split on commas/newlines.
    - If it's a list, keeps only string items.
    - Otherwise returns [].
    """
    if value is None:
        return []

    if isinstance(value, str):
        # Split on newlines or commas, keep meaningful tokens
        parts = []
        for chunk in value.replace(",", "\n").split("\n"):
            s = chunk.strip()
            if s:
                parts.append(s)
        return parts

    if isinstance(value, list):
        out = []
        for item in value:
            if isinstance(item, str):
                s = item.strip()
                if s:
                    out.append(s)
        return out

    return []


def normalize_jd_analysis(raw: Any) -> Dict[str, List[str]]:
    """
    Guarantees schema:
    {
      "must_have": [...],
      "nice_to_have": [...],
      "tech_stack": [...],
      "responsibilities": [...],
      "keywords": [...]
    }
    Deduplicates and trims.
    """
    if not isinstance(raw, dict):
        raw = {}

    normalized: Dict[str, List[str]] = {}

    for key in REQUIRED_KEYS:
        normalized[key] = _to_list_of_strings(raw.get(key))

    # Deduplicate while preserving order
    for key in REQUIRED_KEYS:
        seen = set()
        cleaned = []
        for item in normalized[key]:
            lower = item.lower()
            if lower not in seen:
                seen.add(lower)
                cleaned.append(item)
        normalized[key] = cleaned

    return normalized


def is_good_jd_analysis(parsed: Dict[str, List[str]]) -> bool:
    """
    Basic quality check: schema correct and not empty.
    You can tune this later.
    """
    if not isinstance(parsed, dict):
        return False
    for key in REQUIRED_KEYS:
        if key not in parsed or not isinstance(parsed[key], list):
            return False

    total_items = sum(len(parsed[k]) for k in REQUIRED_KEYS)
    if total_items < 5:
        return False

    if len(parsed["must_have"]) >= 3:
        return True
    if len(parsed["keywords"]) >= 8:
        return True
    if len(parsed["tech_stack"]) >= 3:
        return True
    return False
