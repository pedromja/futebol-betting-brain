"""Acesso unificado ao cache Transfermarkt."""

from __future__ import annotations

from prematch.transfermarkt import bootstrap
from prematch.transfermarkt.cache import (
    load_fixture_refs,
    load_injuries,
    load_manager_h2h,
    load_managers,
    load_referees,
    load_squads,
)
from prematch.transfermarkt.match_names import find_in_index, team_key
from prematch.transfermarkt.types import (
    ManagerH2H,
    ManagerProfile,
    PlayerAbsence,
    RefereeProfile,
    SquadSnapshot,
)


class TransfermarktStore:
    def __init__(self) -> None:
        bootstrap.bootstrap_if_empty()
        self._squads = load_squads()
        self._managers = load_managers()
        self._h2h = load_manager_h2h()
        self._referees = load_referees()
        self._injuries = load_injuries()
        self._fixture_refs = load_fixture_refs()

    def reload(self) -> None:
        self._squads = load_squads()
        self._managers = load_managers()
        self._h2h = load_manager_h2h()
        self._referees = load_referees()
        self._injuries = load_injuries()
        self._fixture_refs = load_fixture_refs()

    def squad(self, team: str) -> SquadSnapshot | None:
        hit = find_in_index(team, self._squads)
        if not hit:
            return None
        key, row = hit
        return SquadSnapshot(
            team=key,
            market_value_m=float(row.get("market_value_m") or 0),
            players=list(row.get("players") or []),
            updated_at=str(row.get("updated_at") or ""),
        )

    def manager(self, team: str) -> ManagerProfile | None:
        hit = find_in_index(team, self._managers)
        if not hit:
            return None
        key, row = hit
        return ManagerProfile(
            team=key,
            manager=str(row.get("manager") or ""),
            formation=str(row.get("formation") or "4-2-3-1"),
            updated_at=str(row.get("updated_at") or ""),
        )

    def manager_h2h(self, manager_a: str, manager_b: str) -> ManagerH2H | None:
        if not manager_a or not manager_b:
            return None
        keys = [
            f"{manager_a}|{manager_b}",
            f"{manager_b}|{manager_a}",
        ]
        row = None
        swapped = False
        for i, key in enumerate(keys):
            if key in self._h2h:
                row = self._h2h[key]
                swapped = i == 1
                break
        if not row:
            return None
        wins_a = int(row.get("wins_a") or 0)
        losses_a = int(row.get("losses_a") or 0)
        if swapped:
            wins_a, losses_a = losses_a, wins_a
        return ManagerH2H(
            manager_a=manager_a,
            manager_b=manager_b,
            wins_a=wins_a,
            draws=int(row.get("draws") or 0),
            losses_a=losses_a,
            avg_goals=float(row.get("avg_goals") or 2.5),
            updated_at=str(row.get("updated_at") or ""),
        )

    def referee_for_fixture(self, home: str, away: str) -> RefereeProfile | None:
        fk = f"{team_key(home)}|{team_key(away)}"
        row = self._fixture_refs.get(fk)
        if not row:
            alt = f"{home.strip().lower()}|{away.strip().lower()}"
            row = self._fixture_refs.get(alt)
        if row:
            name = str(row.get("referee") or "")
            return self.referee(name)
        return None

    def referee(self, name: str) -> RefereeProfile | None:
        if not name:
            return None
        row = self._referees.get(name)
        if not row:
            lower = name.lower()
            for key, val in self._referees.items():
                if lower in key.lower() or key.lower() in lower:
                    row = val
                    name = key
                    break
        if not row:
            return None
        return RefereeProfile(
            name=name,
            yellow_avg=float(row.get("yellow_avg") or 4.0),
            red_avg=float(row.get("red_avg") or 0.12),
            penalty_avg=float(row.get("penalty_avg") or 0.25),
            updated_at=str(row.get("updated_at") or ""),
        )

    def absences(self, team: str) -> list[PlayerAbsence]:
        hit = find_in_index(team, self._injuries)
        if not hit:
            return []
        _, row = hit
        out: list[PlayerAbsence] = []
        for item in row.get("absences") or []:
            out.append(
                PlayerAbsence(
                    name=str(item.get("name") or ""),
                    status=str(item.get("status") or "injured"),
                    days_out=int(item.get("days_out") or 0),
                    games_missed=int(item.get("games_missed") or 0),
                    market_value_m=float(item.get("market_value_m") or 0),
                    replacement_value_m=float(item.get("replacement_value_m") or 0),
                    injury_history=str(item.get("injury_history") or "unknown"),
                    expected_return=str(item.get("expected_return") or ""),
                )
            )
        return out

    def has_data_for(self, home: str, away: str) -> bool:
        return bool(self.squad(home) or self.squad(away))


_STORE: TransfermarktStore | None = None


def get_store() -> TransfermarktStore:
    global _STORE
    if _STORE is None:
        _STORE = TransfermarktStore()
    return _STORE