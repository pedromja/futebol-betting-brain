"""Testes — autenticação username/password."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pytest

from web import auth_store


@pytest.fixture
def auth_env(tmp_path, monkeypatch):
    users = tmp_path / "users.json"
    sessions = tmp_path / "sessions.json"
    monkeypatch.setattr(auth_store, "AUTH_USERS_FILE", users)
    monkeypatch.setattr(auth_store, "AUTH_SESSIONS_FILE", sessions)
    monkeypatch.setenv("AUTH_ENABLED", "1")
    monkeypatch.setenv("AUTH_USERNAME", "")
    monkeypatch.delenv("AUTH_PASSWORD", raising=False)
    auth_store.create_user(
        "tester",
        "secret123",
        status=auth_store.STATUS_APPROVED,
        role=auth_store.ROLE_USER,
    )
    return users, sessions


def test_hash_and_verify():
    h = auth_store.hash_password("abc")
    assert auth_store.verify_password("abc", h)
    assert not auth_store.verify_password("wrong", h)


def test_session_lifecycle(auth_env):
    token, exp = auth_store.create_session("tester")
    assert auth_store.resolve_session(token) == "tester"
    auth_store.revoke_session(token)
    assert auth_store.resolve_session(token) is None


def test_change_password(auth_env):
    auth_store.change_password("tester", "secret123", "newpass456")
    assert auth_store.authenticate("tester", "newpass456")
    assert not auth_store.authenticate("tester", "secret123")


def test_bootstrap_user(auth_env, monkeypatch):
    monkeypatch.setenv("AUTH_USERNAME", "bootstrap")
    monkeypatch.setenv("AUTH_PASSWORD", "bootpass")
    created = auth_store.ensure_bootstrap_user()
    assert created == "bootstrap"
    row = auth_store.get_user("bootstrap")
    assert row["role"] == auth_store.ROLE_ADMIN
    assert row["status"] == auth_store.STATUS_APPROVED
    assert auth_store.authenticate("bootstrap", "bootpass")


def test_register_pending_and_approve(auth_env):
    auth_store.register_user("novo", "pass1234")
    row, reason = auth_store.authenticate_with_status("novo", "pass1234")
    assert row is None
    assert reason == "pending"
    assert auth_store.list_pending_users() == [
        {"username": "novo", "created_at": auth_store.get_user("novo")["created_at"]}
    ]
    auth_store.approve_user("novo")
    assert auth_store.authenticate("novo", "pass1234")
    assert auth_store.list_pending_users() == []


def test_reject_registration(auth_env):
    auth_store.register_user("recusado", "pass1234")
    auth_store.reject_user("recusado")
    row, reason = auth_store.authenticate_with_status("recusado", "pass1234")
    assert row is None
    assert reason == "rejected"


def test_migrate_legacy_users(auth_env, monkeypatch):
    users_file, _ = auth_env
    users_file.write_text(
        json.dumps(
            {
                "users": [
                    {
                        "username": "legacy",
                        "password_hash": auth_store.hash_password("oldpass"),
                        "created_at": "2026-01-01T00:00:00Z",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    changed = auth_store.migrate_legacy_users()
    assert changed == 1
    row = auth_store.get_user("legacy")
    assert row["status"] == auth_store.STATUS_APPROVED
    assert row["role"] == auth_store.ROLE_USER


def test_is_admin_bootstrap(auth_env, monkeypatch):
    monkeypatch.setenv("AUTH_USERNAME", "boss")
    monkeypatch.setenv("AUTH_PASSWORD", "bosspass")
    auth_store.ensure_bootstrap_user()
    assert auth_store.is_admin("boss")
    assert not auth_store.is_admin("tester")


def test_auth_disabled_by_default(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "0")
    monkeypatch.delenv("AUTH_USERNAME", raising=False)
    assert auth_store.auth_enabled() is False


def test_guest_policy_paths():
    from web.auth_policy import guest_allowed_path, guest_permissions

    assert guest_allowed_path("/api/scan")
    assert guest_allowed_path("/api/scan/list")
    assert guest_allowed_path("/api/ia/tips")
    assert guest_allowed_path("/api/match/prematch-insights")
    assert not guest_allowed_path("/api/bots")
    assert not guest_allowed_path("/api/live")
    assert not guest_allowed_path("/api/tips/history")

    guest = guest_permissions(authenticated=False, auth_enabled=True)
    assert guest["guest_mode"] is True
    assert guest["can_use_prematch"] is True
    assert guest["can_use_ia"] is True
    assert guest["can_use_bots"] is False
    assert guest["can_use_live"] is False

    full = guest_permissions(authenticated=True, auth_enabled=True, is_admin=True)
    assert full["can_use_bots"] is True
    assert full["is_admin"] is True