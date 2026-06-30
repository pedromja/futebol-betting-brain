"""Leitura e escrita de cache JSONL Transfermarkt."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypeVar

from config.data_paths import (
    TM_FIXTURE_REFS,
    TM_INJURIES,
    TM_MANAGER_H2H,
    TM_MANAGERS,
    TM_REFEREES,
    TM_SQUADS,
    TRANSFERMARKT_DIR,
    ensure_data_dir,
)

T = TypeVar("T")


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    return rows


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    ensure_data_dir()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def append_jsonl(path: Path, row: dict) -> None:
    ensure_data_dir()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def index_by_team(rows: list[dict], team_field: str = "team") -> dict[str, dict]:
    out: dict[str, dict] = {}
    for row in rows:
        team = str(row.get(team_field) or "").strip()
        if team:
            out[team] = row
    return out


def index_by_key(rows: list[dict], key_field: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for row in rows:
        key = str(row.get(key_field) or "").strip()
        if key:
            out[key] = row
    return out


def load_squads() -> dict[str, dict]:
    return index_by_team(_read_jsonl(TM_SQUADS))


def load_managers() -> dict[str, dict]:
    return index_by_team(_read_jsonl(TM_MANAGERS))


def load_manager_h2h() -> dict[str, dict]:
    return index_by_key(_read_jsonl(TM_MANAGER_H2H), "key")


def load_referees() -> dict[str, dict]:
    return index_by_key(_read_jsonl(TM_REFEREES), "name")


def load_injuries() -> dict[str, dict]:
    return index_by_team(_read_jsonl(TM_INJURIES))


def load_fixture_refs() -> dict[str, dict]:
    return index_by_key(_read_jsonl(TM_FIXTURE_REFS), "fixture_key")


def cache_paths() -> dict[str, str]:
    return {
        "dir": str(TRANSFERMARKT_DIR),
        "squads": str(TM_SQUADS),
        "managers": str(TM_MANAGERS),
        "manager_h2h": str(TM_MANAGER_H2H),
        "referees": str(TM_REFEREES),
        "injuries": str(TM_INJURIES),
        "fixture_refs": str(TM_FIXTURE_REFS),
    }