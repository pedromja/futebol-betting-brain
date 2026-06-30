"""Utilizadores e sessões — ficheiros em DATA_DIR."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import time
from pathlib import Path

from config.data_paths import DATA_DIR, ensure_data_dir

AUTH_USERS_FILE = DATA_DIR / "auth_users.json"
AUTH_SESSIONS_FILE = DATA_DIR / "auth_sessions.json"
SESSION_TTL_SEC = 7 * 24 * 3600
_PBKDF2_ROUNDS = 200_000

STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"

ROLE_ADMIN = "admin"
ROLE_USER = "user"


def _secret() -> str:
    key = (os.getenv("AUTH_SECRET") or os.getenv("SESSION_SECRET") or "").strip()
    if not key:
        key = "sgm-dev-change-me"
    return key


def auth_enabled() -> bool:
    flag = os.getenv("AUTH_ENABLED", "").strip().lower()
    if flag in ("0", "false", "no"):
        return False
    if flag in ("1", "true", "yes"):
        return True
    if os.getenv("DESKTOP_APP") == "1":
        return True
    return bool((os.getenv("AUTH_USERNAME") or "").strip())


def hash_password(password: str, *, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        _PBKDF2_ROUNDS,
    )
    return f"pbkdf2_sha256${_PBKDF2_ROUNDS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, rounds_s, salt, digest_hex = stored.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        rounds = int(rounds_s)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            rounds,
        )
        return secrets.compare_digest(digest.hex(), digest_hex)
    except (TypeError, ValueError):
        return False


def _normalize_user(row: dict) -> dict:
    """Garante campos status/role em utilizadores antigos."""
    out = dict(row)
    if not out.get("status"):
        out["status"] = STATUS_APPROVED
    if not out.get("role"):
        out["role"] = ROLE_USER
    return out


def _read_users() -> dict:
    if not AUTH_USERS_FILE.exists():
        return {"users": []}
    try:
        data = json.loads(AUTH_USERS_FILE.read_text(encoding="utf-8"))
        users = [_normalize_user(u) for u in data.get("users") or []]
        data["users"] = users
        return data
    except (json.JSONDecodeError, OSError):
        return {"users": []}


def _write_users(data: dict) -> None:
    ensure_data_dir()
    AUTH_USERS_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _read_sessions() -> dict:
    if not AUTH_SESSIONS_FILE.exists():
        return {"sessions": {}}
    try:
        data = json.loads(AUTH_SESSIONS_FILE.read_text(encoding="utf-8"))
        if isinstance(data.get("sessions"), dict):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return {"sessions": {}}


def _write_sessions(data: dict) -> None:
    ensure_data_dir()
    AUTH_SESSIONS_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _prune_sessions(sessions: dict) -> dict:
    now = time.time()
    return {k: v for k, v in sessions.items() if float(v.get("exp") or 0) > now}


def list_usernames() -> list[str]:
    return [str(u.get("username") or "") for u in _read_users().get("users") or []]


def get_user(username: str) -> dict | None:
    needle = username.strip().lower()
    for row in _read_users().get("users") or []:
        if str(row.get("username") or "").lower() == needle:
            return _normalize_user(row)
    return None


def is_admin(username: str) -> bool:
    row = get_user(username)
    return bool(row and str(row.get("role") or "") == ROLE_ADMIN)


def user_can_login(row: dict | None) -> bool:
    return bool(row and str(row.get("status") or "") == STATUS_APPROVED)


def create_user(
    username: str,
    password: str,
    *,
    status: str = STATUS_PENDING,
    role: str = ROLE_USER,
) -> dict:
    name = username.strip()
    if not name or len(password) < 4:
        raise ValueError("Utilizador ou palavra-passe inválidos")
    if status not in (STATUS_PENDING, STATUS_APPROVED, STATUS_REJECTED):
        raise ValueError("Estado inválido")
    if role not in (ROLE_ADMIN, ROLE_USER):
        raise ValueError("Perfil inválido")
    data = _read_users()
    users = list(data.get("users") or [])
    if any(str(u.get("username") or "").lower() == name.lower() for u in users):
        raise ValueError("Utilizador já existe")
    row = {
        "username": name,
        "password_hash": hash_password(password),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": status,
        "role": role,
    }
    users.append(row)
    data["users"] = users
    _write_users(data)
    return row


def register_user(username: str, password: str) -> dict:
    """Nova inscrição — fica pendente até aprovação do admin."""
    return create_user(username, password, status=STATUS_PENDING, role=ROLE_USER)


def list_pending_users() -> list[dict]:
    out = []
    for row in _read_users().get("users") or []:
        if str(row.get("status") or "") == STATUS_PENDING:
            out.append(
                {
                    "username": row.get("username"),
                    "created_at": row.get("created_at"),
                }
            )
    return out


def _set_user_status(username: str, status: str) -> dict:
    needle = username.strip().lower()
    if status not in (STATUS_PENDING, STATUS_APPROVED, STATUS_REJECTED):
        raise ValueError("Estado inválido")
    data = _read_users()
    users = []
    found = None
    for u in data.get("users") or []:
        if str(u.get("username") or "").lower() == needle:
            u = {**_normalize_user(u), "status": status}
            found = u
        users.append(u)
    if not found:
        raise ValueError("Utilizador não encontrado")
    data["users"] = users
    _write_users(data)
    return found


def approve_user(username: str) -> dict:
    return _set_user_status(username, STATUS_APPROVED)


def reject_user(username: str) -> dict:
    return _set_user_status(username, STATUS_REJECTED)


def migrate_legacy_users() -> int:
    """Persiste status/role em contas antigas sem esses campos."""
    if not AUTH_USERS_FILE.exists():
        return 0
    try:
        data = json.loads(AUTH_USERS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return 0
    bootstrap = (os.getenv("AUTH_USERNAME") or "").strip().lower()
    users = []
    changed = 0
    for raw in data.get("users") or []:
        row = _normalize_user(raw)
        if bootstrap and str(row.get("username") or "").lower() == bootstrap:
            if row.get("role") != ROLE_ADMIN or row.get("status") != STATUS_APPROVED:
                row = {**row, "role": ROLE_ADMIN, "status": STATUS_APPROVED}
                changed += 1
        elif "status" not in raw or "role" not in raw:
            changed += 1
        users.append(row)
    if changed:
        data["users"] = users
        _write_users(data)
    return changed


def ensure_bootstrap_user() -> str | None:
    """Cria admin inicial a partir de AUTH_USERNAME / AUTH_PASSWORD."""
    user = (os.getenv("AUTH_USERNAME") or "").strip()
    pwd = os.getenv("AUTH_PASSWORD") or ""
    if not user or not pwd:
        return None
    existing = get_user(user)
    if existing:
        if (
            str(existing.get("role") or "") != ROLE_ADMIN
            or str(existing.get("status") or "") != STATUS_APPROVED
        ):
            data = _read_users()
            users = []
            for u in data.get("users") or []:
                if str(u.get("username") or "").lower() == user.lower():
                    u = {
                        **_normalize_user(u),
                        "role": ROLE_ADMIN,
                        "status": STATUS_APPROVED,
                    }
                users.append(u)
            data["users"] = users
            _write_users(data)
        return user
    create_user(user, pwd, status=STATUS_APPROVED, role=ROLE_ADMIN)
    return user


def authenticate(username: str, password: str) -> dict | None:
    row = get_user(username)
    if not row:
        return None
    if not verify_password(password, str(row.get("password_hash") or "")):
        return None
    if not user_can_login(row):
        return None
    return row


def authenticate_with_status(username: str, password: str) -> tuple[dict | None, str | None]:
    """Devolve (user, motivo) — motivo: pending | rejected | invalid."""
    row = get_user(username)
    if not row or not verify_password(password, str(row.get("password_hash") or "")):
        return None, "invalid"
    status = str(row.get("status") or "")
    if status == STATUS_PENDING:
        return None, "pending"
    if status == STATUS_REJECTED:
        return None, "rejected"
    return row, None


def create_session(username: str) -> tuple[str, float]:
    token = secrets.token_urlsafe(32)
    exp = time.time() + SESSION_TTL_SEC
    data = _read_sessions()
    sessions = _prune_sessions(dict(data.get("sessions") or {}))
    sessions[token] = {"username": username.strip(), "exp": exp}
    data["sessions"] = sessions
    _write_sessions(data)
    return token, exp


def revoke_session(token: str) -> bool:
    if not token:
        return False
    data = _read_sessions()
    sessions = dict(data.get("sessions") or {})
    if token not in sessions:
        return False
    del sessions[token]
    data["sessions"] = sessions
    _write_sessions(data)
    return True


def resolve_session(token: str | None) -> str | None:
    if not token:
        return None
    data = _read_sessions()
    sessions = _prune_sessions(dict(data.get("sessions") or {}))
    row = sessions.get(token)
    if not row:
        if sessions != data.get("sessions"):
            data["sessions"] = sessions
            _write_sessions(data)
        return None
    if float(row.get("exp") or 0) <= time.time():
        sessions.pop(token, None)
        data["sessions"] = sessions
        _write_sessions(data)
        return None
    return str(row.get("username") or "") or None


def change_password(username: str, old_password: str, new_password: str) -> None:
    row = authenticate(username, old_password)
    if not row:
        raise ValueError("Palavra-passe actual incorrecta")
    if len(new_password) < 4:
        raise ValueError("Nova palavra-passe demasiado curta")
    data = _read_users()
    users = []
    for u in data.get("users") or []:
        if str(u.get("username") or "").lower() == username.strip().lower():
            u = {**u, "password_hash": hash_password(new_password)}
        users.append(u)
    data["users"] = users
    _write_users(data)