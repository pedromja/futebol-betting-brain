"""Reavaliação pós-jogo — reconfirma resultado e enriquece com stats finais."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from config.data_paths import BOT_SIGNALS_LOG, PREDICTIONS_LOG
from discovery.api_football_client import ApiFootballClient
from discovery.match_stats import fetch_match_live_stats
from discovery.match_stats_types import MatchLiveStatsBundle
from history.market_settlement import pnl_for_outcome, settle_market
from history.outcome_resolver import _write_rows
from history.result_fetcher import FinalScore, ResultFetcher

_REVIEWABLE = frozenset({"win", "loss", "void"})
_MAX_FETCH_DEFAULT = 10


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _is_resolved(row: dict) -> bool:
    return str(row.get("outcome") or "pending").lower() in _REVIEWABLE


def _needs_review(row: dict) -> bool:
    if not _is_resolved(row):
        return False
    review = row.get("review") or {}
    status = str(review.get("status") or "")
    if status in ("", "pending"):
        return True
    if status == "needs_verification":
        attempts = int(review.get("attempts") or 0)
        return attempts < 3
    return False


def _ft_stats_summary(bundle: MatchLiveStatsBundle) -> dict:
    h, a = bundle.home, bundle.away
    home_xg, away_xg = h.xg, a.xg
    total_xg = None
    if home_xg is not None and away_xg is not None:
        total_xg = round(home_xg + away_xg, 2)
    hy = h.yellow_cards or 0
    ay = a.yellow_cards or 0
    hr = h.red_cards or 0
    ar = a.red_cards or 0
    goals = [e for e in bundle.events if e.type.lower() == "goal"]
    cards = [e for e in bundle.events if "card" in e.type.lower()]
    return {
        "xg": {
            "home": home_xg,
            "away": away_xg,
            "total": total_xg,
            "source": bundle.xg_source,
        },
        "shots_on": {"home": h.shots_on, "away": a.shots_on},
        "corners": {"home": h.corners, "away": a.corners},
        "cards": {
            "yellow": hy + ay,
            "red": hr + ar,
            "home_yellow": h.yellow_cards,
            "away_yellow": a.yellow_cards,
        },
        "possession_pct": {"home": h.possession_pct, "away": a.possession_pct},
        "events_goals": len(goals),
        "events_cards": len(cards),
    }


def _market_context_note(row: dict, summary: dict, final: FinalScore | None) -> str:
    market = str(row.get("market") or "")
    lower = market.lower()
    parts: list[str] = []

    if final:
        total_goals = final.home_goals + final.away_goals
        parts.append(f"Resultado FT {final.score_label} ({total_goals} golos)")

    xg = summary.get("xg") or {}
    if xg.get("total") is not None:
        src = xg.get("source") or "api"
        parts.append(f"xG total {xg['total']} ({src})")

    cards = summary.get("cards") or {}
    if cards.get("yellow") is not None:
        parts.append(f"{cards['yellow']} amarelos, {cards.get('red') or 0} vermelhos")

    if "over" in lower and "2.5" in lower:
        tg = (final.home_goals + final.away_goals) if final else None
        if tg is not None:
            parts.append("linha Over 2.5 batida" if tg > 2 else "linha Over 2.5 não batida")
        if xg.get("total") is not None:
            parts.append(
                "xG suporta over" if xg["total"] > 2.4 else "xG abaixo da linha over"
            )
    elif "under" in lower and "2.5" in lower:
        tg = (final.home_goals + final.away_goals) if final else None
        if tg is not None:
            parts.append("under confirmado" if tg <= 2 else "under falhou")
    elif "btts" in lower:
        if final:
            both = final.home_goals > 0 and final.away_goals > 0
            parts.append("ambas marcaram" if both else "nem ambas marcaram")

    minute = row.get("minute")
    score_at = row.get("score_at_tip")
    if minute is not None and str(row.get("mode")) == "live":
        parts.append(f"sinal ao vivo {score_at or '?'} aos {minute}'")

    return " · ".join(parts) if parts else "Stats finais disponíveis"


def _build_verify_prompt(row: dict, *, sources_tried: list[str], reason: str) -> str:
    home = row.get("home") or "?"
    away = row.get("away") or "?"
    league = row.get("league") or ""
    market = row.get("market") or "?"
    odd = row.get("odd") or "?"
    outcome = str(row.get("outcome") or "pending").upper()
    final_score = row.get("final_score") or "pendente"
    pnl = row.get("pnl")
    pnl_txt = f"{pnl:+.2f}€" if pnl is not None else "—"
    bot_line = ""
    if row.get("bot_name"):
        bot_line = f"• Bot: {row.get('bot_name')}\n"
    sources = ", ".join(sources_tried) or "nenhuma"
    return (
        f"Verifica manualmente esta aposta:\n"
        f"• {home} vs {away}"
        f"{f' ({league})' if league else ''}\n"
        f"{bot_line}"
        f"• Mercado: {market} @ {odd}\n"
        f"• Avaliação automática: {outcome} · FT {final_score} · PnL {pnl_txt}\n"
        f"• Motivo: {reason}\n"
        f"• Fontes tentadas: {sources}\n"
        f"Confirma em SofaScore, Flashscore ou no teu histórico de apostas "
        f"se o resultado e o mercado estão corretos."
    )


def _reconfirm_outcome(row: dict, final: FinalScore, now: str) -> bool:
    """Reconsulta resultado final; actualiza outcome/pnl se o score mudou."""
    if str(row.get("outcome") or "").lower() == "void":
        return False
    if final.status in ("CANC", "ABD"):
        row["outcome"] = "void"
        row["final_score"] = final.score_label
        row["pnl"] = 0.0
        row["resolved_at"] = now
        return True

    market = str(row.get("market") or "")
    new_outcome = settle_market(market, final.home_goals, final.away_goals)
    old_outcome = str(row.get("outcome") or "")
    changed = new_outcome != old_outcome or row.get("final_score") != final.score_label

    row["outcome"] = new_outcome
    row["final_score"] = final.score_label
    row["resolved_at"] = now
    if final.fixture_id:
        row["fixture_id"] = final.fixture_id

    try:
        odd_f = float(row.get("odd") or 0)
        stake = row.get("stake_amount") or row.get("kelly_stake")
        stake_f = float(stake) if stake is not None else None
        row["pnl"] = pnl_for_outcome(new_outcome, odd_f, stake_f)
    except (TypeError, ValueError):
        pass
    return changed


def build_review(
    row: dict,
    *,
    final: FinalScore | None,
    bundle: MatchLiveStatsBundle | None,
    sources_tried: list[str],
    reason: str = "",
) -> dict:
    now = _now_iso()
    prev = row.get("review") or {}
    attempts = int(prev.get("attempts") or 0) + 1

    if bundle:
        summary = _ft_stats_summary(bundle)
        note = _market_context_note(row, summary, final)
        outcome = str(row.get("outcome") or "")
        return {
            "status": "enriched",
            "attempts": attempts,
            "reviewed_at": now,
            "sources": sources_tried,
            "outcome_confirmed": True,
            "context_note": note,
            "ft_stats": summary,
            "ft_stats_full": bundle.to_dict(),
            "verify_prompt": None,
        }

    prompt = _build_verify_prompt(row, sources_tried=sources_tried, reason=reason)
    return {
        "status": "initial_only",
        "attempts": attempts,
        "reviewed_at": now,
        "sources": sources_tried,
        "outcome_confirmed": final is not None,
        "context_note": (
            f"Avaliação inicial mantida ({str(row.get('outcome') or '').upper()}) — "
            f"sem stats FT automáticas"
        ),
        "verify_prompt": prompt,
        "needs_verification": True,
    }


def enrich_resolved_log(
    log_path: Path,
    *,
    max_fetch: int = _MAX_FETCH_DEFAULT,
    dry_run: bool = False,
    fetcher: ResultFetcher | None = None,
    client: ApiFootballClient | None = None,
) -> tuple[int, int, int]:
    """
    Reavalia entradas resolvidas sem review completo.
    Devolve (revisadas, enriquecidas, precisam_verificação).
    """
    if not log_path.exists():
        return 0, 0, 0

    rows: list[dict] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    rf = fetcher or ResultFetcher()
    api = client or ApiFootballClient()
    now = _now_iso()
    fetched = 0
    reviewed = enriched = needs_verify = 0
    score_cache: dict[str, FinalScore | None] = {}
    stats_cache: dict[int, MatchLiveStatsBundle | None] = {}

    for row in rows:
        if not _needs_review(row):
            continue
        if fetched >= max_fetch:
            break

        sources_tried: list[str] = []
        home = str(row.get("home") or "")
        away = str(row.get("away") or "")
        kickoff = str(row.get("kickoff") or "")
        fid = row.get("fixture_id")
        try:
            fid_int = int(fid) if fid else None
        except (TypeError, ValueError):
            fid_int = None

        cache_key = f"{fid_int}|{home}|{away}|{kickoff}"
        if cache_key not in score_cache:
            score_cache[cache_key] = rf.resolve(home, away, kickoff, fid_int)
            sources_tried.append("api-football")
            if score_cache[cache_key] is None:
                sources_tried.append("espn")

        final = score_cache[cache_key]
        if final:
            _reconfirm_outcome(row, final, now)
            if final.fixture_id and not fid_int:
                fid_int = int(final.fixture_id)
                row["fixture_id"] = fid_int

        bundle = None
        if fid_int and api.is_configured and not api.quota_exhausted:
            if fid_int not in stats_cache:
                stats_cache[fid_int] = fetch_match_ft_stats(
                    api, fid_int, include_events=True
                )
                fetched += 1
            bundle = stats_cache[fid_int]
            if bundle:
                sources_tried.append("api-football-stats")

        reason = ""
        if not final:
            reason = "resultado final não encontrado nas fontes automáticas"
        elif not bundle:
            if not fid_int:
                reason = "fixture_id em falta — impossível obter xG/cartões"
            elif not api.is_configured:
                reason = "API-Football não configurada"
            else:
                reason = "estatísticas FT indisponíveis na API"

        row["review"] = build_review(
            row,
            final=final,
            bundle=bundle,
            sources_tried=sources_tried,
            reason=reason,
        )
        reviewed += 1
        if row["review"]["status"] == "enriched":
            enriched += 1
        elif row["review"].get("needs_verification"):
            needs_verify += 1

    if not dry_run and reviewed > 0:
        _write_rows(log_path, rows)

    return reviewed, enriched, needs_verify


def fetch_match_ft_stats(
    client: ApiFootballClient,
    fixture_id: int,
    *,
    include_events: bool = True,
) -> MatchLiveStatsBundle | None:
    """Stats finais — cache longo (24h), adequado a pós-jogo."""
    stats_data = client.fetch_fixture_statistics_ft(fixture_id)
    from discovery.match_stats import parse_events_response, parse_statistics_response
    from discovery.xg_estimate import enrich_bundle_xg

    bundle = parse_statistics_response(fixture_id, stats_data)
    if not bundle:
        return None
    if include_events:
        events_data = client.fetch_fixture_events_ft(fixture_id)
        bundle.events = parse_events_response(events_data)
    return enrich_bundle_xg(bundle)


def enrich_all_resolved_logs(
    *,
    max_fetch: int = _MAX_FETCH_DEFAULT,
    dry_run: bool = False,
) -> dict:
    tips_r, tips_e, tips_v = enrich_resolved_log(
        PREDICTIONS_LOG, max_fetch=max_fetch, dry_run=dry_run
    )
    remaining = max(0, max_fetch - tips_r)
    bots_r, bots_e, bots_v = enrich_resolved_log(
        BOT_SIGNALS_LOG, max_fetch=remaining, dry_run=dry_run
    )
    return {
        "reviewed": tips_r + bots_r,
        "enriched": tips_e + bots_e,
        "needs_verification": tips_v + bots_v,
        "tips": {"reviewed": tips_r, "enriched": tips_e, "needs_verification": tips_v},
        "bots": {"reviewed": bots_r, "enriched": bots_e, "needs_verification": bots_v},
    }


def build_verify_queue(
    *,
    limit: int = 20,
) -> list[dict]:
    """Entradas que precisam verificação manual — com prompt pronto."""
    queue: list[dict] = []
    for path, kind in ((PREDICTIONS_LOG, "tip"), (BOT_SIGNALS_LOG, "bot")):
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            review = row.get("review") or {}
            if not review.get("needs_verification") and review.get("status") != "initial_only":
                continue
            prompt = review.get("verify_prompt")
            if not prompt:
                continue
            entry = {
                "kind": kind,
                "id": row.get("signature") or row.get("logged_at"),
                "home": row.get("home"),
                "away": row.get("away"),
                "market": row.get("market"),
                "outcome": row.get("outcome"),
                "final_score": row.get("final_score"),
                "pnl": row.get("pnl"),
                "prompt": prompt,
                "reviewed_at": review.get("reviewed_at"),
            }
            if kind == "bot":
                entry["bot_id"] = row.get("bot_id")
                entry["bot_name"] = row.get("bot_name")
            queue.append(entry)
    queue.sort(key=lambda x: str(x.get("reviewed_at") or ""), reverse=True)
    return queue[:limit]