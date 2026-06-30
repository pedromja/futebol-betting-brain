"""Servidor web fino — expõe o motor Python via HTTP."""

import json
import os
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from config.env import load_dotenv
from discovery.api_football_client import ApiFootballClient
from discovery.quota_guard import active_fallbacks, is_exhausted, PROVIDER_API_FOOTBALL

load_dotenv()
from scanner.live_ranker import LiveScanRanker
from scanner.ranker import ScanRanker
from history.outcome_resolver import resolve_predictions
from history.tips_history import build_history_payload
from web.api.serializers import (
    live_fixture_to_dict,
    live_scan_result_to_dict,
    scan_result_to_dict,
    upcoming_fixture_to_dict,
)

WEB_DIR = Path(__file__).resolve().parents[1]
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


@app.get("/manifest.webmanifest")
def web_manifest():
    """PWA instalável — lê branding.json (actualiza com o projeto)."""
    b = load_branding()
    icons = b.get("icons", {})
    return JSONResponse(
        {
            "name": b.get("app_name_full") or b.get("app_name", "SindGreenMentor"),
            "short_name": (b.get("app_name") or "SG")[:12],
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
    payload = {
        "status": "ok",
        "engine": "futebol-betting-brain",
        "message": "Robô ligado e a responder.",
        "site_url": os.getenv("PUBLIC_SITE_URL", ""),
        "api_football": client.is_configured,
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
    payload = {
        "scanned_at": datetime.now().isoformat(timespec="seconds"),
        "total": len(fixtures),
        "source": client.last_live_source,
        "fixtures": [live_fixture_to_dict(f) for f in fixtures],
    }
    if client.last_live_source == "espn" and client.last_error:
        payload["warning"] = (
            "API-Football indisponível — lista via ESPN (grátis). "
            + client.last_error
        )
    return payload


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
        xai_api_key=os.getenv("XAI_API_KEY"),
        min_score=min_score,
        bankroll=bankroll,
        max_games=max_games,
        league_filter=league,
        prefer_live_odds=not prematch_odds,
    )
    result = ranker.scan_and_rank()
    warning = None
    if ranker.client.last_live_source == "espn" and ranker.client.last_error:
        warning = (
            "API-Football indisponível — dados via ESPN (grátis). "
            + ranker.client.last_error
        )
    return live_scan_result_to_dict(
        result,
        source=ranker.client.last_live_source,
        warning=warning,
    )


@app.get("/api/tips/history")
def api_tips_history(limit: int = 50, auto_resolve: bool = True):
    """Histórico de tips com performance — resolve outcomes se possível."""
    if auto_resolve:
        try:
            resolve_predictions(dry_run=False)
        except Exception:
            pass
    safe_limit = max(1, min(limit, 200))
    return build_history_payload(limit=safe_limit)


@app.post("/api/tips/resolve")
def api_tips_resolve():
    """Força resolução win/loss de tips pendentes."""
    _, stats = resolve_predictions(dry_run=False)
    payload = build_history_payload(limit=100)
    payload["resolve"] = {
        "resolved_now": stats.resolved,
        "still_pending": stats.still_pending,
        "hit_rate_pct": stats.hit_rate_pct,
    }
    return payload


def _build_scan_ranker(hours: int, min_score: float = 0.55, bankroll: float | None = None) -> ScanRanker:
    return ScanRanker(
        xai_api_key=os.getenv("XAI_API_KEY"),
        the_odds_api_key=os.getenv("THE_ODDS_API_KEY"),
        weather_api_key=os.getenv("OPENWEATHERMAP_API_KEY"),
        football_data_key=os.getenv("FOOTBALL_DATA_API_KEY"),
        api_football_key=os.getenv("API_FOOTBALL_KEY"),
        hours_ahead=hours,
        min_score=min_score,
        bankroll=bankroll,
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
    return scan_result_to_dict(ranker.scan_and_rank())


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")