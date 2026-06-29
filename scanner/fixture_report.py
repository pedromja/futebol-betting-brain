"""Tabela de jogos descobertos — sem análise de mercados."""

import re
from datetime import datetime, timezone

from discovery.fixture_types import UpcomingFixture


class FixtureListReport:
    WIDTH = 78

    def _format_kickoff(self, fixture: UpcomingFixture) -> str:
        dt = fixture.kickoff_dt
        if dt:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.strftime("%d/%m %H:%M UTC")
        raw = fixture.kickoff.replace("T", " ")[:16]
        return raw or "—"

    def _short_stage(self, stage: str) -> str:
        key = stage.strip().lower()
        shortcuts = {
            "group stage": "Grupos",
            "round of 16": "Oitavos",
            "quarter-finals": "Quartos",
            "quarterfinals": "Quartos",
            "semi-finals": "Meias",
            "semifinals": "Meias",
            "final": "Final",
        }
        for pattern, label in shortcuts.items():
            if pattern in key:
                return label
        match = re.search(r"round of (\d+)", key)
        if match:
            return f"R{match.group(1)}"
        return stage[:12]

    def _format_league(self, fixture: UpcomingFixture) -> str:
        if fixture.stage:
            return f"{fixture.league} ({self._short_stage(fixture.stage)})"
        return fixture.league

    def _format_odds(self, fixture: UpcomingFixture) -> str:
        odds = fixture.odds_hint or {}
        if not odds:
            return "—"
        try:
            h = float(odds.get("home_win", 0))
            d = float(odds.get("draw", 0))
            a = float(odds.get("away_win", 0))
        except (TypeError, ValueError):
            return "—"
        if h <= 1 or d <= 1 or a <= 1:
            return "—"
        return f"{h:.2f}/{d:.2f}/{a:.2f}"

    def generate(
        self,
        fixtures: list[UpcomingFixture],
        hours_window: int,
        scanned_at: str,
    ) -> str:
        lines: list[str] = []
        lines.append("=" * self.WIDTH)
        lines.append(f"  JOGOS REAIS — PRÓXIMAS {hours_window} HORAS")
        lines.append("=" * self.WIDTH)
        lines.append(f"  Atualizado: {scanned_at}")
        lines.append(f"  Total: {len(fixtures)}")
        lines.append("")

        if not fixtures:
            lines.append("  Nenhum jogo encontrado nesta janela.")
            lines.append("  Tenta --hours 24 ou outro dia de competição.")
            lines.append("=" * self.WIDTH)
            return "\n".join(lines)

        lines.append(
            "  ┌────┬──────────────┬─────────────────────────┬──────────────────────────┬──────────┐"
        )
        lines.append(
            "  │ #  │ Início       │ Jogo                    │ Competição               │ 1X2      │"
        )
        lines.append(
            "  ├────┼──────────────┼─────────────────────────┼──────────────────────────┼──────────┤"
        )

        for i, fx in enumerate(fixtures, start=1):
            kickoff = self._format_kickoff(fx)[:12].ljust(12)
            game = f"{fx.home} vs {fx.away}"[:23].ljust(23)
            league = self._format_league(fx)[:24].ljust(24)
            odds = self._format_odds(fx)[:8].ljust(8)
            lines.append(f"  │{i:2d} │ {kickoff} │ {game} │ {league} │ {odds} │")

        lines.append(
            "  └────┴──────────────┴─────────────────────────┴──────────────────────────┴──────────┘"
        )
        lines.append(
            "  Fontes: ESPN · API-Football · TheSportsDB · Bing (sem análise)"
        )
        lines.append("=" * self.WIDTH)
        return "\n".join(lines)