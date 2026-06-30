"""Actualiza perfis históricos (fecho + estilo) a partir de CSV football-data.co.uk."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.data_paths import HISTORICAL_TEAM_PROFILES
from prematch.historical.aggregate import ingest_league
from prematch.historical.sources import LEAGUE_FILES, DEFAULT_SEASON
from prematch.historical.store import get_store


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Agrega CSV football-data.co.uk → team_profiles.jsonl"
    )
    parser.add_argument(
        "--leagues",
        default="PPL",
        help="Códigos separados por vírgula (PPL, PL, PD, SA, BL1, FL1, DED)",
    )
    parser.add_argument("--season", default=DEFAULT_SEASON, help="Época ex: 2526")
    args = parser.parse_args()

    codes = [c.strip().upper() for c in args.leagues.split(",") if c.strip()]
    store = get_store()
    total = 0

    print(f"Destino: {HISTORICAL_TEAM_PROFILES}")
    for code in codes:
        if code not in LEAGUE_FILES:
            print(f"  SKIP {code}: liga desconhecida")
            continue
        print(f"  Sync {code} ({args.season})…")
        profiles = ingest_league(code, season=args.season)
        if not profiles:
            print(f"  ERRO {code}: download ou CSV vazio")
            continue
        n = store.upsert_many(profiles)
        total += n
        print(f"  OK {code}: {n} equipas")

    print(f"\nConcluído: {total} perfis ({len(store._index)} no cache)")


if __name__ == "__main__":
    main()