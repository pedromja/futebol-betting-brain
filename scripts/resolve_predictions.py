#!/usr/bin/env python3
"""Resolve outcomes win/loss em data/predictions.jsonl."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.env import load_dotenv

load_dotenv(ROOT / ".env")

from history.outcome_resolver import format_report, resolve_predictions
from history.predictions import DEFAULT_LOG


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Preenche outcome (win/loss) de dicas com jogos terminados"
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_LOG,
        help="Caminho do ficheiro JSONL (default: data/predictions.jsonl)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simular sem gravar alterações",
    )
    args = parser.parse_args()

    _, stats = resolve_predictions(args.file, dry_run=args.dry_run)
    print("\n" + format_report(stats))
    if args.dry_run and stats.resolved:
        print("\n  (dry-run — nada gravado)")
    elif stats.resolved:
        print(f"\n  Gravado em: {args.file}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())