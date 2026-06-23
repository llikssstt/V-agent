import os
from pathlib import Path


def load_env_file(start_dir=None):
    if os.getenv("DISABLE_DOTENV_LOAD") == "1":
        return []

    base = Path(start_dir or __file__).resolve()
    candidates = [
        base.parents[1] / ".env",
        base.parents[2] / ".env",
    ]
    loaded = []
    for path in candidates:
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
                loaded.append(key)
    return loaded
