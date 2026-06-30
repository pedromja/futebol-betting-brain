"""Carrega variáveis de .env (sem dependências extra)."""

import os
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def _default_root() -> Path:
    override = os.getenv("APP_ROOT", "").strip()
    return Path(override) if override else _ROOT


def load_dotenv(path: Path | None = None) -> None:
    env_path = path or _default_root() / ".env"
    if not env_path.exists():
        return
    try:
        text = env_path.read_text(encoding="utf-8")
    except OSError:
        return
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value