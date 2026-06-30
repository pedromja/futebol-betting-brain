"""Servidor de desenvolvimento com auth — mantém-se activo."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

os.environ.setdefault("AUTH_ENABLED", "1")
os.environ.setdefault("AUTH_USERNAME", "admin")
os.environ.setdefault("AUTH_PASSWORD", "testadmin123")
os.environ.setdefault("DATA_DIR", str(ROOT / "data"))
# Secret: .env do projeto (mesmas contas que desktop se copiares data/)
from config.env import load_dotenv

load_dotenv(ROOT / ".env")
if not (os.getenv("AUTH_SECRET") or "").strip():
    os.environ.setdefault("AUTH_SECRET", "live-test-secret-2026")

import uvicorn

if __name__ == "__main__":
    print("http://127.0.0.1:18765 — UI web actualizada (web/static)")
    print("Contas: ver .env e data/auth_users.json")
    uvicorn.run(
        "web.api.server:app",
        host="127.0.0.1",
        port=18765,
        log_level="warning",
    )