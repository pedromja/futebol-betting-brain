"""Servidor web fino — expõe o motor Python via HTTP."""

import json
import os
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from web.auth_middleware import AuthMiddleware
from web.auth_policy import guest_permissions
from web.auth_store import (
    approve_user,
    auth_enabled,
    authenticate_with_status,
    change_password,
    create_session,
    auth_bootstrap_ready,
    ensure_bootstrap_user,
    ensure_extra_bootstrap_admins,
    migrate_legacy_users,
    is_admin,
    list_pending_users,
    register_user,
    reject_user,
    resolve_session,
    revoke_session,
)

from config.data_paths import DATA_DIR, ensure_data_dir
from config.env import load_dotenv
from discovery.api_football_client import ApiFootballClient
from discovery.quota_guard import active_fallbacks, is_exhausted, PROVIDER_API_FOOTBALL

load_dotenv()
from scanner.live_ranker import LiveScanRanker
from scanner.ranker import ScanRanker
from history.outcome_resolver import resolve_predictions
from history.tips_history import build_history_payload, get_last_tip
from discovery.match_stats import fetch_match_live_stats
from discovery.stats_snapshots import load_stats_history, record_stats_snapshot
from live.extended_bridge import analyze_extended_markets
from prematch.auditors import evaluate_motivation
from prematch.transfermarkt import analyze_prematch
from prematch.transfermarkt.cache import cache_paths
from prematch.transfermarkt.auto_sync import sync_match_teams
from prematch.transfermarkt.sync import log_sync_event, sync_teams_from_api
from prematch.transfermarkt.store import get_store
from prematch.transfermarkt import api_client as tm_api
from bots.catalog import catalog_payload
from bots.evaluator import evaluate_bots_for_scan
from bots.performance import build_bot_history_payload, build_performance_payload
from bots.store import delete_bot, get_bot, list_bots, save_bot, toggle_bot
from history.bot_signals import append_bot_hits
from bots.types import BotConfig
from web.push_store import load_subscriptions, save_subscription
from web.api.serializers import (
    live_fixture_to_dict,
    live_scan_result_to_dict,
    scan_result_to_dict,
    upcoming_fixture_to_dict,
)

