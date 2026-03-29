"""Generate HTML analysis report."""

import re
from datetime import datetime

import markdown
from jinja2 import Environment, FileSystemLoader

from . import config
from .utils import parse_json_field


def _md_to_html(text: str) -> str:
    """Convert markdown text to HTML."""
    try:
        return markdown.markdown(text)
    except Exception:
        # Fallback: basic conversion
        html = text.replace("\n\n", "</p><p>").replace("\n", "<br>")
        return f"<p>{html}</p>"


def _extract_year(date_str: str) -> str:
    """Extract year from various date formats."""
    if not date_str:
        return "Unknown"
    # Try ISO format
    m = re.search(r"(\d{4})", date_str)
    return m.group(1) if m else "Unknown"


def generate_report(articles: list, timeline_analysis: str = "") -> str:
    """Generate the full HTML report.

    Args:
        articles: List of sqlite3.Row or dict objects with article data.
        timeline_analysis: Markdown-formatted timeline analysis from AI.

    Returns:
        HTML string of the complete report.
    """
    env = Environment(loader=FileSystemLoader(str(config.TEMPLATE_DIR)))
    template = env.get_template("report.html")

    # Prepare article data with parsed JSON fields
    processed = []
    for a in articles:
        article = dict(a)
        article["key_tech_list"] = parse_json_field(article.get("key_tech", "[]"))
        article["key_viewpoints_list"] = parse_json_field(article.get("key_viewpoints", "[]"))
        processed.append(article)

    # Group by year
    year_groups = {}
    for article in processed:
        year = _extract_year(article.get("published_date", ""))
        year_groups.setdefault(year, []).append(article)

    # Sort years descending, articles within each year by date
    articles_by_year = sorted(year_groups.items(), key=lambda x: x[0], reverse=True)

    # Calculate stats
    years = [y for y in year_groups.keys() if y != "Unknown"]
    if years:
        year_span = f"{min(years)}-{max(years)}"
    else:
        year_span = "N/A"

    analyzed_count = sum(1 for a in processed if a.get("summary"))

    # Convert timeline analysis from markdown to HTML
    timeline_html = _md_to_html(timeline_analysis) if timeline_analysis else ""

    html = template.render(
        total_articles=len(processed),
        analyzed_articles=analyzed_count,
        year_span=year_span,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        timeline_analysis=timeline_html,
        articles_by_year=articles_by_year,
    )

    return html


def save_report(html: str, filename: str = "report.html") -> str:
    """Save HTML report to output directory. Returns the file path."""
    config.OUTPUT_DIR.mkdir(exist_ok=True)
    path = config.OUTPUT_DIR / filename
    path.write_text(html, encoding="utf-8")
    return str(path)
