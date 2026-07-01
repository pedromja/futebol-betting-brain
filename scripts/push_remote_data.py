#!/usr/bin/env python3
"""Envia ficheiros locais de DATA_DIR para Supabase Storage (setup inicial)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.env import load_dotenv

load_dotenv(ROOT / ".env")

from storage.remote_sync import push_all_tracked, remote_enabled, remote_status


def main() -> int:
    status = remote_status()
    if not remote_enabled():
        print("REMOTE_STORAGE: desactivado — define SUPABASE_URL e SUPABASE_SERVICE_KEY no .env")
        return 1
    print(json.dumps(status, indent=2))
    results = push_all_tracked(force=True)
    ok = sum(1 for v in results.values() if v)
    for rel, pushed in sorted(results.items()):
        mark = "OK" if pushed else "skip"
        print(f"  [{mark}] {rel}")
    print(f"\nEnviados: {ok}/{len(results)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())