"""Relatório de jogos ao vivo."""

from discovery.live_fixture_types import LiveFixture
from scanner.live_ranker import LiveScanResult


class LiveListReport:
    WIDTH = 78

    def generate(self, fixtures: list[LiveFixture], scanned_at: str) -> str:
        lines: list[str] = []
        lines.append("=" * self.WIDTH)
        lines.append("  JOGOS AO VIVO AGORA")
        lines.append("=" * self.WIDTH)
        lines.append(f"  Atualizado: {scanned_at}")
        lines.append(f"  Total: {len(fixtures)}")
        lines.append("")

        if not fixtures:
            lines.append("  Nenhum jogo ao vivo neste momento.")
            lines.append("=" * self.WIDTH)
            return "\n".join(lines)

        lines.append(
            "  ┌────┬──────┬─────────────────────────┬──────────────────────────┐"
        )
        lines.append(
            "  │ #  │ Min  │ Jogo                    │ Competição               │"
        )
        lines.append(
            "  ├────┼──────┼─────────────────────────┼──────────────────────────┤"
        )
        for i, fx in enumerate(fixtures, start=1):
            minute = f"{fx.minute}'".ljust(4)
            if fx.injury_time:
                minute = f"{fx.minute}+{fx.injury_time}"[:4].ljust(4)
            game = f"{fx.score_label} {fx.home} vs {fx.away}"[:23].ljust(23)
            league = fx.league[:24].ljust(24)
            lines.append(f"  │{i:2d} │ {minute} │ {game} │ {league} │")
        lines.append(
            "  └────┴──────┴─────────────────────────┴──────────────────────────┘"
        )
        lines.append("=" * self.WIDTH)
        return "\n".join(lines)


class LiveScanReport:
    WIDTH = 78

    def generate(self, result: LiveScanResult) -> str:
        lines: list[str] = []
        lines.append("=" * self.WIDTH)
        lines.append("  LIVE SCAN — ANÁLISE IN-PLAY")
        lines.append("=" * self.WIDTH)
        lines.append(f"  Analisado em: {result.scanned_at}")
        lines.append(
            f"  Ao vivo: {result.total_live} | "
            f"Analisados: {result.total_analyzed} | "
            f"Ignorados: {len(result.skipped)}"
        )
        lines.append("")

        if result.best and result.best.should_bet:
            b = result.best
            fx = b.fixture
            lines.append("  ★ MELHOR LIVE")
            lines.append(
                f"    {fx.score_label} {fx.home} vs {fx.away} "
                f"({fx.minute}' {fx.status_short})"
            )
            lines.append(f"    {fx.league}")
            lines.append(
                f"    {b.best_market} | EV {b.best_ev*100:+.1f}% | "
                f"Score {b.best_score:.2f} (limiar {b.effective_min_score:.2f})"
            )
            if b.top_markets:
                lines.append(f"    Top: {' · '.join(b.top_markets)}")
            if b.stake_plan:
                lines.append(f"    {b.stake_plan.display}")
            elif b.kelly_stake is not None:
                lines.append(f"    Kelly: {b.kelly_stake:.2f}")
            lines.append("")

        if result.ranked:
            lines.append("  RANKING LIVE:")
            lines.append(
                "  ┌────┬──────────┬────────────────────┬──────────────┬──────┬───────┐"
            )
            lines.append(
                "  │ #  │ Resultado│ Mercado            │ EV           │Score │ Stake │"
            )
            lines.append(
                "  ├────┼──────────┼────────────────────┼──────────────┼──────┼───────┤"
            )
            for r in result.ranked[:12]:
                fx = r.fixture
                res = f"{fx.minute}' {fx.score_label}"[:8].ljust(8)
                market = r.best_market[:18].ljust(18)
                ev = f"{r.best_ev*100:+5.0f}%"
                score = f"{r.best_score:.2f}"
                star = "★" if r.should_bet else " "
                stk = (
                    f"{r.stake_plan.level}/10" if r.stake_plan else "—"
                )[:5].ljust(5)
                lines.append(
                    f"  │{r.rank:2d}{star}│ {res} │ {market} │ {ev} │{score}│ {stk} │"
                )
            lines.append(
                "  └────┴──────────┴────────────────────┴──────────────┴──────┴───────┘"
            )

        if result.skipped:
            lines.append("")
            lines.append(f"  Ignorados ({len(result.skipped)}):")
            for label, reason in result.skipped[:8]:
                lines.append(f"    • {label}: {reason}")
            if len(result.skipped) > 8:
                lines.append(f"    … +{len(result.skipped) - 8}")

        lines.append("")
        lines.append("  Dicas recomendadas guardadas em data/predictions.jsonl")
        lines.append("=" * self.WIDTH)
        return "\n".join(lines)