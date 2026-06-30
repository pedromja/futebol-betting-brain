"""Actualiza cache Transfermarkt — edita JSONL ou copia do bundle do projeto."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from prematch.transfermarkt.bootstrap import bootstrap_if_empty
from prematch.transfermarkt.cache import cache_paths


def main() -> None:
    wrote = bootstrap_if_empty()
    paths = cache_paths()
    print("Cache Transfermarkt")
    for key, val in paths.items():
        print(f"  {key}: {val}")
    if wrote:
        print("  Seed/bundle copiado para DATA_DIR.")
    else:
        print("  Cache já existente — edita os JSONL ou adiciona linhas novas.")
    print()
    print("Ficheiros: squads, managers, manager_h2h, referees, injuries, fixture_refs")


if __name__ == "__main__":
    main()