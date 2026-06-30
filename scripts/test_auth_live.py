"""Teste ao vivo do fluxo registo → aprovação admin."""
from __future__ import annotations

import json
import os
import shutil
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PORT = 18765
BASE = f"http://127.0.0.1:{PORT}"
DATA_DIR = ROOT / "data" / "auth_live_test"


def _req(method: str, path: str, body: dict | None = None, token: str | None = None):
    data = None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = resp.read().decode("utf-8")
            return resp.status, json.loads(payload) if payload else {}
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8")
        try:
            parsed = json.loads(payload) if payload else {}
        except json.JSONDecodeError:
            parsed = {"raw": payload}
        return exc.code, parsed


def _wait_health(timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{BASE}/api/health", timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.3)
    return False


def _start_server() -> None:
    import uvicorn

    uvicorn.run(
        "web.api.server:app",
        host="127.0.0.1",
        port=PORT,
        log_level="error",
        access_log=False,
    )


def main() -> int:
    if DATA_DIR.exists():
        shutil.rmtree(DATA_DIR)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    os.environ["AUTH_ENABLED"] = "1"
    os.environ["AUTH_USERNAME"] = "admin"
    os.environ["AUTH_PASSWORD"] = "testadmin123"
    os.environ["AUTH_SECRET"] = "live-test-secret-2026"
    os.environ["DATA_DIR"] = str(DATA_DIR)

    thread = threading.Thread(target=_start_server, daemon=True)
    thread.start()
    if not _wait_health():
        print("FAIL: servidor não arrancou")
        return 1

    print("OK: servidor em", BASE)

    code, reg = _req("POST", "/api/auth/register", {"username": "joao", "password": "pass1234"})
    assert code == 200 and reg.get("status") == "pending", (code, reg)
    print("OK: registo pendente ->", reg.get("message"))

    code, login_pending = _req("POST", "/api/auth/login", {"username": "joao", "password": "pass1234"})
    assert code == 403 and login_pending.get("status") == "pending", (code, login_pending)
    print("OK: login bloqueado ->", login_pending.get("error"))

    code, admin_login = _req("POST", "/api/auth/login", {"username": "admin", "password": "testadmin123"})
    assert code == 200 and admin_login.get("is_admin") is True, (code, admin_login)
    admin_token = admin_login["token"]
    print("OK: admin autenticado")

    code, pending = _req("GET", "/api/auth/admin/pending", token=admin_token)
    assert code == 200 and any(u.get("username") == "joao" for u in pending.get("pending", [])), (code, pending)
    print("OK: lista pendentes ->", pending.get("pending"))

    code, approved = _req(
        "POST",
        "/api/auth/admin/approve",
        {"username": "joao"},
        token=admin_token,
    )
    assert code == 200 and approved.get("status") == "approved", (code, approved)
    print("OK: joao aprovado")

    code, user_login = _req("POST", "/api/auth/login", {"username": "joao", "password": "pass1234"})
    assert code == 200 and user_login.get("is_admin") is False, (code, user_login)
    print("OK: joao entra após aprovação")

    code, status = _req("GET", "/api/auth/status", token=user_login["token"])
    assert code == 200 and status.get("can_use_bots") is True, (code, status)
    print("OK: permissões completas ->", {k: status[k] for k in ("guest_mode", "can_use_bots", "can_use_live", "is_admin")})

    code, forbidden = _req("GET", "/api/auth/admin/pending", token=user_login["token"])
    assert code == 403, (code, forbidden)
    print("OK: utilizador normal não acede ao painel admin")

    print("\nFluxo completo validado com sucesso.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())