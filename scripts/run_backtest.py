#!/usr/bin/env python3
"""CLI — backtest multi-liga pré-jogo vs IA live."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.runner import run_backtest, save_backtest_results  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Backtest CSV multi-liga")
    parser.add_argument(
        "--leagues",
        default="PPL,PL,PD,SA,BL1,FL1",
        help="Códigos separados por vírgula (default: top 6)",
    )
    parser.add_argument(
        "--seasons",
        default="2324,2425,2526",
        help="Épocas football-data (ex: 2324,2425,2526)",
    )
    parser.add_argument("--min-score", type=float, default=0.55, help="min_score base")
    parser.add_argument("--out", default="", help="Ficheiro JSON de saída (opcional)")
    args = parser.parse_args()

    leagues = tuple(x.strip() for x in args.leagues.split(",") if x.strip())
    seasons = tuple(x.strip() for x in args.seasons.split(",") if x.strip())
    payload = run_backtest(leagues=leagues, seasons=seasons, base_min_score=args.min_score)
    save_backtest_results(payload)

    if args.out:
        Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    pm = payload.get("prematch") or {}
    live = payload.get("live_ia") or {}
    print(f"Jogos: {payload['config']['matches_parsed']}")
    print(
        f"Pré-jogo: {pm.get('samples', 0)} apostas · "
        f"{pm.get('hit_rate_pct', '—')}% · ROI {pm.get('roi_pct', '—')}%"
    )
    print(
        f"IA live:  {live.get('samples', 0)} apostas · "
        f"{live.get('hit_rate_pct', '—')}% · ROI {live.get('roi_pct', '—')}%"
    )
    comp = payload.get("competitions") or {}
    cs = comp.get("summary") or {}
    print(
        f"Torneios: {comp.get('matches_parsed', 0)} jogos · "
        f"{cs.get('samples', 0)} apostas · {cs.get('hit_rate_pct', '—')}% · ROI {cs.get('roi_pct', '—')}%"
    )
    for a in comp.get("assumptions") or []:
        v = a.get("validated")
        mark = "OK" if v is True else "NO" if v is False else "??"
        print(f"  [{mark}] {a.get('label')}: {a.get('detail')}")
    print("Por tier (pré-jogo):")
    for row in pm.get("by_tier") or []:
        print(
            f"  {row['key']}: {row.get('samples', 0)} · "
            f"{row.get('hit_rate_pct', '—')}% · ROI {row.get('roi_pct', '—')}%"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())