"""Middleware — convidado: pré-jogo + IA; autenticado: tudo."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from web.auth_policy import guest_allowed_path
from web.auth_store import auth_enabled, is_admin, resolve_session

_ADMIN_PREFIX = "/api/auth/admin/"


def _extract_token(request: Request) -> str | None:
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    return request.cookies.get("sgm_token") or None


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not auth_enabled():
            return await call_next(request)

        path = request.url.path
        if not path.startswith("/api/"):
            return await call_next(request)

        token = _extract_token(request)
        username = resolve_session(token)
        if username:
            request.state.auth_user = username
            request.state.auth_is_admin = is_admin(username)

        if path.startswith(_ADMIN_PREFIX):
            if not username:
                return JSONResponse(
                    {
                        "error": "Inicia sessão como administrador",
                        "auth_required": True,
                        "login_required": True,
                    },
                    status_code=401,
                )
            if not is_admin(username):
                return JSONResponse(
                    {"error": "Apenas administradores podem aceder a esta área"},
                    status_code=403,
                )
            return await call_next(request)

        if guest_allowed_path(path):
            return await call_next(request)

        if not username:
            return JSONResponse(
                {
                    "error": "Inicia sessão para aceder a esta funcionalidade",
                    "auth_required": True,
                    "login_required": True,
                },
                status_code=401,
            )
        return await call_next(request)