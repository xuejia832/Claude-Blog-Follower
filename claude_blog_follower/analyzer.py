"""AI-powered content analysis using Anthropic SDK."""

import json

import anthropic

from . import config
from .prompts import load_prompt
from .utils import extract_json_from_response, truncate_content


def _get_client() -> anthropic.Anthropic:
    """Create Anthropic client with configured API key."""
    if not config.ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set. Add it to your .env file."
        )
    return anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)


def _call_api(prompt: str, model: str | None = None) -> str:
    """Call Anthropic API and return the response text."""
    client = _get_client()
    model = model or config.HAIKU_MODEL

    message = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def analyze_article(title: str, date: str, content: str) -> dict:
    """Analyze a single article using Anthropic SDK.

    Returns dict with keys: summary, key_tech, key_viewpoints.
    """
    content = truncate_content(content, config.MAX_CONTENT_LENGTH)

    prompt = load_prompt("analyze-article", title=title, date=date, content=content)
    if not prompt:
        # Fallback if prompt file is missing
        return {"summary": "", "key_tech": [], "key_viewpoints": []}

    response_text = _call_api(prompt, model=config.HAIKU_MODEL)

    # Parse JSON from response
    try:
        json_text = extract_json_from_response(response_text)
        result = json.loads(json_text)
    except json.JSONDecodeError:
        result = {
            "summary": response_text[:500],
            "key_tech": [],
            "key_viewpoints": [],
        }

    return {
        "summary": result.get("summary", ""),
        "key_tech": result.get("key_tech", []),
        "key_viewpoints": result.get("key_viewpoints", []),
    }


def generate_timeline_analysis(articles: list[dict]) -> str:
    """Generate a comprehensive timeline analysis using Anthropic SDK.

    Args:
        articles: List of dicts with title, published_date, summary.

    Returns:
        Markdown-formatted analysis report.
    """
    lines = []
    for a in articles:
        date = a.get("published_date", "unknown")
        title = a.get("title", "")
        summary = a.get("summary", "")
        lines.append(f"- [{date}] {title}: {summary}")

    articles_summary = "\n".join(lines)
    articles_summary = truncate_content(articles_summary, 80000)

    prompt = load_prompt("timeline-analysis", articles_summary=articles_summary)
    if not prompt:
        return ""

    return _call_api(prompt, model=config.SONNET_MODEL)
