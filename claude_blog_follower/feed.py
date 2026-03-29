"""Feed pipeline: generate feeds from sources and assemble digest input.

Inspired by follow-builders' prepare-digest.js pattern:
  1. generate_feed() — fetch from all sources, write intermediate JSON
  2. prepare_digest() — assemble feeds + prompts + config into one blob
"""

import json
from datetime import datetime

from . import config
from .prompts import load_prompt
from .sources import get_source
from .storage import get_existing_urls, save_article


def generate_feed(
    source_configs: list[dict],
    max_articles: int = 0,
    progress_callback=None,
) -> dict:
    """Run all enabled sources and generate feed JSON files.

    Args:
        source_configs: List of source config dicts from default-sources.json.
        max_articles: Max articles per source (0 = unlimited).
        progress_callback: Called with (source_name, current, total).

    Returns:
        Summary dict with per-source stats.
    """
    config.FEEDS_DIR.mkdir(exist_ok=True)
    summary = {"generated_at": datetime.now().isoformat(), "sources": {}}

    for src_cfg in source_configs:
        source_id = src_cfg["id"]
        scraper_id = src_cfg.get("scraper", source_id)

        try:
            source = get_source(scraper_id)
        except ValueError:
            summary["sources"][source_id] = {"error": f"Unknown scraper: {scraper_id}"}
            continue

        # Get known URLs for this source
        known_urls = get_existing_urls(source_id)

        # Fetch new articles
        articles = source.fetch_new(
            known_urls=known_urls,
            max_articles=max_articles,
            progress_callback=progress_callback,
        )

        # Save to SQLite
        new_count = 0
        for article in articles:
            saved = save_article(
                url=article["url"],
                title=article["title"],
                published_date=article.get("published_date", ""),
                content=article.get("content", ""),
                source_id=source_id,
            )
            if saved:
                new_count += 1

        # Write feed JSON
        feed_data = {
            "generated_at": datetime.now().isoformat(),
            "source": source_id,
            "source_name": source.name,
            "articles": articles,
            "stats": {
                "total_discovered": len(articles) + len(known_urls),
                "new_fetched": len(articles),
                "new_saved": new_count,
            },
        }

        feed_path = config.FEEDS_DIR / f"feed-{source_id}.json"
        feed_path.write_text(
            json.dumps(feed_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        summary["sources"][source_id] = feed_data["stats"]

    return summary


def prepare_digest(cfg: dict | None = None) -> dict:
    """Assemble everything the analyzer needs into one JSON blob.

    Reads existing feed files + prompts + config, producing a single
    dict that can be passed to the analyzer without any further I/O.

    Returns:
        Dict with keys: config, articles, prompts, stats.
    """
    if cfg is None:
        cfg = config.load_config()

    # Collect articles from all feed files
    all_articles = []
    source_stats = {}

    if config.FEEDS_DIR.exists():
        for feed_file in config.FEEDS_DIR.glob("feed-*.json"):
            try:
                feed_data = json.loads(feed_file.read_text(encoding="utf-8"))
                articles = feed_data.get("articles", [])
                all_articles.extend(articles)
                source_stats[feed_data.get("source", "unknown")] = {
                    "article_count": len(articles),
                }
            except (json.JSONDecodeError, KeyError):
                continue

    # Load prompts
    prompts = {
        "analyze_article": load_prompt("analyze-article"),
        "timeline_analysis": load_prompt("timeline-analysis"),
        "translate": load_prompt("translate"),
    }

    return {
        "status": "ok",
        "generated_at": datetime.now().isoformat(),
        "config": {
            "language": cfg.get("language", "zh"),
            "model": cfg.get("analysis", {}).get("model", config.HAIKU_MODEL),
            "timeline_model": cfg.get("analysis", {}).get("timeline_model", config.SONNET_MODEL),
            "max_content_length": cfg.get("analysis", {}).get("max_content_length", config.MAX_CONTENT_LENGTH),
        },
        "articles": all_articles,
        "prompts": prompts,
        "stats": {
            "total_articles": len(all_articles),
            "source_breakdown": source_stats,
        },
    }
