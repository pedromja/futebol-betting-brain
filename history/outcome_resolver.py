"""Resolve outcomes pendentes em predictions.jsonl."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from history.market_settlement import pnl_for_outcome, settle_market
from history.predictions import DEFAULT_LOG
from history.result_fetcher import ResultFetcher


@dataclass
class ResolveStats:
    total: int
    pending: int
    resolved: int
    wins: int
    losses: int
    voids: int
    still_pending: int
    not_finished: int
    errors: int

    @property
    def hit_rate_pct(self) -> float | None:
        decided = self.wins + self.losses
        if decided == 0:
            return None
        return round(100 * self.wins / decided, 1)


def _parse_kickoff(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _is_pending(row: dict) -> bool:
    outcome = str(row.get("outcome") or "pending").lower()
    return outcome in ("pending", "", "none", "null")


def _default_row_fields(row: dict) -> None:
    row.setdefault("mode", "prematch")
    row.setdefault("outcome", "pending")
    row.setdefault("stake_level", None)
    row.setdefault("stake_label", "")
    row.setdefault("stake_pct", None)
    row.setdefault("stake_amount", None)


def resolve_predictions(
    log_path: Path | None = None,
    *,
    dry_run: bool = False,
    fetcher: ResultFetcher | None = None,
) -> tuple[list[dict], ResolveStats]:
    path = log_path or DEFAULT_LOG
    if not path.exists():
        return [], ResolveStats(0, 0, 0, 0, 0, 0, 0, 0, 0)

    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    rf = fetcher or ResultFetcher()
    now = datetime.now(timezone.utc)
    stats = ResolveStats(
        total=len(rows),
        pending=0,
        resolved=0,
        wins=0,
        losses=0,
        voids=0,
        still_pending=0,
        not_finished=0,
        errors=0,
    )

    cache: dict[str, object] = {}

    for row in rows:
        _default_row_fields(row)
        if not _is_pending(row):
            if str(row.get("outcome")).lower() == "win":
                stats.wins += 1
            elif str(row.get("outcome")).lower() == "loss":
                stats.losses += 1
            elif str(row.get("outcome")).lower() == "void":
                stats.voids += 1
            continue

        stats.pending += 1
        kickoff = _parse_kickoff(str(row.get("kickoff") or ""))
        if kickoff and kickoff > now:
            stats.not_finished += 1
            stats.still_pending += 1
            continue

        home = str(row.get("home") or "")
        away = str(row.get("away") or "")
        fid = row.get("fixture_id")
        espn_eid = str(row.get("espn_event_id") or "").strip() or None
        espn_code = str(row.get("espn_league_code") or "").strip() or None
        league = str(row.get("league") or "")
        cache_key = f"{fid}|{espn_eid}|{home}|{away}|{row.get('kickoff')}"

        if cache_key not in cache:
            cache[cache_key] = rf.resolve(
                home,
                away,
                str(row.get("kickoff") or ""),
                int(fid) if fid else None,
                espn_event_id=espn_eid,
                espn_league_code=espn_code,
                league=league,
            )

        final = cache[cache_key]
        if final is None:
            stats.still_pending += 1
            continue

        if final.status in ("CANC", "ABD"):
            row["outcome"] = "void"
            row["final_score"] = final.score_label
            row["resolved_at"] = now.isoformat(timespec="seconds")
            row["pnl"] = 0.0
            stats.resolved += 1
            stats.voids += 1
            continue

        outcome = settle_market(
            str(row.get("market") or ""),
            final.home_goals,
            final.away_goals,
        )
        stake = row.get("stake_amount") or row.get("kelly_stake")
        try:
            stake_f = float(stake) if stake is not None else None
        except (TypeError, ValueError):
            stake_f = None
        try:
            odd_f = float(row.get("odd") or 0)
        except (TypeError, ValueError):
            odd_f = 0.0

        row["outcome"] = outcome
        row["final_score"] = final.score_label
        row["resolved_at"] = now.isoformat(timespec="seconds")
        row["pnl"] = pnl_for_outcome(outcome, odd_f, stake_f)
        if final.fixture_id:
            row["fixture_id"] = final.fixture_id

        stats.resolved += 1
        if outcome == "win":
            stats.wins += 1
        elif outcome in ("void", "push"):
            stats.voids += 1
        else:
            stats.losses += 1

    if not dry_run and stats.resolved > 0:
        _write_rows(path, rows)

    return rows, stats


def _write_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    tmp.replace(path)


def format_report(stats: ResolveStats) -> str:
    lines = [
        "=" * 58,
        "  RESOLUÇÃO DE DICAS — predictions.jsonl",
        "=" * 58,
        f"  Total registos:     {stats.total}",
        f"  Pendentes:          {stats.pending}",
        f"  Resolvidos agora:   {stats.resolved}",
        f"  Ainda pendentes:    {stats.still_pending}",
        f"    (jogo futuro):    {stats.not_finished}",
        "",
        f"  Acertos (win):      {stats.wins}",
        f"  Erros (loss):       {stats.losses}",
        f"  Anulados (void):    {stats.voids}",
    ]
    rate = stats.hit_rate_pct
    if rate is not None:
        lines.append(f"  Taxa de acerto:     {rate}%")
    lines.append("=" * 58)
    return "\n".join(lines)