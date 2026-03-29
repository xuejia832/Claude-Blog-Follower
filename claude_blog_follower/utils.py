"""Shared utility functions."""

import json


def parse_json_field(value: str) -> list[str]:
    """Safely parse a JSON string field to list."""
    if not value:
        return []
    try:
        result = json.loads(value)
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def truncate_content(text: str, max_length: int = 15000) -> str:
    """Truncate text to max_length with a marker."""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "\n\n[... 内容已截断 ...]"


def extract_json_from_response(text: str) -> str:
    """Extract JSON from a response that may contain markdown code blocks."""
    if "```" in text:
        parts = text.split("```")
        if len(parts) >= 2:
            json_text = parts[1]
            if json_text.startswith("json"):
                json_text = json_text[4:]
            return json_text.strip()
    return text