def _resolve_web_dir() -> Path:
    override = (os.getenv("WEB_DIR") or "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[1]


WEB_DIR = _resolve_web_dir()
STATIC_DIR = WEB_DIR / "static"
BRANDING_FILE = WEB_DIR / "branding.json"

app = FastAPI(
    title="Futebol Betting Brain",
    version="0.1.0",
    description="API para a PWA — importa o motor existente, não duplica lógica.",
)
app.add_middleware(AuthMiddleware)


@app.on_event("startup")
def _auth_startup() -> None:
    migrate_legacy_users()
    ensure_bootstrap_user()
    ensure_extra_bootstrap_admins()


def _token_from_request(request: Request) -> str | None:
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    return request.cookies.get("sgm_token") or None


class LoginBody(BaseModel):
    username: str
    password: str


class ChangePasswordBody(BaseModel):
    old_password: str
    new_password: str


class RegisterBody(BaseModel):
    username: str
    password: str


class AdminUserBody(BaseModel):
    username: str


@app.get("/api/auth/status")
def api_auth_status(request: Request):
    """Estado de autenticação — público."""
    enabled = auth_enabled()
    token = _token_from_request(request)
    username = resolve_session(token) if enabled else None
    admin = is_admin(username) if username else False
    perms = guest_permissions(
        authenticated=bool(username),
        auth_enabled=enabled,
        is_admin=admin,
    )
    return {
        "auth_enabled": enabled,
        "auth_bootstrap_ready": auth_bootstrap_ready() if enabled else True,
        "authenticated": bool(username),
        "username": username,
        **perms,
    }


@app.post("/api/auth/register")
def api_auth_register(body: RegisterBody):
    if not auth_enabled():
        return JSONResponse({"error": "Autenticação desactivada"}, status_code=400)
    try:
        row = register_user(body.username.strip(), body.password)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return {
        "ok": True,
        "username": row.get("username"),
        "status": row.get("status"),
        "message": "Inscrição recebida. Aguarda aprovação do administrador.",
    }


@app.post("/api/auth/login")
def api_auth_login(body: LoginBody):
    if not auth_enabled():
        return JSONResponse({"error": "Autenticação desactivada"}, status_code=400)
    row, reason = authenticate_with_status(body.username.strip(), body.password)
    if reason == "pending":
        return JSONResponse(
            {
                "error": "Conta pendente de aprovação pelo administrador",
                "status": "pending",
            },
            status_code=403,
        )
    if reason == "rejected":
        return JSONResponse(
            {
                "error": "Inscrição rejeitada. Contacta o administrador.",
                "status": "rejected",
            },
            status_code=403,
        )
    if not row:
        return JSONResponse({"error": "Utilizador ou palavra-passe incorrectos"}, status_code=401)
    token, exp = create_session(str(row.get("username") or body.username))
    return {
        "ok": True,
        "token": token,
        "username": row.get("username"),
        "is_admin": is_admin(str(row.get("username") or "")),
        "expires_at": datetime.utcfromtimestamp(exp).isoformat(timespec="seconds") + "Z",
    }


@app.get("/api/auth/admin/pending")
def api_auth_admin_pending(request: Request):
    return {"pending": list_pending_users()}


@app.post("/api/auth/admin/approve")
def api_auth_admin_approve(body: AdminUserBody, request: Request):
    try:
        row = approve_user(body.username.strip())
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return {"ok": True, "username": row.get("username"), "status": row.get("status")}


@app.post("/api/auth/admin/reject")
def api_auth_admin_reject(body: AdminUserBody, request: Request):
    try:
        row = reject_user(body.username.strip())
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return {"ok": True, "username": row.get("username"), "status": row.get("status")}


@app.post("/api/auth/logout")
def api_auth_logout(request: Request):
    token = _token_from_request(request)
    if token:
        revoke_session(token)
    return {"ok": True}


@app.post("/api/auth/change-password")
def api_auth_change_password(body: ChangePasswordBody, request: Request):
    username = getattr(request.state, "auth_user", None) or resolve_session(
        _token_from_request(request)
    )
    if not username:
        return JSONResponse({"error": "Não autenticado"}, status_code=401)
    try:
        change_password(username, body.old_password, body.new_password)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return {"ok": True}


def load_branding() -> dict:
    if BRANDING_FILE.exists():
        with open(BRANDING_FILE, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {
            "app_name": "Betting Brain",
            "app_name_full": "Betting Brain",
            "tagline": "Scanner automático",
            "theme_color": "#1a2332",
            "background_color": "#0f1419",
            "icons": {"favicon": "/icons/icon-192.jpg"},
        }
    env_url = (os.getenv("MOMENT_BANNER_URL") or "").strip()
    if env_url and not (data.get("moment_banner_url") or "").strip():
        data["moment_banner_url"] = env_url
    return data


@app.get("/api/branding")
def api_branding():
    """Nome, ícone e cores — um ficheiro, toda a app actualiza."""
    return load_branding()


@app.get("/api/health")
def api_health():
    """Health check — splash desktop e monitorização."""
    resolved_pending = 0
    try:
        from history.resolve_scheduler import maybe_resolve_pending

        resolved_pending = maybe_resolve_pending()
    except Exception:
        pass
    return {
        "ok": True,
        "desktop": os.getenv("DESKTOP_APP") == "1",
        "auth_enabled": auth_enabled(),
        "auth_bootstrap_ready": auth_bootstrap_ready(),
        "resolved_pending": resolved_pending,
        "time": datetime.now().isoformat(timespec="seconds"),
    }


@app.get("/manifest.webmanifest")
def web_manifest():
    """PWA instalável — lê branding.json (actualiza com o projeto)."""
    b = load_branding()
    icons = b.get("icons", {})
    return JSONResponse(
        {
            "name": b.get("app_name_full") or b.get("app_name", "SindGreenMentor"),
            "short_name": (b.get("short_name") or b.get("app_name") or "SindGrEeN")[:12],
            "description": b.get("tagline", ""),
            "start_url": "/",
            "scope": "/",
            "display": "standalone",
            "orientation": "portrait",
            "background_color": b.get("background_color", "#0a2a20"),
            "theme_color": b.get("theme_color", "#0d3b2e"),
            "icons": [
                {
                    "src": icons.get("icon_192", "/icons/icon-192.jpg"),
                    "sizes": "192x192",
                    "type": "image/jpeg",
                    "purpose": "any",
                },
                {
                    "src": icons.get("icon_512", "/icons/icon-512.jpg"),
                    "sizes": "512x512",
                    "type": "image/jpeg",
                    "purpose": "any maskable",
                },
            ],
        },
        media_type="application/manifest+json",
    )


@app.get("/health")
def health():
    client = ApiFootballClient(api_key=os.getenv("API_FOOTBALL_KEY"))
    ensure_data_dir()
    payload = {
        "status": "ok",
        "engine": "futebol-betting-brain",
        "message": "Robô ligado e a responder.",
        "site_url": os.getenv("PUBLIC_SITE_URL", ""),
        "api_football": client.is_configured,
        "data_dir": str(DATA_DIR),
        "push_subscribers": len(load_subscriptions(limit=500)),
    }
    if client.is_configured:
        try:
            payload["quota_hint"] = client.quota_hint()
        except Exception:
            pass
        if client.last_error:
            payload["api_football_error"] = client.last_error
        if is_exhausted(PROVIDER_API_FOOTBALL):
            payload["api_football_exhausted"] = True
            payload["active_fallbacks"] = active_fallbacks()
    return payload


@app.get("/api/live/list")
def api_live_list(league: str | None = None):
    """Jogos ao vivo — lista rápida (1 pedido API-Football)."""
    client = ApiFootballClient(api_key=os.getenv("API_FOOTBALL_KEY"))
    if not client.is_configured:
        return JSONResponse(
            {"error": "Serviço temporariamente indisponível", "fixtures": []},
            status_code=503,
        )
    fixtures = client.scan_live()
    if league:
        key = league.lower()
        fixtures = [f for f in fixtures if key in f"{f.league} {f.stage}".lower()]
    from web.api.serializers import attach_game_temperature

    fx_rows = attach_game_temperature([live_fixture_to_dict(f) for f in fixtures])
    return {
        "scanned_at": datetime.now().isoformat(timespec="seconds"),
        "total": len(fixtures),
        "live_source": client.last_live_source,
        "live_source_label": {
            "api-football": "API-Football",
            "espn": "ESPN",
            "none": "Indisponível",
        }.get(client.last_live_source, client.last_live_source),
        "fixtures": fx_rows,
    }


@app.get("/api/live")
def api_live(
    min_score: float = 0.55,
    league: str | None = None,
    bankroll: float | None = None,
    max_games: int = 15,
    prematch_odds: bool = False,
):
    """Mesmo motor que `python main.py --live-scan`."""
    client = ApiFootballClient(api_key=os.getenv("API_FOOTBALL_KEY"))
    if not client.is_configured:
        return JSONResponse(
            {"error": "Serviço temporariamente indisponível"},
            status_code=503,
        )
    ranker = LiveScanRanker(
        api_football_key=os.getenv("API_FOOTBALL_KEY"),
        football_data_key=os.getenv("FOOTBALL_DATA_API_KEY"),
        weather_api_key=os.getenv("OPENWEATHERMAP_API_KEY"),
        min_score=min_score,
        bankroll=bankroll,
        max_games=max_games,
        league_filter=league,
        prefer_live_odds=not prematch_odds,
        news_enabled=False,
    )
    from scanner.scan_cache import get_live, live_key, set_live

    cache_k = live_key(
        min_score=min_score,
        bankroll=bankroll,
        max_games=max_games,
        league=league,
        prematch_odds=prematch_odds,
    )
    cached = get_live(cache_k)
    if cached:
        return cached

    result = ranker.scan_and_rank()
    payload = live_scan_result_to_dict(
        result,
        last_tip=get_last_tip(mode="live"),
        live_source=ranker.client.last_live_source,
    )
    hits = evaluate_bots_for_scan(payload.get("ranked") or [], mode="live")
    append_bot_hits(hits, scanned_at=payload.get("scanned_at"), bankroll=bankroll)
    payload["bot_hits"] = hits
    return set_live(cache_k, payload)


@app.get("/api/tips/history")
def api_tips_history(limit: int = 50, auto_resolve: bool = True, force_resolve: bool = False):
    """Histórico de tips com performance — resolve outcomes se possível."""
    if auto_resolve:
        from history.resolve_scheduler import maybe_resolve_pending

        maybe_resolve_pending(force=force_resolve)
    safe_limit = max(1, min(limit, 200))
    return build_history_payload(limit=safe_limit)


@app.post("/api/tips/resolve")
def api_tips_resolve():
    """Força resolução win/loss de tips pendentes."""
    from history.resolve_scheduler import mark_resolved, maybe_enrich_resolved

    _, stats = resolve_predictions(dry_run=False)
    mark_resolved(resolved_count=stats.resolved)
    maybe_enrich_resolved(force=True)
    payload = build_history_payload(limit=100)
    payload["resolve"] = {
        "resolved_now": stats.resolved,
        "still_pending": stats.still_pending,
        "hit_rate_pct": stats.hit_rate_pct,
    }
    return payload


@app.get("/api/review/verify-queue")
def api_review_verify_queue(limit: int = 15):
    """Apostas/sinais que precisam verificação manual — com prompt pronto."""
    from history.post_match_review import build_verify_queue
    from history.resolve_scheduler import maybe_enrich_resolved

    maybe_enrich_resolved()
    safe_limit = max(1, min(limit, 50))
    items = build_verify_queue(limit=safe_limit)
    return {"items": items, "total": len(items)}


@app.post("/api/review/enrich")
def api_review_enrich(max_fetch: int = 12):
    """Força reavaliação pós-jogo com stats finais."""
    from history.post_match_review import enrich_all_resolved_logs
    from history.resolve_scheduler import mark_enriched

    safe_max = max(1, min(max_fetch, 20))
    stats = enrich_all_resolved_logs(max_fetch=safe_max, dry_run=False)
    mark_enriched(reviewed_count=stats.get("reviewed", 0))
    return stats


class OutcomeCorrectBody(BaseModel):
    kind: str = "tip"
    entry_id: str
    outcome: str
    final_score: str | None = None
    note: str | None = None


@app.patch("/api/outcome/correct")
def api_outcome_correct(body: OutcomeCorrectBody):
    """Correcção manual GREEN/RED (tips ou sinais de bots)."""
    from bots.performance import signal_to_public
    from history.manual_outcome import correct_outcome
    from history.tips_history import tip_to_public

    try:
        row = correct_outcome(
            kind=body.kind,
            entry_id=body.entry_id.strip(),
            outcome=body.outcome,
            final_score=body.final_score,
            note=body.note,
        )
    except LookupError:
        return JSONResponse({"error": "Entrada não encontrada"}, status_code=404)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    kind_l = body.kind.lower().strip()
    is_bot = kind_l in ("bot", "bots", "signal")
    public = signal_to_public(row) if is_bot else tip_to_public(row)
    return {"ok": True, "entry": public}


def _build_scan_ranker(hours: int, min_score: float = 0.55, bankroll: float | None = None) -> ScanRanker:
    return ScanRanker(
        the_odds_api_key=os.getenv("THE_ODDS_API_KEY"),
        weather_api_key=os.getenv("OPENWEATHERMAP_API_KEY"),
        football_data_key=os.getenv("FOOTBALL_DATA_API_KEY"),
        api_football_key=os.getenv("API_FOOTBALL_KEY"),
        hours_ahead=hours,
        min_score=min_score,
        bankroll=bankroll,
        news_enabled=False,
    )


@app.get("/api/scan/list")
def api_scan_list(hours: int = 12):
    """Lista rápida de jogos pré-jogo (sem análise EV). Alarga 12h→24h se vazio."""
    from scanner.scan_cache import get_prematch, prematch_key, set_prematch

    list_key = f"{prematch_key(hours=hours, min_score=0, bankroll=None)}|list"
    cached = get_prematch(list_key, ttl=90.0)
    if cached and cached.get("fixtures"):
        return cached

    ranker = _build_scan_ranker(hours)
    fixtures, window, extended = ranker.discover_only()
    payload = {
        "scanned_at": datetime.now().isoformat(timespec="seconds"),
        "requested_hours": hours,
        "hours_window": window,
        "window_extended": extended,
        "total": len(fixtures),
        "fixtures": [upcoming_fixture_to_dict(f) for f in fixtures],
    }
    if extended:
        payload["notice"] = (
            f"Sem jogos nas próximas {hours}h — janela alargada para {window}h"
        )
    return set_prematch(list_key, payload)


@app.get("/api/transfermarkt/status")
def api_transfermarkt_status():
    """Estado da integração transfermarkt-api + cache JSONL."""
    return {
        "api_url": tm_api.api_base_url(),
        "api_reachable": tm_api.is_configured(),
        "cache": cache_paths(),
    }


@app.post("/api/transfermarkt/sync")
def api_transfermarkt_sync(teams: str, country: str = "Portugal"):
    """
    Sincroniza equipas da transfermarkt-api para o cache JSONL.
    teams: nomes separados por vírgula (ex: Benfica,Sporting,Maritimo)
    """
    names = [t.strip() for t in (teams or "").split(",") if t.strip()]
    if not names:
        return JSONResponse({"error": "teams obrigatório"}, status_code=400)
    if len(names) > 12:
        return JSONResponse({"error": "máximo 12 equipas por pedido"}, status_code=400)
    summary = sync_teams_from_api(names, prefer_country=country)
    log_sync_event(summary)
    get_store().reload()
    return summary


@app.get("/api/match/motivation")
def api_match_motivation(
    home: str,
    away: str,
    market: str = "",
    ev: float = 0.0,
    league: str = "",
    stage: str = "",
):
    """Motivation Gate — auditores ClubElo, Table Stakes, Transfermarkt."""
    if not home.strip() or not away.strip():
        return JSONResponse({"error": "home e away obrigatórios"}, status_code=400)
    tm = analyze_prematch(home.strip(), away.strip())
    odds_hint = None
    report = evaluate_motivation(
        home.strip(),
        away.strip(),
        best_market=market or "Vitória Casa",
        best_ev=max(0.0, ev),
        league=league,
        stage=stage,
        tm_insights=tm,
        odds_hint=odds_hint,
    )
    return report.to_dict()


@app.get("/api/match/prematch-insights")
def api_match_prematch_insights(
    home: str,
    away: str,
    referee: str | None = None,
    league: str = "",
    stage: str = "",
    home_win: float | None = None,
    draw: float | None = None,
    away_win: float | None = None,
):
    """Inteligência Transfermarkt — 4 pilares (cache JSONL)."""
    if not home.strip() or not away.strip():
        return JSONResponse({"error": "home e away obrigatórios"}, status_code=400)
    sync_match_teams(
        home.strip(),
        away.strip(),
        league=league,
        stage=stage,
    )
    odds_hint = None
    if home_win and draw and away_win:
        odds_hint = {"home_win": home_win, "draw": draw, "away_win": away_win}
    insights = analyze_prematch(
        home.strip(),
        away.strip(),
        odds_hint=odds_hint,
        referee_name=referee,
    )
    payload = insights.to_dict()
    payload["cache"] = cache_paths()
    return payload


@app.get("/api/match/detail")
def api_match_detail(
    fixture_id: int,
    events: bool = False,
    home_score: int | None = None,
    away_score: int | None = None,
    minute: int | None = None,
    injury_time: int = 0,
    home: str | None = None,
    away: str | None = None,
):
    """
    Estatísticas ao vivo — posse, chutes, xG (lazy, só ao abrir detalhe).
    1 pedido API-Football por defeito; events=true acrescenta +1 pedido.
    Parâmetros de score/minuto permitem mercados avançados e snapshots.
    """
    if fixture_id <= 0:
        return JSONResponse({"error": "fixture_id inválido"}, status_code=400)

    client = ApiFootballClient(api_key=os.getenv("API_FOOTBALL_KEY"))
    if not client.is_configured:
        return JSONResponse(
            {"error": "API-Football não configurada", "stats_available": False},
            status_code=503,
        )
    if is_exhausted(PROVIDER_API_FOOTBALL):
        return JSONResponse(
            {
                "error": "Quota API-Football esgotada",
                "stats_available": False,
                "fixture_id": fixture_id,
            },
            status_code=503,
        )

    bundle = fetch_match_live_stats(client, fixture_id, include_events=events)
    if not bundle:
        from live.match_intensity import build_pressure_analysis

        history = load_stats_history(fixture_id)
        return {
            "fixture_id": fixture_id,
            "stats_available": False,
            "fetched_at": datetime.now().isoformat(timespec="seconds"),
            "message": "Estatísticas indisponíveis para este jogo (liga ou momento).",
            "stats_history": history,
            "pressure_analysis": build_pressure_analysis(history),
            "extended_markets": [],
        }
    payload = bundle.to_dict()
    payload["stats_available"] = True

    if minute is not None and home_score is not None and away_score is not None:
        record_stats_snapshot(
            bundle,
            minute=minute,
            home_score=home_score,
            away_score=away_score,
        )
        payload["extended_markets"] = analyze_extended_markets(
            bundle,
            home_score=home_score,
            away_score=away_score,
            minute=minute,
            home_name=home or bundle.home.team or "Casa",
            away_name=away or bundle.away.team or "Fora",
            injury_time=injury_time,
        )
    else:
        payload["extended_markets"] = []

    history = load_stats_history(fixture_id)
    payload["stats_history"] = history
    from live.match_intensity import build_pressure_analysis

    payload["pressure_analysis"] = build_pressure_analysis(history)
    return payload


class PushSubscriptionBody(BaseModel):
    endpoint: str
    keys: dict | None = None


@app.post("/api/push/subscribe")
def api_push_subscribe(body: PushSubscriptionBody):
    """Regista subscrição Web Push para alertas futuros no servidor."""
    ok = save_subscription(body.model_dump())
    if not ok:
        return JSONResponse({"error": "Subscrição inválida"}, status_code=400)
    return {"ok": True, "subscribers": len(load_subscriptions(limit=500))}


@app.get("/api/push/vapid-public-key")
def api_push_vapid_key():
    """Chave pública VAPID — necessária para subscrição push no browser."""
    key = (os.getenv("VAPID_PUBLIC_KEY") or "").strip()
    return {"public_key": key or None, "configured": bool(key)}


@app.get("/api/scan")
def api_scan(
    request: Request,
    hours: int = 12,
    min_score: float = 0.55,
    bankroll: float | None = None,
):
    """
    Mesmo motor que `python main.py --scan`.
    Chaves vêm das variáveis de ambiente (como no CLI).
    """
    from scanner.scan_cache import get_prematch, prematch_key, set_prematch

    cache_k = prematch_key(hours=hours, min_score=min_score, bankroll=bankroll)
    logged_in = bool(getattr(request.state, "auth_user", None))
    cached = get_prematch(cache_k) if logged_in else None

    if cached:
        payload = dict(cached)
    else:
        ranker = _build_scan_ranker(hours, min_score, bankroll)
        payload = scan_result_to_dict(ranker.scan_and_rank())
        if logged_in:
            hits = evaluate_bots_for_scan(payload.get("ranked") or [], mode="prematch")
            append_bot_hits(hits, scanned_at=payload.get("scanned_at"), bankroll=bankroll)
            payload["bot_hits"] = hits
            return set_prematch(cache_k, payload)

    if not logged_in:
        payload = dict(payload)
        payload["bot_hits"] = []
        payload["guest_mode"] = True
    try:
        from history.resolve_scheduler import maybe_resolve_pending

        payload["resolved_pending"] = maybe_resolve_pending()
    except Exception:
        payload["resolved_pending"] = 0
    return payload


class BotBody(BaseModel):
    id: str | None = None
    name: str
    mode: str = "prematch"
    description: str = ""
    active: bool = True
    notify: bool = True
    leagues: list[str] = []
    markets: list[str] = []
    min_score: float | None = None
    min_ev_pct: float | None = None
    max_stake_level: int | None = None
    minutes_before: int | None = None
    conditions: list[dict] = []
    conditions_logic: str = "and"
    condition_groups: list[dict] = []
    groups_logic: str = "or"
    template: str | None = None


@app.get("/api/bots/catalog")
def api_bots_catalog():
    """Categorias de condições, mercados e templates para o wizard."""
    return catalog_payload()


@app.get("/api/bots")
def api_bots_list(include_performance: bool = False, auto_resolve: bool = True):
    if auto_resolve:
        from history.resolve_scheduler import maybe_resolve_pending

        maybe_resolve_pending()
    bots = [b.to_dict() for b in list_bots()]
    payload = {"bots": bots, "limit": 40, "total": len(bots)}
    if include_performance:
        payload["performance"] = build_performance_payload()
    return payload


@app.get("/api/bots/performance")
def api_bots_performance(auto_resolve: bool = True):
    if auto_resolve:
        from history.resolve_scheduler import maybe_resolve_pending

        maybe_resolve_pending()
    return build_performance_payload()


@app.get("/api/ia/live")
def api_ia_live_board(force: bool = False):
    """Jogos ESPN in-play + análises IA autónoma."""
    from ia.autonomous_engine import build_live_board_payload

    return build_live_board_payload(force=force)


@app.get("/api/ia/live/{game_id}")
def api_ia_live_game(
    game_id: str,
    league_code: str = "",
    force: bool = False,
    debug: bool = False,
):
    """Análise IA para um jogo ESPN (gameId). debug=1 expõe llm_context para revisão humana."""
    from ia.autonomous_engine import analyze_by_game_id

    payload = analyze_by_game_id(
        game_id,
        league_code=league_code or None,
        force=force,
        include_context=debug,
    )
    if not payload:
        return JSONResponse({"error": "Jogo não encontrado ou não está in-play"}, status_code=404)
    return payload


@app.post("/api/ia/live/{game_id}/refresh")
def api_ia_live_refresh(game_id: str, league_code: str = ""):
    """Força novo ciclo LLM para o jogo."""
    from ia.autonomous_engine import analyze_by_game_id

    payload = analyze_by_game_id(game_id, league_code=league_code or None, force=True)
    if not payload:
        return JSONResponse({"error": "Jogo não encontrado"}, status_code=404)
    return payload


@app.get("/api/ia/tips")
def api_ia_tips(limit: int = 80, auto_resolve: bool = True):
    """Dicas IA + acertividade acumulada por mercado."""
    if auto_resolve:
        from history.resolve_scheduler import maybe_resolve_pending

        maybe_resolve_pending()
    from bots.ia_tips import build_ia_tips_payload

    safe_limit = max(10, min(limit, 150))
    return build_ia_tips_payload(limit=safe_limit)


@app.get("/api/ia/backtest")
def api_ia_backtest(refresh: bool = False):
    """Backtest multi-liga — pré-jogo vs IA live (CSV histórico)."""
    from backtest.runner import build_backtest_payload

    return build_backtest_payload(refresh=refresh)


@app.get("/api/bots/ia-audit")
def api_bots_ia_audit(refresh: bool = False, auto_resolve: bool = True):
    """Auditoria IA — greens/reds, conhecimento acumulado e modelos restritos."""
    if auto_resolve:
        from history.resolve_scheduler import maybe_resolve_pending

        maybe_resolve_pending()
    from bots.ia_audit import load_ia_audit, refresh_ia_audit

    if refresh:
        state = refresh_ia_audit()
    else:
        state = load_ia_audit()
    return state.to_dict()


@app.get("/api/bots/{bot_id}/history")
def api_bot_history(bot_id: str, limit: int = 40, auto_resolve: bool = True):
    if not get_bot(bot_id):
        return JSONResponse({"error": "Bot não encontrado"}, status_code=404)
    if auto_resolve:
        from history.resolve_scheduler import maybe_resolve_pending

        maybe_resolve_pending()
    safe_limit = max(1, min(limit, 100))
    return build_bot_history_payload(bot_id, limit=safe_limit)


@app.post("/api/bots")
def api_bots_create(body: BotBody):
    try:
        bot = BotConfig.from_dict(body.model_dump())
        bot = save_bot(bot, is_new=True)
        return bot.to_dict()
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@app.get("/api/bots/{bot_id}")
def api_bots_get(bot_id: str):
    bot = get_bot(bot_id)
    if not bot:
        return JSONResponse({"error": "Bot não encontrado"}, status_code=404)
    return bot.to_dict()


@app.put("/api/bots/{bot_id}")
def api_bots_update(bot_id: str, body: BotBody):
    existing = get_bot(bot_id)
    if not existing:
        return JSONResponse({"error": "Bot não encontrado"}, status_code=404)
    payload = body.model_dump()
    payload["id"] = bot_id
    payload["created_at"] = existing.created_at
    bot = save_bot(BotConfig.from_dict(payload))
    return bot.to_dict()


@app.delete("/api/bots/{bot_id}")
def api_bots_delete(bot_id: str):
    if not delete_bot(bot_id):
        return JSONResponse({"error": "Bot não encontrado"}, status_code=404)
    return {"ok": True}


@app.patch("/api/bots/{bot_id}/toggle")
def api_bots_toggle(bot_id: str, active: bool | None = None):
    bot = toggle_bot(bot_id, active=active)
    if not bot:
        return JSONResponse({"error": "Bot não encontrado"}, status_code=404)
    return bot.to_dict()


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")