"""Configuration for Claude Blog Follower.

Loads configuration from three layers:
  1. Defaults from config-schema.json
  2. Project config/config.json (if exists)
  3. User ~/.claude-blog-follower/config.json (if exists)
  4. Environment variables from .env (secrets only)
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── Paths ──────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "articles.db"
OUTPUT_DIR = PROJECT_ROOT / "output"
TEMPLATE_DIR = PROJECT_ROOT / "templates"
FEEDS_DIR = PROJECT_ROOT / "feeds"
PROMPTS_DIR = PROJECT_ROOT / "prompts"
CONFIG_DIR = PROJECT_ROOT / "config"
USER_DIR = Path.home() / ".claude-blog-follower"

# ── Secrets (from .env only) ───────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
EMAIL_TO = os.getenv("EMAIL_TO", "")
SERVERCHAN_KEY = os.getenv("SERVERCHAN_KEY", "")

# ── Scraping defaults (kept for backward compat) ──────────────────────
SITEMAP_URL = "https://www.anthropic.com/sitemap.xml"
NEWS_URL_PREFIX = "https://www.anthropic.com/news/"
REQUEST_HEADERS = {"User-Agent": "Claude-Blog-Follower/3.0"}
REQUEST_TIMEOUT = 30
REQUEST_DELAY = 1.0


def _load_schema_defaults() -> dict:
    """Extract default values from config-schema.json."""
    schema_path = CONFIG_DIR / "config-schema.json"
    if not schema_path.exists():
        return {}
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    defaults = {}
    for key, prop in schema.get("properties", {}).items():
        if prop.get("type") == "object":
            # For objects, merge top-level default with nested property defaults
            base = dict(prop.get("default", {}))
            for nk, np in prop.get("properties", {}).items():
                if "default" in np and nk not in base:
                    base[nk] = np["default"]
            if base:
                defaults[key] = base
        elif "default" in prop:
            defaults[key] = prop["default"]
    return defaults


def _load_json_file(path: Path) -> dict:
    """Load a JSON file, returning empty dict if not found."""
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def load_config() -> dict:
    """Load merged configuration from all layers."""
    cfg = _load_schema_defaults()

    # Layer 2: project config
    project_cfg = _load_json_file(CONFIG_DIR / "config.json")
    _deep_merge(cfg, project_cfg)

    # Layer 3: user config
    user_cfg = _load_json_file(USER_DIR / "config.json")
    _deep_merge(cfg, user_cfg)

    return cfg


def _deep_merge(base: dict, override: dict):
    """Merge override into base, in place."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def load_sources() -> list[dict]:
    """Load the blog sources registry."""
    data = _load_json_file(CONFIG_DIR / "default-sources.json")
    return data.get("sources", [])


def get_enabled_sources(cfg: dict | None = None) -> list[dict]:
    """Get enabled sources, filtered by user config if specified."""
    sources = load_sources()
    if cfg and cfg.get("sources"):
        allowed = set(cfg["sources"])
        sources = [s for s in sources if s["id"] in allowed]
    return [s for s in sources if s.get("enabled", True)]


def ensure_user_dir():
    """Create user config directory if it doesn't exist."""
    USER_DIR.mkdir(parents=True, exist_ok=True)
    (USER_DIR / "prompts").mkdir(exist_ok=True)


# ── Convenience: load config once at module level ──────────────────────
_config = load_config()

# Expose commonly used settings as module-level constants for backward compat
HAIKU_MODEL = _config.get("analysis", {}).get("model", "claude-haiku-4-5-20251001")
SONNET_MODEL = _config.get("analysis", {}).get("timeline_model", "claude-sonnet-4-5-20241022")
MAX_CONTENT_LENGTH = _config.get("analysis", {}).get("max_content_length", 15000)
DEFAULT_DISPLAY_COUNT = _config.get("display_count", 20)
LANGUAGE = _config.get("language", "zh")
DELIVERY_METHOD = _config.get("delivery", {}).get("method", "stdout")
