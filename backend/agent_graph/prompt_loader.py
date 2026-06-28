from functools import lru_cache
from pathlib import Path


PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"


@lru_cache(maxsize=16)
def load_prompt(name):
    path = (PROMPT_DIR / name).resolve()
    try:
        path.relative_to(PROMPT_DIR.resolve())
    except ValueError as exc:
        raise ValueError(f"invalid prompt name: {name}") from exc
    if path.suffix != ".md":
        raise ValueError(f"prompt must be a markdown file: {name}")
    return path.read_text(encoding="utf-8")
