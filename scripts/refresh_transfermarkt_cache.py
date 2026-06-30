"""Actualiza cache Transfermarkt — bundle local ou sync via transfermarkt-api."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from prematch.transfermarkt.bootstrap import bootstrap_if_empty
from prematch.transfermarkt.cache import cache_paths
from prematch.transfermarkt.sync import log_sync_event, sync_teams_from_api
from prematch.transfermarkt.store import get_store


def main() -> None:
    parser = argparse.ArgumentParser(description="Cache Transfermarkt (JSONL)")
    parser.add_argument(
        "--sync",
        metavar="TEAMS",
        help="Equipas separadas por vírgula (ex: Benfica,Marítimo,Cinfães)",
    )
    parser.add_argument(
        "--country",
        default="Portugal",
        help="País preferido na pesquisa de clubes (default: Portugal)",
    )
    args = parser.parse_args()

    bootstrap_if_empty()
    paths = cache_paths()
    print("Cache Transfermarkt")
    for key, val in paths.items():
        print(f"  {key}: {val}")

    if args.sync:
        teams = [t.strip() for t in args.sync.split(",") if t.strip()]
        print(f"\nSync API: {len(teams)} equipa(s)…")
        summary = sync_teams_from_api(teams, prefer_country=args.country)
        log_sync_event(summary)
        get_store().reload()
        for row in summary.get("results") or []:
            if row.get("ok"):
                print(
                    f"  OK {row['team']}: {row['market_value_m']}M · "
                    f"{row['players']} jogadores · {row['absences']} ausências"
                )
            else:
                print(f"  ERRO {row.get('team', '?')}: {row.get('error')}")
        print(f"\nConcluído: {summary['synced']}/{summary['total']}")
        return

    print("\nSem --sync: usa bundle/seed local.")
    print("Exemplo: python scripts/refresh_transfermarkt_cache.py --sync Benfica,Maritimo")


if __name__ == "__main__":
    main()