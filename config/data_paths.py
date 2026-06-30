"""Caminhos de dados persistentes — local ou disco Render (DATA_DIR)."""

from __future__ import annotations

import os
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_DATA = _PROJECT_ROOT / "data"

DATA_DIR = Path(os.getenv("DATA_DIR", str(_DEFAULT_DATA)))
PREDICTIONS_LOG = DATA_DIR / "predictions.jsonl"
LIVE_STATS_SNAPSHOTS = DATA_DIR / "live_stats_snapshots.jsonl"
PUSH_SUBSCRIPTIONS = DATA_DIR / "push_subscriptions.jsonl"
BOTS_FILE = DATA_DIR / "bots.jsonl"
TRANSFERMARKT_DIR = DATA_DIR / "transfermarkt"
TM_SQUADS = TRANSFERMARKT_DIR / "squads.jsonl"
TM_MANAGERS = TRANSFERMARKT_DIR / "managers.jsonl"
TM_MANAGER_H2H = TRANSFERMARKT_DIR / "manager_h2h.jsonl"
TM_REFEREES = TRANSFERMARKT_DIR / "referees.jsonl"
TM_INJURIES = TRANSFERMARKT_DIR / "injuries.jsonl"
TM_FIXTURE_REFS = TRANSFERMARKT_DIR / "fixture_refs.jsonl"
HISTORICAL_DIR = DATA_DIR / "historical"
HISTORICAL_TEAM_PROFILES = HISTORICAL_DIR / "team_profiles.jsonl"


def ensure_data_dir() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR