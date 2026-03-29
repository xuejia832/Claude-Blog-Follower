"""Scrape articles from Anthropic's website via sitemap and HTML parsing."""

import re
import time
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup

from . import config


def fetch_page(url: str) -> str:
    resp = requests.get(url, headers=config.REQUEST_HEADERS, timeout=config.REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.text


def discover_article_urls() -> list[str]:
    """Get all news article URLs from sitemap.xml."""
    xml_text = fetch_page(config.SITEMAP_URL)
    root = ElementTree.fromstring(xml_text)

    # sitemap uses namespace
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = []
    for loc in root.findall(".//s:loc", ns):
        url = loc.text.strip() if loc.text else ""
        if url.startswith(config.NEWS_URL_PREFIX):
            # Skip the listing page itself
            slug = url[len(config.NEWS_URL_PREFIX):].strip("/")
            if slug:
                urls.append(url)

    return urls


def extract_article(html: str, url: str) -> dict:
    """Extract article metadata and content from an article page."""
    soup = BeautifulSoup(html, "html.parser")

    # Title: first <h1>
    h1 = soup.find("h1")
    title = h1.get_text(strip=True) if h1 else ""

    # Date: look for common date patterns near the top
    published_date = _extract_date(soup)

    # Content: collect text from main content area
    content_parts = []
    # Try to find the main article body - look for <article> or main content div
    article_el = soup.find("article")
    if not article_el:
        # Fallback: get content after h1
        article_el = soup.find("main") or soup.body

    if article_el:
        for tag in article_el.find_all(["h1", "h2", "h3", "p", "li", "blockquote"]):
            text = tag.get_text(strip=True)
            if text and len(text) > 1:
                content_parts.append(text)

    content = "\n\n".join(content_parts)

    return {
        "url": url,
        "title": title,
        "published_date": published_date,
        "content": content,
    }


def _extract_date(soup: BeautifulSoup) -> str:
    """Try to extract publication date from the page."""
    # Look for <time> tag
    time_tag = soup.find("time")
    if time_tag:
        dt = time_tag.get("datetime", "") or time_tag.get_text(strip=True)
        if dt:
            return dt

    # Look for meta tags
    for meta_name in ("article:published_time", "og:article:published_time", "date"):
        meta = soup.find("meta", {"property": meta_name}) or soup.find("meta", {"name": meta_name})
        if meta and meta.get("content"):
            return meta["content"]

    # Fallback: regex for date patterns like "Mar 24, 2026" or "2026-03-24"
    text = soup.get_text()
    # Match "Month DD, YYYY"
    m = re.search(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4}", text)
    if m:
        return m.group(0)

    # Match ISO date
    m = re.search(r"\d{4}-\d{2}-\d{2}", text)
    if m:
        return m.group(0)

    return ""


def fetch_all_articles(existing_urls: set[str] | None = None, progress_callback=None) -> list[dict]:
    """Fetch all articles, skipping already-known URLs.

    Args:
        existing_urls: Set of URLs already in the database (skip these).
        progress_callback: Called with (current, total) for progress reporting.

    Returns:
        List of article dicts with url, title, published_date, content.
    """
    all_urls = discover_article_urls()

    if existing_urls:
        new_urls = [u for u in all_urls if u not in existing_urls]
    else:
        new_urls = all_urls

    articles = []
    total = len(new_urls)

    for i, url in enumerate(new_urls):
        if progress_callback:
            progress_callback(i + 1, total)

        try:
            html = fetch_page(url)
            article = extract_article(html, url)
            if article["title"]:
                articles.append(article)
        except Exception as e:
            # Log but continue
            articles.append({
                "url": url,
                "title": f"[Error fetching: {e}]",
                "published_date": "",
                "content": "",
            })

        # Be polite
        if i < total - 1:
            time.sleep(config.REQUEST_DELAY)

    return articles
