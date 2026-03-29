"""Pluggable blog source scrapers.

Each source implements the Source protocol:
  - id: str
  - name: str
  - fetch_new(known_urls, max_articles, progress_callback) -> list[dict]
"""

from __future__ import annotations

import time
from typing import Protocol

import requests


class Source(Protocol):
    """Protocol for blog source scrapers."""

    id: str
    name: str

    def discover_urls(self) -> list[str]:
        """Discover all article URLs from this source."""
        ...

    def extract_article(self, html: str, url: str) -> dict:
        """Extract article data from a fetched HTML page."""
        ...

    def fetch_new(
        self,
        known_urls: set[str] | None = None,
        max_articles: int = 0,
        progress_callback=None,
    ) -> list[dict]:
        """Fetch new articles not in known_urls."""
        ...


class BaseSource:
    """Base implementation with common fetching logic."""

    id: str = ""
    name: str = ""
    request_headers: dict = {"User-Agent": "Claude-Blog-Follower/3.0"}
    request_timeout: int = 30
    request_delay: float = 1.0

    def fetch_page(self, url: str) -> str:
        resp = requests.get(url, headers=self.request_headers, timeout=self.request_timeout)
        resp.raise_for_status()
        return resp.text

    def discover_urls(self) -> list[str]:
        raise NotImplementedError

    def extract_article(self, html: str, url: str) -> dict:
        raise NotImplementedError

    def fetch_new(
        self,
        known_urls: set[str] | None = None,
        max_articles: int = 0,
        progress_callback=None,
    ) -> list[dict]:
        all_urls = self.discover_urls()

        if known_urls:
            new_urls = [u for u in all_urls if u not in known_urls]
        else:
            new_urls = all_urls

        if max_articles > 0:
            new_urls = new_urls[:max_articles]

        articles = []
        total = len(new_urls)

        for i, url in enumerate(new_urls):
            if progress_callback:
                progress_callback(i + 1, total)
            try:
                html = self.fetch_page(url)
                article = self.extract_article(html, url)
                if article.get("title"):
                    article["source_id"] = self.id
                    articles.append(article)
            except Exception as e:
                articles.append({
                    "url": url,
                    "title": f"[Error fetching: {e}]",
                    "published_date": "",
                    "content": "",
                    "source_id": self.id,
                })

            if i < total - 1:
                time.sleep(self.request_delay)

        return articles


# Source registry — import source modules to trigger @register_source
_REGISTRY: dict[str, type[BaseSource]] = {}
_MODULES_LOADED = False


def _ensure_loaded():
    """Lazy-import source modules to populate the registry."""
    global _MODULES_LOADED
    if _MODULES_LOADED:
        return
    from . import anthropic_news  # noqa: F401
    from . import anthropic_engineering  # noqa: F401
    _MODULES_LOADED = True


def register_source(cls: type[BaseSource]) -> type[BaseSource]:
    """Decorator to register a source class."""
    _REGISTRY[cls.id] = cls
    return cls


def get_source(source_id: str) -> BaseSource:
    """Get a source instance by ID."""
    _ensure_loaded()
    if source_id not in _REGISTRY:
        raise ValueError(f"Unknown source: {source_id}. Available: {list(_REGISTRY.keys())}")
    return _REGISTRY[source_id]()


def get_all_sources() -> dict[str, type[BaseSource]]:
    """Get all registered sources."""
    _ensure_loaded()
    return dict(_REGISTRY)
