"""SQLite storage for articles."""

import json
import sqlite3
from datetime import datetime

from . import config


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            published_date TEXT DEFAULT '',
            content TEXT DEFAULT '',
            summary TEXT DEFAULT '',
            key_tech TEXT DEFAULT '[]',
            key_viewpoints TEXT DEFAULT '[]',
            fetched_at TEXT NOT NULL,
            analyzed_at TEXT DEFAULT '',
            source_id TEXT DEFAULT 'anthropic-news'
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_published ON articles(published_date)")
    # Migrate: add source_id column if table already exists without it
    try:
        conn.execute("ALTER TABLE articles ADD COLUMN source_id TEXT DEFAULT 'anthropic-news'")
    except sqlite3.OperationalError:
        pass  # Column already exists
    conn.execute("CREATE INDEX IF NOT EXISTS idx_source ON articles(source_id)")
    conn.commit()
    conn.close()


def save_article(url: str, title: str, published_date: str = "",
                 content: str = "", source_id: str = "anthropic-news") -> bool:
    """Save an article. Returns True if newly inserted, False if already exists."""
    conn = get_db()
    cursor = conn.execute(
        "INSERT OR IGNORE INTO articles (url, title, published_date, content, fetched_at, source_id) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (url, title, published_date, content, datetime.now().isoformat(), source_id),
    )
    inserted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return inserted


def save_analysis(article_id: int, summary: str, key_tech: list[str],
                  key_viewpoints: list[str]):
    """Save AI analysis results for an article."""
    conn = get_db()
    conn.execute(
        "UPDATE articles SET summary = ?, key_tech = ?, key_viewpoints = ?, analyzed_at = ? "
        "WHERE id = ?",
        (summary, json.dumps(key_tech, ensure_ascii=False),
         json.dumps(key_viewpoints, ensure_ascii=False),
         datetime.now().isoformat(), article_id),
    )
    conn.commit()
    conn.close()


def get_existing_urls(source_id: str = "") -> set[str]:
    conn = get_db()
    if source_id:
        rows = conn.execute("SELECT url FROM articles WHERE source_id = ?", (source_id,)).fetchall()
    else:
        rows = conn.execute("SELECT url FROM articles").fetchall()
    conn.close()
    return {row["url"] for row in rows}


def get_unanalyzed_articles() -> list[sqlite3.Row]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM articles WHERE analyzed_at = '' OR analyzed_at IS NULL "
        "ORDER BY published_date"
    ).fetchall()
    conn.close()
    return rows


def get_all_articles(limit: int = 0) -> list[sqlite3.Row]:
    conn = get_db()
    sql = "SELECT * FROM articles ORDER BY published_date DESC"
    if limit > 0:
        sql += f" LIMIT {limit}"
    rows = conn.execute(sql).fetchall()
    conn.close()
    return rows


def get_analyzed_articles() -> list[sqlite3.Row]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM articles WHERE analyzed_at != '' AND analyzed_at IS NOT NULL "
        "ORDER BY published_date"
    ).fetchall()
    conn.close()
    return rows


def get_articles_since(since_date: str) -> list[sqlite3.Row]:
    """Get articles fetched after a given ISO date string."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM articles WHERE fetched_at > ? ORDER BY published_date",
        (since_date,),
    ).fetchall()
    conn.close()
    return rows


def get_article_count() -> int:
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    conn.close()
    return count


def get_analyzed_count() -> int:
    conn = get_db()
    count = conn.execute(
        "SELECT COUNT(*) FROM articles WHERE analyzed_at != '' AND analyzed_at IS NOT NULL"
    ).fetchone()[0]
    conn.close()
    return count
