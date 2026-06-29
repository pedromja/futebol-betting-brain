from decision.engine import Decision
from output.process_trace import ProcessTrace


class ReportGenerator:
    WIDTH = 58

    def _line(self, char: str = "═") -> str:
        return char * self.WIDTH

    def _confidence_label(self, value: float) -> str:
        if value >= 0.75:
            return "Alta"
        if value >= 0.60:
            return "Média-Alta"
        if value >= 0.45:
            return "Média"
        return "Baixa"

    def _summary_block(self, decision: Decision) -> str:
        match = decision.match
        rec = decision.recommendation
        lines: list[str] = []

        lines.append(self._line())
        mode = "AO VIVO" if decision.mode == "live" else "PRÉ-JOGO"
        lines.append(f"  JOGO: {match.home.name} vs {match.away.name}  [{mode}]")
        if decision.live_state:
            s = decision.live_state
            lines.append(
                f"  RESULTADO: {s.home_score}-{s.away_score} | {s.minute}'+{s.injury_time}"
            )
        if match.league:
            date_part = f" | Data: {match.date}" if match.date else ""
            lines.append(f"  LIGA: {match.league}{date_part}")
        if decision.stakes_report and decision.stakes_report.combined_note != "Sem ajuste de necessidade":
            lines.append(f"  NECESSIDADES: {decision.stakes_report.combined_note}")
        if decision.odds_fetch:
            of = decision.odds_fetch
            lines.append(
                f"  ODDS: {of.bookmaker_title or of.bookmaker} "
                f"({of.source}, região {of.region}, decimal)"
            )
            if of.credits_remaining is not None:
                lines.append(f"  API credits restantes: {of.credits_remaining}")
        lines.append(self._line())
        lines.append("")

        if decision.discovered_venue and decision.discovered_venue.stadium:
            dv = decision.discovered_venue
            src = {
                "x_search": "validado no X",
                "web_search": "pesquisa web",
                "registry_team": "registo local",
                "geocoded": "geocodificado",
            }.get(dv.source, dv.source)
            lines.append(f"  Estádio ({src}): {dv.stadium}, {dv.city}")
            lines.append("")

        if decision.news_report and decision.news_report.source != "none":
            src = "X (tempo real)" if decision.news_report.source == "x_search" else "X (demo)"
            lines.append(f"  DeepSearch: {src}")
            if decision.home_distortion and decision.home_distortion.total_distortion > 0.001:
                hd = decision.home_distortion
                lines.append(
                    f"    {hd.team_name}: ataque {hd.original_attack:.2f}→{hd.adjusted_attack:.2f}, "
                    f"defesa {hd.original_defense:.2f}→{hd.adjusted_defense:.2f}"
                )
            if decision.away_distortion and decision.away_distortion.total_distortion > 0.001:
                ad = decision.away_distortion
                lines.append(
                    f"    {ad.team_name}: ataque {ad.original_attack:.2f}→{ad.adjusted_attack:.2f}, "
                    f"defesa {ad.original_defense:.2f}→{ad.adjusted_defense:.2f}"
                )
            lines.append("")

        if decision.environment:
            w = decision.environment.weather
            env = decision.environment
            wlabel = {
                "openweathermap_current": "OWM atual",
                "openweathermap_forecast": "OWM previsão",
                "sample": "demo",
            }.get(env.weather_source, env.weather_source)
            venue = env.venue_resolved_name or env.venue.stadium or env.venue.city
            lines.append(f"  Local: {venue}")
            lines.append(
                f"  Ambiente ({wlabel}): {w.temperature_c:.0f}°C, chuva {w.precipitation_mm:.0f}mm, "
                f"vento {w.wind_kmh:.0f}km/h"
            )
            lines.append(
                f"    Viagem fora: {decision.environment.travel.away_distance_km:.0f}km | "
                f"Altitudes: {decision.environment.home_profile.altitude_m:.0f}m / "
                f"{decision.environment.away_profile.altitude_m:.0f}m"
            )
            if decision.home_env_distortion and decision.home_env_distortion.total_distortion > 0.001:
                ed = decision.home_env_distortion
                lines.append(
                    f"    {ed.team_name} (meteo/alt): ataque {ed.original_attack:.2f}→{ed.adjusted_attack:.2f}"
                )
            if decision.away_env_distortion and decision.away_env_distortion.total_distortion > 0.001:
                ed = decision.away_env_distortion
                lines.append(
                    f"    {ed.team_name} (meteo/viagem/alt): ataque {ed.original_attack:.2f}→{ed.adjusted_attack:.2f}"
                )
            lines.append("")

        if rec.should_bet and rec.best:
            lines.append(f"  ★ DECISÃO: {rec.best.label} @ {rec.best.odd:.2f}")
            lines.append(
                f"    Score {rec.best.total_score:.2f} | EV {rec.best.ev_percent:+.1f}% | "
                f"Confiança {self._confidence_label(rec.best.confidence)}"
            )
            if decision.alternative:
                alt = decision.alternative
                lines.append(
                    f"    Alternativa: {alt.label} @ {alt.odd:.2f} (score {alt.total_score:.2f})"
                )
        else:
            lines.append("  ⚠ DECISÃO: NÃO APOSTAR NESTE JOGO")
            if rec.all_markets:
                top = rec.all_markets[0]
                lines.append(
                    f"    Melhor opção ({top.label}) ficou abaixo do limiar "
                    f"({top.total_score:.2f} < {rec.min_score:.2f})"
                )

        lines.append("")
        lines.append("  RANKING DE MERCADOS:")
        lines.append("  ┌─────────────────────┬──────┬──────┬───────┬────────┐")
        lines.append("  │ Mercado             │ Odd  │ EV   │ Conf. │ Score  │")
        lines.append("  ├─────────────────────┼──────┼──────┼───────┼────────┤")

        for i, market in enumerate(rec.all_markets[:8]):
            star = " ★" if i == 0 and rec.should_bet else "  "
            label = market.label[:19].ljust(19)
            lines.append(
                f"  │ {label} │ {market.odd:4.2f} │ {market.ev_percent:+4.0f}% │ "
                f"{market.confidence * 100:4.0f}% │ {market.total_score:.2f}{star} │"
            )

        lines.append("  └─────────────────────┴──────┴──────┴───────┴────────┘")
        lines.append(self._line())

        return "\n".join(lines)

    def generate(self, decision: Decision, verbose: bool = True) -> str:
        parts = [self._summary_block(decision)]

        if verbose:
            parts.append("")
            parts.append("  PROCESSO COMPLETO DE ANÁLISE DE VALOR")
            parts.append(ProcessTrace().generate(decision))

        return "\n".join(parts)