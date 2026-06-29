from decision.engine import Decision
from markets.markets import Market, MarketType



class ProcessTrace:
    WIDTH = 58

    def _line(self, char: str = "─") -> str:
        return "  " + char * (self.WIDTH - 2)

    def _section(self, step: int, title: str) -> list[str]:
        return [
            "",
            self._line("═"),
            f"  PASSO {step}: {title}",
            self._line("═"),
        ]

    def _overround(self, *odds: float) -> tuple[float, list[float]]:
        implied = [1 / o for o in odds if o > 0]
        total = sum(implied)
        fair = [p / total for p in implied] if total > 0 else implied
        margin = (total - 1) * 100 if total > 0 else 0
        return margin, fair

    def _market_matches(self, market: Market, h: int, a: int) -> bool:
        mt = market.market_type
        if mt == MarketType.HOME_WIN:
            return h > a
        if mt == MarketType.DRAW:
            return h == a
        if mt == MarketType.AWAY_WIN:
            return h < a
        if mt == MarketType.OVER_25:
            return h + a > 2
        if mt == MarketType.UNDER_25:
            return h + a <= 2
        if mt == MarketType.BTTS_YES:
            return h > 0 and a > 0
        if mt == MarketType.BTTS_NO:
            return h == 0 or a == 0
        if mt == MarketType.DOUBLE_CHANCE_1X:
            return h >= a
        if mt == MarketType.DOUBLE_CHANCE_X2:
            return h <= a
        if mt == MarketType.DOUBLE_CHANCE_12:
            return h != a
        return False

    def _top_contributing_scorelines(
        self, decision: Decision, market: Market, n: int = 5
    ) -> list[tuple[int, int, float]]:
        matrix = decision.recommendation.matrix
        hits = [
            (h, a, p)
            for (h, a), p in matrix.matrix.items()
            if self._market_matches(market, h, a)
        ]
        hits.sort(key=lambda x: x[2], reverse=True)
        return hits[:n]

    def _news_section(self, decision: Decision) -> list[str]:
        lines: list[str] = []
        report = decision.news_report
        if not report:
            lines += self._section(1, "DEEPSEARCH (X) — NOTÍCIAS")
            lines.append("  Pesquisa de notícias desativada.")
            return lines

        source_label = {
            "x_search": "X Search API (xAI) — tempo real",
            "web_search": "Pesquisa web (Bing) — gratuita",
            "sample_x": "Notícias de exemplo validadas (modo demo)",
            "none": "Sem notícias disponíveis",
        }.get(report.source, report.source)

        lines += self._section(1, "DEEPSEARCH (X) — NOTÍCIAS VALIDADAS")

        if decision.discovered_venue and decision.discovered_venue.discovery_steps:
            lines.append("  Estádio (descoberta automática):")
            for step in decision.discovered_venue.discovery_steps:
                lines.append(f"    • {step}")
            if decision.discovered_venue.stadium:
                lines.append(
                    f"    → {decision.discovered_venue.stadium} "
                    f"({decision.discovered_venue.city}, {decision.discovered_venue.country})"
                )
            lines.append("")

        lines.append(f"  Fonte notícias: {source_label}")
        lines.append("")
        lines.append("  Fórmula de impacto por notícia:")
        lines.append("    I = W_c × S × V × R × P")
        lines.append("    W_c=peso categoria | S=severidade | V=credibilidade X")
        lines.append("    R=e^(-dias/7) | P=importância jogador")
        lines.append("")

        for side, dist, team_report in [
            ("CASA", decision.home_distortion, report.home),
            ("FORA", decision.away_distortion, report.away),
        ]:
            lines.append(f"  [{side}] {team_report.team}")
            if not team_report.items:
                lines.append("    Sem notícias relevantes encontradas.")
                lines.append("")
                continue

            for item in team_report.items:
                val = "✓" if item.validated else "?"
                lines.append(f"    [{val}] {item.headline}")
                lines.append(f"        {item.summary}")
                if item.source_handle:
                    lines.append(f"        Fonte: {item.source_handle}")
                lines.append("")

            if dist and dist.details:
                lines.append(f"    Cálculo de distorção — {dist.team_name}:")
                for detail in dist.details:
                    for step in detail.formula_steps:
                        lines.append(f"      {step}")
                    lines.append("")

                lines.append(
                    f"    Agregação: tanh(ΣΔ×2)/2 → "
                    f"Δataque={dist.attack_delta_total:+.4f}, "
                    f"Δdefesa={dist.defense_delta_total:+.4f}"
                )
                lines.append(
                    f"    M_ataque={dist.attack_multiplier:.3f} | "
                    f"M_defesa={dist.defense_multiplier:.3f} | "
                    f"Distorção total={dist.total_distortion:.3f}"
                )
                lines.append(
                    f"    Ataque: {dist.original_attack:.2f} → {dist.adjusted_attack:.2f} golos/jogo"
                )
                lines.append(
                    f"    Defesa: {dist.original_defense:.2f} → {dist.adjusted_defense:.2f} golos sofridos/jogo"
                )
            lines.append("")

        return lines

    def _environment_section(self, decision: Decision) -> list[str]:
        lines: list[str] = []
        env = decision.environment
        if not env:
            lines += self._section(2, "CONDIÇÕES AMBIENTAIS")
            lines.append("  Análise ambiental desativada.")
            return lines

        w = env.weather
        weather_src = {
            "openweathermap_current": "OpenWeatherMap (tempo atual)",
            "openweathermap_forecast": "OpenWeatherMap (previsão para o jogo)",
            "sample": "Dados de exemplo",
        }.get(env.weather_source, env.weather_source)

        lines += self._section(2, "CONDIÇÕES AMBIENTAIS — METEO, VIAGEM, ALTITUDE")

        venue_label = env.venue_resolved_name or env.venue.stadium or env.venue.city
        resolve_src = {
            "registry": "registo local (venue_coords.json)",
            "geocoded": "geocodificado e adicionado ao registo (OpenWeatherMap)",
            "not_found": "não resolvido",
        }.get(env.venue_resolve_source, env.venue_resolve_source or "—")

        lines.append(f"  Local do jogo: {venue_label}")
        if env.venue.stadium:
            lines.append(f"  Estádio: {env.venue.stadium}")
        lines.append(f"  Cidade: {env.venue.city} | Altitude: {env.venue.altitude_m:.0f}m")
        lines.append(f"  Resolução do local: {resolve_src}")
        lines.append(f"  Fonte meteorologia: {weather_src}")
        if env.weather_fetched_at:
            lines.append(f"  Obtido em: {env.weather_fetched_at}")
        lines.append(
            f"  Meteorologia: {w.temperature_c:.0f}°C, chuva {w.precipitation_mm:.0f}mm, "
            f"vento {w.wind_kmh:.0f}km/h → S_w={w.computed_severity:.3f}"
        )
        lines.append(
            f"  Viagem fora: {env.travel.away_distance_km:.0f}km, "
            f"{env.travel.away_travel_hours:.1f}h, "
            f"fuso ±{env.travel.timezone_diff}"
        )
        lines.append(
            f"  Altitudes natais: casa {env.home_profile.altitude_m:.0f}m | "
            f"fora {env.away_profile.altitude_m:.0f}m"
        )
        lines.append("")
        lines.append("  Fórmulas:")
        lines.append("    Meteo: Δ = -W_m × S_w × A_t × C_t  (A: casa=0.35, fora=1.0)")
        lines.append("    Altitude: I_alt = min(Δh/1000, 1) — penaliza visitante")
        lines.append("    Viagem: I_travel = I_dist + I_time + I_tz — só visitante")
        lines.append("")

        for side, dist in [
            ("CASA", decision.home_env_distortion),
            ("FORA", decision.away_env_distortion),
        ]:
            lines.append(f"  [{side}]")
            if not dist:
                lines.append("    Sem impacto ambiental significativo.")
                lines.append("")
                continue
            for detail in dist.details:
                for step in detail.formula_steps:
                    lines.append(f"    {step}")
                lines.append("")
            lines.append(
                f"    Agregação: tanh(ΣΔ×2)/2 → "
                f"Δataque={dist.attack_delta_total:+.4f}, "
                f"Δdefesa={dist.defense_delta_total:+.4f}"
            )
            lines.append(
                f"    M_ataque={dist.attack_multiplier:.3f} | M_defesa={dist.defense_multiplier:.3f}"
            )
            lines.append(
                f"    Ataque: {dist.original_attack:.2f} → {dist.adjusted_attack:.2f}"
            )
            lines.append(
                f"    Defesa: {dist.original_defense:.2f} → {dist.adjusted_defense:.2f}"
            )
            lines.append("")

        return lines

    def _stakes_section(self, decision: Decision) -> list[str]:
        lines: list[str] = []
        report = decision.stakes_report
        if not report:
            return lines

        lines += self._section(2, "NECESSIDADES DAS EQUIPAS (STAKES)")
        lines.append(
            "  Equipas com objetivos diferentes atacam/defendem com intensidade diferente."
        )
        lines.append("  Já apurada → poupa | Precisa ganhar → arrisca mais | Empate chega → fecha.")
        lines.append("")

        for side, adj in [("CASA", report.home), ("FORA", report.away)]:
            lines.append(f"  [{side}] {adj.team_name}: {adj.label}")
            for step in adj.formula_steps:
                lines.append(f"    {step}")
            lines.append(
                f"    Multiplicadores finais: ataque ×{adj.attack_mult:.2f}, "
                f"defesa ×{adj.defense_mult:.2f}, urgência {adj.urgency:.2f}"
            )
            lines.append("")

        if report.combined_note:
            lines.append(f"  Resumo: {report.combined_note}")
            lines.append("")
        return lines

    def _live_section(self, decision: Decision) -> list[str]:
        lines: list[str] = []
        state = decision.live_state
        meta = decision.live_meta
        if not state:
            return lines

        lines.append("")
        lines.append("  ► ESTADO AO VIVO")
        lines.append(self._line("─"))
        lines.append(
            f"  Resultado: {state.home_score}-{state.away_score} | "
            f"Minuto: {state.minute}'+{state.injury_time} | "
            f"Período: {state.period.value}"
        )
        lines.append(
            f"  Tempo restante ~{state.remaining_minutes:.0f} min "
            f"({state.remaining_fraction * 100:.0f}% do jogo)"
        )
        if meta:
            lines.append(
                f"  λ restante: casa {meta.home_lambda_remaining:.3f} | "
                f"fora {meta.away_lambda_remaining:.3f} "
                f"(jogo completo seria {meta.home_lambda_full:.2f}+{meta.away_lambda_full:.2f})"
            )
        lines.append("")
        lines.append("  Mercados já decididos (excluídos da análise):")
        settled = [
            n for n in (meta.market_notes if meta else [])
            if n.status.value.startswith("settled")
        ]
        if settled:
            for n in settled:
                lines.append(f"    • {n.market_type}: {n.reason}")
        else:
            lines.append("    Nenhum (todos ainda em aberto)")
        lines.append("")
        return lines

    def generate(self, decision: Decision) -> str:
        match = decision.match
        rec = decision.recommendation
        lb = rec.lambda_breakdown
        home = match.home
        away = match.away
        odds = match.odds
        lines: list[str] = []

        lines += self._news_section(decision)
        lines += self._environment_section(decision)
        lines += self._stakes_section(decision)
        lines += self._live_section(decision)

        step_data = 3
        title_data = "DADOS FINAIS (APÓS NOTÍCIAS + AMBIENTE + NECESSIDADES)"
        if decision.live_state:
            title_data += " — AJUSTADO AO VIVO"
        lines += self._section(step_data, title_data)
        if (
            decision.home_distortion
            or decision.away_distortion
            or decision.home_env_distortion
            or decision.away_env_distortion
        ):
            lines.append("  Valores estatísticos após todos os ajustes contextuais:")
            lines.append("")
        lines.append(f"  Casa: {home.name}")
        lines.append(
            f"    Ataque (média golos marcados): {home.goals_scored_avg:.2f}/jogo"
        )
        lines.append(
            f"    Defesa (média golos sofridos):  {home.goals_conceded_avg:.2f}/jogo"
        )
        lines.append(
            f"    Forma: marcou {home.scored_in_last_n}/{home.last_n}, "
            f"sofreu {home.conceded_in_last_n}/{home.last_n}"
        )
        lines.append(f"  Fora: {away.name}")
        lines.append(
            f"    Ataque (média golos marcados): {away.goals_scored_avg:.2f}/jogo"
        )
        lines.append(
            f"    Defesa (média golos sofridos):  {away.goals_conceded_avg:.2f}/jogo"
        )
        lines.append(
            f"    Forma: marcou {away.scored_in_last_n}/{away.last_n}, "
            f"sofreu {away.conceded_in_last_n}/{away.last_n}"
        )
        lines.append(f"  Liga média de golos (referência): {lb.league_avg:.2f}")

        if decision.original_match:
            oh, oa = decision.original_match.home, decision.original_match.away
            lines.append("")
            lines.append("  Valores originais (só estatísticas, sem ajustes):")
            lines.append(
                f"    {oh.name}: ataque {oh.goals_scored_avg:.2f}, defesa {oh.goals_conceded_avg:.2f}"
            )
            lines.append(
                f"    {oa.name}: ataque {oa.goals_scored_avg:.2f}, defesa {oa.goals_conceded_avg:.2f}"
            )

        lam_title = "CÁLCULO DE GOLOS ESPERADOS (λ)"
        if decision.live_state:
            lam_title = "Golos esperados NO TEMPO RESTANTE (λ_restante)"
        lines += self._section(4, lam_title)
        if decision.live_state and decision.live_meta:
            lm = decision.live_meta
            lines.append(
                f"  λ_restante = λ_jogo_completo × fracção_tempo × urgência"
            )
            lines.append(
                f"  Casa: {lm.home_lambda_full:.3f} × {decision.live_state.remaining_fraction:.2f} "
                f"≈ {lm.home_lambda_remaining:.3f}"
            )
            lines.append(
                f"  Fora: {lm.away_lambda_full:.3f} × {decision.live_state.remaining_fraction:.2f} "
                f"≈ {lm.away_lambda_remaining:.3f}"
            )
        else:
            lines.append("  Fórmula casa:")
            lines.append("    λ_casa = ataque_casa × (defesa_fora / média_liga) × vantagem_casa")
            lines.append(f"    {lb.home_formula}")
            lines.append("")
            lines.append("  Fórmula fora:")
            lines.append("    λ_fora = ataque_fora × (defesa_casa / média_liga)")
            lines.append(f"    {lb.away_formula}")
        lines.append("")
        lines.append(
            f"  Total esperado: {rec.home_lambda:.3f} + {rec.away_lambda:.3f} "
            f"= {rec.home_lambda + rec.away_lambda:.3f} golos"
        )

        matrix_title = "MATRIZ POISSON — RESULTADOS MAIS PROVÁVEIS"
        if decision.live_state:
            s = decision.live_state
            matrix_title = (
                f"MATRIZ FINAL (a partir de {s.home_score}-{s.away_score} no min {s.minute}')"
            )
        lines += self._section(5, matrix_title)
        if decision.live_state:
            lines.append(
                "  Probabilidades de resultado ao apito final (90'), "
                "somando golos adicionais possíveis."
            )
        else:
            lines.append("  Cada célula = P(golos_casa) × P(golos_fora) com distribuição Poisson")
        lines.append("")
        for h, a, p in rec.matrix.top_scorelines(8):
            lines.append(f"    {h}-{a}: {p * 100:5.2f}%")
        lines.append("")
        lines.append(
            f"  P(casa vence): {rec.matrix.prob_home_win() * 100:.1f}%  |  "
            f"P(empate): {rec.matrix.prob_draw() * 100:.1f}%  |  "
            f"P(fora vence): {rec.matrix.prob_away_win() * 100:.1f}%"
        )
        lines.append(
            f"  P(over 2.5): {rec.matrix.prob_over(2.5) * 100:.1f}%  |  "
            f"P(BTTS): {rec.matrix.prob_btts_yes() * 100:.1f}%"
        )

        lines += self._section(6, "ANÁLISE DAS ODDS — PROBABILIDADE IMPLÍCITA")
        lines.append("  Fórmula: prob_implícita = 1 / odd")
        lines.append("")

        margin_1x2, fair_1x2 = self._overround(
            odds.home_win, odds.draw, odds.away_win
        )
        labels_1x2 = ["Vitória Casa", "Empate", "Vitória Fora"]
        raw_1x2 = [1 / odds.home_win, 1 / odds.draw, 1 / odds.away_win]
        lines.append("  Mercado 1X2:")
        for label, odd, raw, fair in zip(
            labels_1x2, [odds.home_win, odds.draw, odds.away_win], raw_1x2, fair_1x2
        ):
            lines.append(
                f"    {label}: odd {odd:.2f} → {raw * 100:.1f}% bruta → "
                f"{fair * 100:.1f}% justa (sem margem)"
            )
        lines.append(f"    Margem da casa (overround): {margin_1x2:.1f}%")
        lines.append("")

        margin_ou, fair_ou = self._overround(odds.over_25, odds.under_25)
        lines.append("  Mercado Over/Under 2.5:")
        lines.append(
            f"    Over 2.5: odd {odds.over_25:.2f} → {1/odds.over_25*100:.1f}% bruta → "
            f"{fair_ou[0]*100:.1f}% justa"
        )
        lines.append(
            f"    Under 2.5: odd {odds.under_25:.2f} → {1/odds.under_25*100:.1f}% bruta → "
            f"{fair_ou[1]*100:.1f}% justa"
        )
        lines.append(f"    Margem da casa: {margin_ou:.1f}%")

        lines += self._section(7, "DETEÇÃO DE VALOR — MERCADO A MERCADO")
        lines.append("  Fórmula EV (valor esperado): EV = (prob_modelo × odd) − 1")
        lines.append("  Edge = prob_modelo − prob_implícita")
        lines.append("  EV > 0 → a odd paga mais do que o modelo estima ser justo")
        lines.append("")

        for market in rec.all_markets:
            bd = market.breakdown
            lines.append(f"  ▸ {market.label} @ {market.odd:.2f}")
            lines.append(f"    Origem da prob.: {bd.prob_derivation}")
            lines.append(
                f"    Prob. modelo: {market.model_prob * 100:.2f}%  |  "
                f"Prob. implícita: {market.implied_prob * 100:.2f}%  |  "
                f"Edge: {bd.edge * 100:+.2f}pp"
            )
            lines.append(
                f"    EV = ({market.model_prob:.4f} × {market.odd:.2f}) − 1 "
                f"= {market.expected_value * 100:+.2f}%"
            )
            top_lines = self._top_contributing_scorelines(decision, market, 3)
            if top_lines:
                contrib = ", ".join(
                    f"{h}-{a} ({p*100:.1f}%)" for h, a, p in top_lines
                )
                lines.append(f"    Resultados que mais contribuem: {contrib}")
            lines.append("")

        lines += self._section(8, "PONTUAÇÃO FINAL — COMO O SCORE É CALCULADO")
        lines.append("  Fórmula:")
        lines.append(
            "    score = (EV_norm × 40%) + (confiança × 35%) + (forma × 25%)"
        )
        lines.append("    EV_norm = normalização de EV para escala 0-1")
        lines.append("      EV_norm = clamp((EV + 0.15) / 0.30, 0, 1)")
        lines.append("")
        lines.append("  Confiança do modelo baseada em:")
        lines.append("    • Certeza da probabilidade (quanto mais longe de 50%, melhor)")
        lines.append("    • Tamanho da amostra (jogos analisados)")
        lines.append("")
        lines.append("  Score de forma baseado em:")
        lines.append("    • Consistência ofensiva (marcar em X dos últimos N jogos)")
        lines.append("    • Consistência defensiva (sofrer em X dos últimos N jogos)")
        lines.append("")

        for i, market in enumerate(rec.all_markets[:6]):
            bd = market.breakdown
            lines.append(f"  {i+1}. {market.label}")
            lines.append(
                f"     EV_norm {bd.normalized_ev:.3f} × 0.40 = {bd.ev_contribution:.3f}"
            )
            lines.append(
                f"   + Conf.  {market.confidence:.3f} × 0.35 = {bd.conf_contribution:.3f}"
            )
            lines.append(
                f"   + Forma  {market.form_score:.3f} × 0.25 = {bd.form_contribution:.3f}"
            )
            lines.append(f"   = SCORE {market.total_score:.3f}")
            lines.append("")

        lines += self._section(9, "DECISÃO AUTOMÁTICA")
        lines.append(f"  Limiar mínimo para apostar: {rec.min_score:.2f}")
        if rec.should_bet and rec.best:
            lines.append(
                f"  Mercado vencedor: {rec.best.label} (score {rec.best.total_score:.3f})"
            )
            lines.append(
                f"  Motivo: maior score acima do limiar, com EV {rec.best.ev_percent:+.1f}%"
            )
            lines.append(
                f"  O programa escolheu este mercado porque combina valor estatístico,"
            )
            lines.append(
                f"  confiança do modelo ({rec.best.confidence*100:.0f}%) e forma recente."
            )
        else:
            lines.append("  Resultado: NÃO APOSTAR")
            if rec.all_markets:
                top = rec.all_markets[0]
                lines.append(
                    f"  Melhor mercado ({top.label}) tem score {top.total_score:.3f}, "
                    f"abaixo do limiar {rec.min_score:.2f}"
                )
            lines.append(
                "  O programa rejeitou todos os mercados por falta de valor/confiança suficiente."
            )

        return "\n".join(lines)