"""
SindGreenMentor Desktop — janela nativa com interface premium.

Dev:  python desktop/launcher.py
Exe:  dist\\SindGreenMentor\\SindGreenMentor.exe
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
import threading
import time
import urllib.error
import urllib.request
from desktop.runtime import app_root, bundle_root, configure_environment

configure_environment()
from config.env import load_dotenv  # noqa: E402

_env_path = app_root() / ".env"
if not _env_path.exists():
    for _candidate in (app_root() / ".env.example", _ROOT / ".env.example", _ROOT / ".env"):
        if _candidate.exists():
            shutil.copy2(_candidate, _env_path)
            break
load_dotenv(_env_path)
if not (os.getenv("AUTH_USERNAME") or "").strip():
    os.environ.setdefault("AUTH_USERNAME", "admin")
if not (os.getenv("AUTH_PASSWORD") or "").strip():
    os.environ.setdefault("AUTH_PASSWORD", "admin123")
if not (os.getenv("AUTH_SECRET") or "").strip():
    os.environ.setdefault("AUTH_SECRET", "sgm-desktop-change-me")
os.environ["AUTH_ENABLED"] = "1"
os.environ.setdefault("DESKTOP_APP", "1")

DEFAULT_PORT = 8765
WINDOW_TITLE = "SindGreenMentor Pro"


def _pick_port(preferred: int = DEFAULT_PORT) -> int:
    for port in (preferred, preferred + 1, preferred + 2, 0):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(("127.0.0.1", port))
                return sock.getsockname()[1]
        except OSError:
            continue
    return preferred


def _load_branding() -> dict:
    for path in (bundle_root() / "web" / "branding.json", app_root() / "web" / "branding.json"):
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
    return {"app_name_full": WINDOW_TITLE, "tagline": "Análise inteligente de apostas"}


def _icon_path() -> str | None:
    for candidate in (
        bundle_root() / "web" / "static" / "icons" / "icon-512.jpg",
        app_root() / "web" / "static" / "icons" / "icon-512.jpg",
    ):
        if candidate.exists():
            return str(candidate)
    return None


def _start_server(port: int) -> None:
    import uvicorn

    uvicorn.run(
        "web.api.server:app",
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False,
    )


def _wait_for_server(port: int, timeout_sec: float = 45.0) -> bool:
    url = f"http://127.0.0.1:{port}/api/health"
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.5) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(0.35)
    return False


def main() -> int:
    try:
        import webview
    except ImportError:
        print("Instala dependências desktop: pip install -r requirements-desktop.txt")
        return 1

    branding = _load_branding()
    title = branding.get("app_name_full") or WINDOW_TITLE
    port = _pick_port(DEFAULT_PORT)

    server_thread = threading.Thread(target=_start_server, args=(port,), daemon=True)
    server_thread.start()
    _wait_for_server(port)

    splash = bundle_root() / "desktop" / "splash.html"
    if not splash.exists():
        splash = Path(__file__).resolve().parent / "splash.html"
    splash_url = splash.as_uri() + f"?port={port}"

    window = webview.create_window(
        title=title,
        url=splash_url,
        width=1320,
        height=880,
        min_size=(1024, 720),
        resizable=True,
        background_color="#040f0c",
        text_select=True,
    )

    def _navigate_when_ready() -> None:
        if _wait_for_server(port, timeout_sec=60):
            window.load_url(f"http://127.0.0.1:{port}/?desktop=1")

    threading.Thread(target=_navigate_when_ready, daemon=True).start()

    webview.start(gui="edgechromium", debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())