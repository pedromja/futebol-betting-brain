"""Teste ao vivo do auth na app desktop (porta 8765)."""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
BASE = f"http://127.0.0.1:{PORT}"


def req(method: str, path: str, body: dict | None = None, token: str | None = None):
    data = None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=12) as resp:
            payload = resp.read().decode("utf-8")
            return resp.status, json.loads(payload) if payload else {}
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8")
        try:
            parsed = json.loads(payload) if payload else {}
        except json.JSONDecodeError:
            parsed = {"raw": payload}
        return exc.code, parsed


def main() -> int:
    print(f"Testar auth em {BASE}\n")

    code, health = req("GET", "/api/health")
    if code != 200:
        print(f"FAIL: servidor offline ({code})")
        return 1
    print("OK health:", health)

    code, status = req("GET", "/api/auth/status")
    if code != 200 or not status.get("auth_enabled"):
        print(f"FAIL: auth desactivado ({code}, {status})")
        return 1
    print("OK guest:", {k: status[k] for k in ("guest_mode", "can_use_bots", "can_use_live", "can_use_prematch")})

    test_user = "teste_desktop"
    req("POST", "/api/auth/register", {"username": test_user, "password": "test1234"})

    code, blocked = req("POST", "/api/auth/login", {"username": test_user, "password": "test1234"})
    if code != 403:
        print(f"FAIL: login pendente devia ser 403 ({code}, {blocked})")
        return 1
    print("OK login pendente bloqueado")

    code, admin = req("POST", "/api/auth/login", {"username": "admin", "password": "testadmin123"})
    if code != 200 or not admin.get("is_admin"):
        print(f"FAIL: admin login ({code}, {admin})")
        return 1
    token = admin["token"]
    print("OK admin login ->", admin.get("username"))

    code, pending = req("GET", "/api/auth/admin/pending", token=token)
    names = [u.get("username") for u in pending.get("pending", [])]
    if code != 200 or test_user not in names:
        print(f"FAIL: pendentes ({code}, {names})")
        return 1
    print("OK pendentes ->", names)

    code, approved = req("POST", "/api/auth/admin/approve", {"username": test_user}, token=token)
    if code != 200:
        print(f"FAIL: aprovar ({code}, {approved})")
        return 1
    print("OK aprovado ->", test_user)

    code, user = req("POST", "/api/auth/login", {"username": test_user, "password": "test1234"})
    if code != 200:
        print(f"FAIL: login user ({code}, {user})")
        return 1
    print("OK user login -> bots/live:", user.get("can_use_bots"), user.get("can_use_live"))

    code, full = req("GET", "/api/auth/status", token=user["token"])
    if not full.get("can_use_bots") or not full.get("can_use_live"):
        print(f"FAIL: permissoes ({full})")
        return 1
    print("OK permissoes completas")

    print("\nAuth desktop validado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())