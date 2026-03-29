"""Anthropic News blog scraper (via sitemap.xml).

Extracted from the original scraper.py with minimal changes.
"""

import re
from xml.etree import ElementTree

from bs4 import BeautifulSoup

from . import BaseSource, register_source


@register_source
class AnthropicNewsSource(BaseSource):
    id = "anthropic-news"
    name = "Anthropic News"

    sitemap_url = "https://www.anthropic.com/sitemap.xml"
    url_prefix = "https://www.anthropic.com/news/"

    def discover_urls(self) -> list[str]:
        """Get all news article URLs from sitemap.xml."""
        xml_text = self.fetch_page(self.sitemap_url)
        root = ElementTree.fromstring(xml_text)

        ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = []
        for loc in root.findall(".//s:loc", ns):
            url = loc.text.strip() if loc.text else ""
            if url.startswith(self.url_prefix):
                slug = url[len(self.url_prefix):].strip("/")
                if slug:
                    urls.append(url)
        return urls

    def extract_article(self, html: str, url: str) -> dict:
        """Extract article metadata and content from an article page."""
        soup = BeautifulSoup(html, "html.parser")

        h1 = soup.find("h1")
        title = h1.get_text(strip=True) if h1 else ""

        published_date = _extract_date(soup)

        content_parts = []
        article_el = soup.find("article")
        if not article_el:
            article_el = soup.find("main") or soup.body

        if article_el:
            for tag in article_el.find_all(["h1", "h2", "h3", "p", "li", "blockquote"]):
                text = tag.get_text(strip=True)
                if text and len(text) > 1:
                    content_parts.append(text)

        return {
            "url": url,
            "title": title,
            "published_date": published_date,
            "content": "\n\n".join(content_parts),
        }


def _extract_date(soup: BeautifulSoup) -> str:
    """Try to extract publication date from the page."""
    time_tag = soup.find("time")
    if time_tag:
        dt = time_tag.get("datetime", "") or time_tag.get_text(strip=True)
        if dt:
            return dt

    for meta_name in ("article:published_time", "og:article:published_time", "date"):
        meta = soup.find("meta", {"property": meta_name}) or soup.find("meta", {"name": meta_name})
        if meta and meta.get("content"):
            return meta["content"]

    text = soup.get_text()
    m = re.search(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4}", text)
    if m:
        return m.group(0)

    m = re.search(r"\d{4}-\d{2}-\d{2}", text)
    if m:
        return m.group(0)

    return ""
