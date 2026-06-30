"""Preenche cache JSONL a partir de team_grandiosity.json se vazio."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from config.data_paths import (
    TM_INJURIES,
    TM_MANAGERS,
    TM_REFEREES,
    TM_SQUADS,
    TRANSFERMARKT_DIR,
    ensure_data_dir,
)
from prematch.transfermarkt.cache import _write_jsonl

_PROJECT_DATA = Path(__file__).resolve().parents[2] / "data"
_BUNDLED_TM = _PROJECT_DATA / "transfermarkt"
_GRANDIOSITY = _PROJECT_DATA / "team_grandiosity.json"

_DEFAULT_MANAGERS = {
    "Benfica": ("Roger Schmidt", "4-2-3-1"),
    "Sporting": ("Ruben Amorim", "3-4-3"),
    "FC Porto": ("Sérgio Conceição", "4-4-2"),
    "SC Braga": ("Artur Jorge", "4-2-3-1"),
    "Marítimo": ("Fábio Vieira", "4-2-3-1"),
    "Cinfães": ("Rui Ferreira", "5-4-1"),
    "Estoril": ("Ian Cathro", "4-2-3-1"),
    "Farense": ("Vítor Oliveira", "4-3-3"),
    "Paris Saint-Germain": ("Luis Enrique", "4-3-3"),
    "Nice": ("Francesco Farioli", "3-4-2-1"),
}

_DEFAULT_REFEREES = [
    {"name": "António Nobre", "yellow_avg": 5.1, "red_avg": 0.18, "penalty_avg": 0.34},
    {"name": "Manuel Mota", "yellow_avg": 4.2, "red_avg": 0.10, "penalty_avg": 0.22},
    {"name": "João Pinheiro", "yellow_avg": 3.8, "red_avg": 0.08, "penalty_avg": 0.19},
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _copy_bundled_jsonl() -> bool:
    if not _BUNDLED_TM.is_dir():
        return False
    import shutil

    copied = False
    for src in _BUNDLED_TM.glob("*.jsonl"):
        dest = TRANSFERMARKT_DIR / src.name
        if dest.exists() and dest.stat().st_size > 0:
            continue
        shutil.copy2(src, dest)
        copied = True
    return copied


def bootstrap_if_empty() -> bool:
    """Devolve True se escreveu ficheiros seed."""
    ensure_data_dir()
    TRANSFERMARKT_DIR.mkdir(parents=True, exist_ok=True)
    if _copy_bundled_jsonl():
        return True
    wrote = False
    if not TM_SQUADS.exists() or TM_SQUADS.stat().st_size == 0:
        _write_squads()
        wrote = True
    if not TM_MANAGERS.exists() or TM_MANAGERS.stat().st_size == 0:
        _write_managers()
        wrote = True
    if not TM_REFEREES.exists() or TM_REFEREES.stat().st_size == 0:
        _write_referees()
        wrote = True
    if not TM_INJURIES.exists():
        _write_jsonl(TM_INJURIES, [])
        wrote = True
    return wrote


def _write_squads() -> None:
    rows: list[dict] = []
    data = {}
    if _GRANDIOSITY.exists():
        with open(_GRANDIOSITY, encoding="utf-8") as fh:
            data = json.load(fh)
    extras = {
        "Marítimo": 15.0,
        "Cinfães": 0.5,
    }
    for key, entry in data.items():
        if key.startswith("_"):
            continue
        mv = float(entry.get("market_value_m", 0))
        rows.append({"team": key, "market_value_m": mv, "players": [], "updated_at": _now()})
    for team, mv in extras.items():
        if team not in {r["team"] for r in rows}:
            rows.append({"team": team, "market_value_m": mv, "players": [], "updated_at": _now()})
    _write_jsonl(TM_SQUADS, rows)


def _write_managers() -> None:
    rows = [
        {
            "team": team,
            "manager": mgr,
            "formation": fmt,
            "updated_at": _now(),
        }
        for team, (mgr, fmt) in _DEFAULT_MANAGERS.items()
    ]
    _write_jsonl(TM_MANAGERS, rows)


def _write_referees() -> None:
    rows = [{**ref, "updated_at": _now()} for ref in _DEFAULT_REFEREES]
    _write_jsonl(TM_REFEREES, rows)