"""Servidor web fino — expõe o motor Python via HTTP."""

import json
import os
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

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
from bots.store import delete_bot, get_bot, list_bots, save_bot, toggle_bot
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


def load_branding() -> dict:
    if BRANDING_FILE.exists():
        with open(BRANDING_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {
        "app_name": "Betting Brain",
        "app_name_full": "Betting Brain",
        "tagline": "Scanner automático",
        "theme_color": "#1a2332",
        "background_color": "#0f1419",
        "icons": {"favicon": "/icons/icon-192.jpg"},
    }


@app.get("/api/branding")
def api_branding():
    """Nome, ícone e cores — um ficheiro, toda a app actualiza."""
    return load_branding()


@app.get("/api/health")
def api_health():
    """Health check — splash desktop e monitorização."""
    return {
        "ok": True,
        "desktop": os.getenv("DESKTOP_APP") == "1",
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
    return {
        "scanned_at": datetime.now().isoformat(timespec="seconds"),
        "total": len(fixtures),
        "live_source": client.last_live_source,
        "live_source_label": {
            "api-football": "API-Football",
            "espn": "ESPN",
            "none": "Indisponível",
        }.get(client.last_live_source, client.last_live_source),
        "fixtures": [live_fixture_to_dict(f) for f in fixtures],
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
    result = ranker.scan_and_rank()
    payload = live_scan_result_to_dict(
        result,
        last_tip=get_last_tip(mode="live"),
        live_source=ranker.client.last_live_source,
    )
    payload["bot_hits"] = evaluate_bots_for_scan(payload.get("ranked") or [], mode="live")
    return payload


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
    from history.resolve_scheduler import mark_resolved

    _, stats = resolve_predictions(dry_run=False)
    mark_resolved(resolved_count=stats.resolved)
    payload = build_history_payload(limit=100)
    payload["resolve"] = {
        "resolved_now": stats.resolved,
        "still_pending": stats.still_pending,
        "hit_rate_pct": stats.hit_rate_pct,
    }
    return payload


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
    return payload


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
        return {
            "fixture_id": fixture_id,
            "stats_available": False,
            "fetched_at": datetime.now().isoformat(timespec="seconds"),
            "message": "Estatísticas indisponíveis para este jogo (liga ou momento).",
            "stats_history": load_stats_history(fixture_id),
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

    payload["stats_history"] = load_stats_history(fixture_id)
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
    hours: int = 12,
    min_score: float = 0.55,
    bankroll: float | None = None,
):
    """
    Mesmo motor que `python main.py --scan`.
    Chaves vêm das variáveis de ambiente (como no CLI).
    """
    ranker = _build_scan_ranker(hours, min_score, bankroll)
    payload = scan_result_to_dict(ranker.scan_and_rank())
    payload["bot_hits"] = evaluate_bots_for_scan(payload.get("ranked") or [], mode="prematch")
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
    template: str | None = None


@app.get("/api/bots/catalog")
def api_bots_catalog():
    """Categorias de condições, mercados e templates para o wizard."""
    return catalog_payload()


@app.get("/api/bots")
def api_bots_list():
    bots = [b.to_dict() for b in list_bots()]
    return {"bots": bots, "limit": 40, "total": len(bots)}


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