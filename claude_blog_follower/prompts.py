"""Three-tier prompt loader.

Priority:
  1. User custom:   ~/.claude-blog-follower/prompts/<name>.md
  2. Project default: <project>/prompts/<name>.md
  3. Hardcoded fallback (empty string)
"""

from pathlib import Path

# Directories
_PROJECT_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_USER_PROMPTS_DIR = Path.home() / ".claude-blog-follower" / "prompts"


def load_prompt(name: str, **format_kwargs) -> str:
    """Load a prompt template by name and apply format variables.

    Searches for <name>.md in user dir first, then project dir.
    Template uses Python str.format() syntax with doubled braces
    for literal braces (e.g., {{ and }}).

    Args:
        name: Prompt name without extension (e.g., "analyze-article").
        **format_kwargs: Variables to substitute into the template.

    Returns:
        The formatted prompt string.
    """
    filename = f"{name}.md"

    # Tier 1: user custom
    user_path = _USER_PROMPTS_DIR / filename
    if user_path.exists():
        template = user_path.read_text(encoding="utf-8")
        return template.format(**format_kwargs) if format_kwargs else template

    # Tier 2: project default
    project_path = _PROJECT_PROMPTS_DIR / filename
    if project_path.exists():
        template = project_path.read_text(encoding="utf-8")
        return template.format(**format_kwargs) if format_kwargs else template

    # Tier 3: fallback
    return ""


def list_prompts() -> list[dict]:
    """List all available prompts with their source tier."""
    prompts = {}

    # Scan project prompts first
    if _PROJECT_PROMPTS_DIR.exists():
        for p in _PROJECT_PROMPTS_DIR.glob("*.md"):
            prompts[p.stem] = {"name": p.stem, "source": "project", "path": str(p)}

    # User prompts override
    if _USER_PROMPTS_DIR.exists():
        for p in _USER_PROMPTS_DIR.glob("*.md"):
            prompts[p.stem] = {"name": p.stem, "source": "user", "path": str(p)}

    return list(prompts.values())
