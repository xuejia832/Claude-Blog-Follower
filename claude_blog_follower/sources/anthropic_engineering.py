"""Anthropic Engineering blog scraper (via index page).

Scrapes the engineering blog index page for article links,
then extracts content from each article page.
"""

import re

from bs4 import BeautifulSoup

from . import BaseSource, register_source


@register_source
class AnthropicEngineeringSource(BaseSource):
    id = "anthropic-engineering"
    name = "Anthropic Engineering"

    index_url = "https://www.anthropic.com/engineering"
    url_prefix = "https://www.anthropic.com/research/"

    def discover_urls(self) -> list[str]:
        """Discover article URLs from the engineering index page."""
        html = self.fetch_page(self.index_url)
        soup = BeautifulSoup(html, "html.parser")

        urls = set()
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            # Normalize relative URLs
            if href.startswith("/research/"):
                href = f"https://www.anthropic.com{href}"
            if href.startswith(self.url_prefix):
                slug = href[len(self.url_prefix):].strip("/")
                if slug:
                    urls.add(href)

        return list(urls)

    def extract_article(self, html: str, url: str) -> dict:
        """Extract article data from an engineering blog page."""
        soup = BeautifulSoup(html, "html.parser")

        h1 = soup.find("h1")
        title = h1.get_text(strip=True) if h1 else ""

        published_date = self._extract_date(soup)

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

    def _extract_date(self, soup: BeautifulSoup) -> str:
        """Try to extract publication date."""
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
