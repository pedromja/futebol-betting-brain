from scanner.ranker import ScanResult


class ScanReport:
    WIDTH = 62

    def generate(self, result: ScanResult) -> str:
        lines: list[str] = []
        lines.append("=" * self.WIDTH)
        lines.append(f"  SCANNER AUTOMÁTICO — PRÓXIMAS {result.hours_window} HORAS")
        lines.append("=" * self.WIDTH)
        lines.append(f"  Analisado em: {result.scanned_at}")
        lines.append(
            f"  Jogos encontrados: {result.total_found} | "
            f"Analisados com odds: {result.total_analyzed}"
        )
        lines.append("")

        if not result.ranked:
            lines.append("  Nenhum jogo analisável nas próximas 12 horas.")
            lines.append("  (Sem jogos na janela — web/ESPN ou samples em dias vazios)")
            lines.append("=" * self.WIDTH)
            return "\n".join(lines)

        if result.best and result.best.should_bet:
            b = result.best
            lines.append("  ★ MELHOR APOSTA (maior EV)")
            lines.append(f"    {b.fixture.home} vs {b.fixture.away}")
            stage = f" | Fase: {b.fixture.stage}" if b.fixture.stage else ""
            lines.append(
                f"    Liga: {b.fixture.league}{stage} | Início: {b.fixture.kickoff}"
            )
            lines.append(
                f"    Mercado: {b.best_market} | EV: {b.best_ev*100:+.1f}% | "
                f"Score: {b.best_score:.2f} (limiar {b.effective_min_score:.2f})"
            )
            if b.top_markets and len(b.top_markets) > 1:
                lines.append(f"    Top mercados: {' · '.join(b.top_markets)}")
            if b.kelly_stake is not None:
                lines.append(
                    f"    Stake Kelly: {b.kelly_stake:.2f} ({b.kelly_pct:.1f}% banca)"
                )
            stakes = b.decision.stakes_report
            if stakes and stakes.combined_note != "Sem ajuste de necessidade":
                lines.append(f"    Necessidades: {stakes.combined_note}")
            lines.append("")

        lines.append("  RANKING COMPLETO:")
        lines.append("  ┌────┬─────────────────────────┬──────────────────┬──────┬──────┐")
        lines.append("  │ #  │ Jogo                    │ Mercado          │ EV   │Score │")
        lines.append("  ├────┼─────────────────────────┼──────────────────┼──────┼──────┤")

        for r in result.ranked[:15]:
            star = "★" if r.rank == 1 and r.should_bet else " "
            game = f"{r.fixture.home} vs {r.fixture.away}"[:23].ljust(23)
            market = r.best_market[:16].ljust(16)
            ev = f"{r.best_ev*100:+4.0f}%"
            score = f"{r.best_score:.2f}"
            bet = "✓" if r.should_bet else "—"
            lines.append(
                f"  │{r.rank:2d}{star}│ {game} │ {market} │ {ev} │{score}│{bet}"
            )

        lines.append("  └────┴─────────────────────────┴──────────────────┴──────┴──────┘")
        lines.append("  ✓ = recomenda aposta | — = abaixo do limiar")
        lines.append("=" * self.WIDTH)
        return "\n".join(lines)