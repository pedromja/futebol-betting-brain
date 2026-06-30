"""Arranca servidor PWA (web/static ao vivo) na porta 8765."""
from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from config.env import load_dotenv

load_dotenv(ROOT / ".env")
os.environ.setdefault("AUTH_ENABLED", "1")


def _lan_ip() -> str | None:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except OSError:
        return None


def main() -> None:
    port = 8765
    ip = _lan_ip()
    print("")
    print("  SindGreenMentor — servidor WEB (web/static ao vivo)")
    print(f"  PC:        http://127.0.0.1:{port}/")
    if ip:
        print(f"  Telemóvel: http://{ip}:{port}/")
    print("  Ctrl+C para parar")
    print("")

    import uvicorn

    uvicorn.run(
        "web.api.server:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()