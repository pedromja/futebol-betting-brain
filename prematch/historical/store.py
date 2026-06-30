"""Cache JSONL — perfis históricos por equipa."""

from __future__ import annotations

import json

from config.data_paths import HISTORICAL_TEAM_PROFILES, ensure_data_dir
from prematch.historical.sources import league_to_code
from prematch.historical.types import TeamHistoricalProfile
from prematch.transfermarkt.match_names import find_in_index, team_key


def _read_jsonl(path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _write_jsonl(path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows)
    path.write_text(text + ("\n" if text else ""), encoding="utf-8")


class HistoricalStore:
    def __init__(self) -> None:
        self._index: dict[str, TeamHistoricalProfile] = {}
        self.reload()

    def reload(self) -> None:
        self._index = {}
        for row in _read_jsonl(HISTORICAL_TEAM_PROFILES):
            profile = TeamHistoricalProfile.from_dict(row)
            if profile.team:
                self._index[profile.team] = profile

    def upsert_many(self, profiles: list[TeamHistoricalProfile]) -> int:
        ensure_data_dir()
        rows = _read_jsonl(HISTORICAL_TEAM_PROFILES)
        by_team = {str(r.get("team")): r for r in rows}
        for p in profiles:
            by_team[p.team] = p.to_dict()
        _write_jsonl(HISTORICAL_TEAM_PROFILES, list(by_team.values()))
        self.reload()
        return len(profiles)

    def profile(self, team_name: str, *, league: str = "") -> TeamHistoricalProfile | None:
        hit = find_in_index(team_name, self._index)
        if hit:
            return hit[1]  # type: ignore[return-value]
        code = league_to_code(league)
        if not code:
            return None
        needle = team_key(team_name)
        for key, prof in self._index.items():
            if prof.league == code and (
                team_key(key) == needle or needle in team_key(key) or team_key(key) in needle
            ):
                return prof
        return None


_store: HistoricalStore | None = None


def get_store() -> HistoricalStore:
    global _store
    if _store is None:
        _store = HistoricalStore()
    return _store