"""Temperatura do jogo (lista live) e série de pressão (detalhe ao seleccionar)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class GameTemperature:
    level: str  # calm | warm | hot
    events_per_min: float
    label: str
    goals: int
    minute: int
    hint: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "events_per_min": round(self.events_per_min, 3),
            "label": self.label,
            "goals": self.goals,
            "minute": self.minute,
            "hint": self.hint,
        }


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def compute_home_pressure(
    *,
    home_xg: float,
    away_xg: float,
    home_possession_pct: float | None,
    home_shots_on: int | None,
    away_shots_on: int | None,
) -> float:
    """Pressão casa 0–100 (50 = equilibrado)."""
    hp = (home_possession_pct or 50) / 100.0
    hso = home_shots_on or 0
    aso = away_shots_on or 0
    shot_total = max(hso + aso, 1)
    shot_bias = (hso - aso) / shot_total
    xg_delta = home_xg - away_xg
    score = 50.0 + 22.0 * xg_delta + 16.0 * (hp - 0.5) + 12.0 * shot_bias
    return round(_clamp(score, 0.0, 100.0), 1)


def compute_temperature(
    *,
    minute: int,
    home_score: int,
    away_score: int,
    status: str = "",
    ht_home_score: int | None = None,
    ht_away_score: int | None = None,
    snapshot_prev: dict | None = None,
    snapshot_last: dict | None = None,
) -> GameTemperature:
    """
    Temperatura leve para a grelha — sem pedidos API extra.
    Verde/amarelo/vermelho ≈ eventos ponderados por minuto.
    """
    eff_min = max(int(minute or 0), 1)
    goals = int(home_score or 0) + int(away_score or 0)
    goal_epm = goals / eff_min

    burst = 0.0
    if ht_home_score is not None and ht_away_score is not None and eff_min > 45:
        ht_goals = int(ht_home_score) + int(ht_away_score)
        sh_goals = max(0, goals - ht_goals)
        sh_min = max(eff_min - 45, 1)
        burst = (sh_goals / sh_min) * 1.4

    activity = 0.0
    if snapshot_prev and snapshot_last:
        m0 = int(snapshot_prev.get("minute") or 0)
        m1 = int(snapshot_last.get("minute") or max(m0, 1))
        dm = max(m1 - m0, 1)
        g0 = int(snapshot_prev.get("home_score") or 0) + int(snapshot_prev.get("away_score") or 0)
        g1 = int(snapshot_last.get("home_score") or 0) + int(snapshot_last.get("away_score") or 0)
        c0 = int(snapshot_prev.get("total_corners") or 0)
        c1 = int(snapshot_last.get("total_corners") or 0)
        k0 = int(snapshot_prev.get("total_cards") or 0)
        k1 = int(snapshot_last.get("total_cards") or 0)
        s0 = int(snapshot_prev.get("home_shots_on") or 0) + int(snapshot_prev.get("away_shots_on") or 0)
        s1 = int(snapshot_last.get("home_shots_on") or 0) + int(snapshot_last.get("away_shots_on") or 0)
        activity = (
            abs(g1 - g0) * 3.0
            + abs(c1 - c0) * 0.45
            + abs(k1 - k0) * 1.1
            + abs(s1 - s0) * 0.2
        ) / dm

    events_per_min = goal_epm * 2.2 + burst + activity
    st = str(status or "").upper()
    if st == "HT":
        events_per_min *= 0.55

    if events_per_min >= 0.13:
        level, label = "hot", "Quente"
    elif events_per_min >= 0.055:
        level, label = "warm", "Morno"
    else:
        level, label = "calm", "Frio"

    hint = f"{events_per_min:.2f} evt/min · {goals} golos · {eff_min}'"
    if activity > 0.08:
        hint += " · ritmo alto (stats)"
    elif burst >= 0.1:
        hint += " · 2.ª parte acelerada"

    return GameTemperature(
        level=level,
        events_per_min=events_per_min,
        label=label,
        goals=goals,
        minute=eff_min,
        hint=hint,
    )


def temperature_from_fixture_dict(
    fx: dict,
    *,
    snapshot_prev: dict | None = None,
    snapshot_last: dict | None = None,
) -> dict[str, Any]:
    return compute_temperature(
        minute=int(fx.get("minute") or 0),
        home_score=int(fx.get("home_score") or 0),
        away_score=int(fx.get("away_score") or 0),
        status=str(fx.get("status") or ""),
        ht_home_score=fx.get("ht_home_score"),
        ht_away_score=fx.get("ht_away_score"),
        snapshot_prev=snapshot_prev,
        snapshot_last=snapshot_last,
    ).to_dict()


def build_pressure_analysis(history: list[dict]) -> dict[str, Any]:
    """Série de pressão e intensidade — só para página de detalhe."""
    if not history:
        return {"available": False, "points": 0, "series": [], "current": None}

    series: list[dict[str, Any]] = []
    prev: dict | None = None
    for row in history:
        hxg = float(row.get("home_xg") or 0)
        axg = float(row.get("away_xg") or 0)
        home_p = compute_home_pressure(
            home_xg=hxg,
            away_xg=axg,
            home_possession_pct=row.get("home_possession_pct"),
            home_shots_on=row.get("home_shots_on"),
            away_shots_on=row.get("away_shots_on"),
        )
        away_p = round(100.0 - home_p, 1)
        intensity = 0.0
        if prev is not None:
            dm = max(int(row.get("minute") or 0) - int(prev.get("minute") or 0), 1)
            dg = abs(
                int(row.get("home_score") or 0)
                + int(row.get("away_score") or 0)
                - int(prev.get("home_score") or 0)
                - int(prev.get("away_score") or 0)
            )
            dc = abs(int(row.get("total_corners") or 0) - int(prev.get("total_corners") or 0))
            dk = abs(int(row.get("total_cards") or 0) - int(prev.get("total_cards") or 0))
            intensity = round((dg * 3 + dc * 0.5 + dk * 1.2) / dm, 3)
        series.append(
            {
                "minute": row.get("minute"),
                "home_xg": hxg,
                "away_xg": axg,
                "home_possession_pct": row.get("home_possession_pct"),
                "total_corners": row.get("total_corners"),
                "home_pressure": home_p,
                "away_pressure": away_p,
                "intensity": intensity,
                "home_score": row.get("home_score"),
                "away_score": row.get("away_score"),
            }
        )
        prev = row

    last = series[-1]
    hp = float(last["home_pressure"])
    if hp >= 62:
        side_label = "Pressão casa"
    elif hp <= 38:
        side_label = "Pressão fora"
    else:
        side_label = "Equilibrado"

    return {
        "available": len(series) >= 1,
        "points": len(series),
        "series": series,
        "current": {
            "home_pressure": last["home_pressure"],
            "away_pressure": last["away_pressure"],
            "intensity": last["intensity"],
            "label": side_label,
            "minute": last.get("minute"),
        },
    }