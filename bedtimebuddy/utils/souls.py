from pathlib import Path

from bedtimebuddy.config import get_settings


def load_soul(*names: str) -> str:
    """Load and concatenate SOUL markdown files."""
    souls_path = get_settings().souls_path
    parts: list[str] = []
    for name in names:
        path = souls_path / name
        if path.exists():
            parts.append(path.read_text(encoding="utf-8").strip())
    return "\n\n---\n\n".join(parts)


def load_bedtime_souls() -> str:
    return load_soul("_shared-safety.md", "bedtime-brain.md", "bedtime-story.md")


def load_story_souls() -> str:
    return load_soul("_shared-safety.md", "bedtime-story.md")
