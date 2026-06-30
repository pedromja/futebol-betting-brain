"""Política de acesso — convidado: pré-jogo + IA; ao vivo/bots/histórico pedem login (UI mostra tudo)."""

from __future__ import annotations

_GUEST_EXACT = frozenset(
    {
        "/api/health",
        "/api/branding",
        "/manifest.webmanifest",
    }
)

_GUEST_PREFIXES = (
    "/api/auth/",
    "/api/scan",
    "/api/match/prematch-insights",
    "/api/match/motivation",
    "/api/ia/",
)


def guest_allowed_path(path: str) -> bool:
    if path in _GUEST_EXACT:
        return True
    return any(
        path == prefix or path.startswith(prefix + "/") or path.startswith(prefix)
        for prefix in _GUEST_PREFIXES
    )


def guest_permissions(
    *,
    authenticated: bool,
    auth_enabled: bool,
    is_admin: bool = False,
) -> dict:
    if not auth_enabled:
        return {
            "guest_mode": False,
            "can_use_bots": True,
            "can_use_live": True,
            "can_use_history": True,
            "can_use_prematch": True,
            "can_use_ia": True,
            "is_admin": False,
        }
    if authenticated:
        return {
            "guest_mode": False,
            "can_use_bots": True,
            "can_use_live": True,
            "can_use_history": True,
            "can_use_prematch": True,
            "can_use_ia": True,
            "is_admin": is_admin,
        }
    return {
        "guest_mode": True,
        "can_use_bots": False,
        "can_use_live": False,
        "can_use_history": False,
        "can_use_prematch": True,
        "can_use_ia": True,
        "is_admin": False,
    }