"""Motivation Gate — comité de auditores que valida «porque» antes do stake."""

from __future__ import annotations

import os

from bankroll.ev_stake import EvStakePlan
from discovery.team_stats_fetcher import FormSnapshot
from prematch.auditors.clubelo_client import fetch_pair
from prematch.auditors.market_side import bet_side_from_market, vote_aligns_with_market
from prematch.auditors.table_stakes import audit_table_stakes
from prematch.auditors.types import AuditorVote, MotivationReport
from prematch.transfermarkt.types import PrematchInsights

_TRAP_EV = 0.12
_ELO_MIN_GAP = 35.0
_FORM_MIN_GAP = 0.35


def _audit_clubelo(home: str, away: str) -> tuple[AuditorVote | None, dict | None]:
    home_elo, away_elo = fetch_pair(home, away)
    if not home_elo or not away_elo:
        return None, None

    diff = home_elo.elo - away_elo.elo
    if diff >= _ELO_MIN_GAP:
        side = "home"
        label = f"Elo casa +{diff:.0f} ({home_elo.elo:.0f} vs {away_elo.elo:.0f})"
    elif diff <= -_ELO_MIN_GAP:
        side = "away"
        label = f"Elo fora +{-diff:.0f} ({away_elo.elo:.0f} vs {home_elo.elo:.0f})"
    else:
        side = "neutral"
        label = f"Elo equilibrado ({home_elo.elo:.0f} vs {away_elo.elo:.0f})"

    vote = AuditorVote(
        auditor_id="strength_clubelo",
        category="strength",
        side=side,
        label=label,
    )
    return vote, {
        "home": home_elo.to_dict(),
        "away": away_elo.to_dict(),
        "diff": round(diff, 1),
    }


def _audit_value_gap(tm: PrematchInsights | None) -> AuditorVote | None:
    vg = tm.value_gap if tm else None
    if not vg:
        return None
    mapping = {
        "home_undervalued": "home",
        "away_undervalued": "away",
        "home_overpriced": "away",
        "away_overpriced": "home",
    }
    side = mapping.get(vg.signal, "neutral")
    if side == "neutral" and vg.signal == "fair":
        return None
    return AuditorVote(
        auditor_id="strength_value",
        category="strength",
        side=side,
        label=vg.label,
    )


def _audit_form(
    home_form: FormSnapshot | None,
    away_form: FormSnapshot | None,
) -> AuditorVote | None:
    if not home_form or not away_form:
        return None
    if home_form.games_played < 3 or away_form.games_played < 3:
        return None

    home_net = home_form.scored_avg - home_form.conceded_avg
    away_net = away_form.scored_avg - away_form.conceded_avg
    diff = home_net - away_net
    if diff >= _FORM_MIN_GAP:
        side = "home"
        label = (
            f"Forma casa superior (+{diff:.2f} golos/jogo líquidos, "
            f"{home_form.source})"
        )
    elif diff <= -_FORM_MIN_GAP:
        side = "away"
        label = (
            f"Forma fora superior (+{-diff:.2f} golos/jogo líquidos, "
            f"{away_form.source})"
        )
    else:
        return None

    return AuditorVote(
        auditor_id="strength_form",
        category="form",
        side=side,
        label=label,
    )


def _audit_availability(
    tm: PrematchInsights | None,
    bet_side: str,
) -> list[AuditorVote]:
    if not tm:
        return []
    votes: list[AuditorVote] = []
    home_imp = tm.home_absences.total_impact if tm.home_absences else 0.0
    away_imp = tm.away_absences.total_impact if tm.away_absences else 0.0

    if home_imp >= 0.20 and away_imp < 0.12:
        votes.append(
            AuditorVote(
                auditor_id="availability_home",
                category="availability",
                side="away",
                label=f"Lesões casa — impacto {home_imp:.0%}",
            )
        )
    elif away_imp >= 0.20 and home_imp < 0.12:
        votes.append(
            AuditorVote(
                auditor_id="availability_away",
                category="availability",
                side="home",
                label=f"Lesões fora — impacto {away_imp:.0%}",
            )
        )

    if bet_side == "home" and home_imp >= 0.25:
        votes.append(
            AuditorVote(
                auditor_id="availability_bet_risk",
                category="availability",
                side="neutral",
                label=f"Risco: aposta casa com plantel esboroado ({home_imp:.0%})",
                supports_market=False,
            )
        )
    elif bet_side == "away" and away_imp >= 0.25:
        votes.append(
            AuditorVote(
                auditor_id="availability_bet_risk",
                category="availability",
                side="neutral",
                label=f"Risco: aposta fora com plantel esboroado ({away_imp:.0%})",
                supports_market=False,
            )
        )
    return votes


def _collect_votes(
    home: str,
    away: str,
    *,
    league: str,
    bet_side: str,
    tm: PrematchInsights | None,
    home_form: FormSnapshot | None,
    away_form: FormSnapshot | None,
    football_data_key: str | None,
) -> tuple[list[AuditorVote], dict | None, dict | None]:
    votes: list[AuditorVote] = []
    clubelo_payload: dict | None = None
    table_payload: dict | None = None

    clubelo_vote, clubelo_payload = _audit_clubelo(home, away)
    if clubelo_vote and clubelo_vote.side != "neutral":
        votes.append(clubelo_vote)

    value_vote = _audit_value_gap(tm)
    if value_vote:
        votes.append(value_vote)

    form_vote = _audit_form(home_form, away_form)
    if form_vote:
        votes.append(form_vote)

    table_vote, table_payload = audit_table_stakes(
        home, away, league, api_key=football_data_key
    )
    if table_vote and table_vote.side != "neutral":
        votes.append(table_vote)

    votes.extend(_audit_availability(tm, bet_side))
    return votes, clubelo_payload, table_payload


def _score_votes(votes: list[AuditorVote], bet_side: str) -> tuple[int, int, list[str]]:
    aligned: list[AuditorVote] = []
    categories: set[str] = set()
    labels: list[str] = []

    for vote in votes:
        if not vote.supports_market:
            labels.append(vote.label)
            continue
        if vote_aligns_with_market(vote.side, bet_side):
            aligned.append(vote)
            categories.add(vote.category)
            labels.append(vote.label)

    return len(aligned), len(categories), labels


def evaluate_motivation(
    home: str,
    away: str,
    *,
    best_market: str,
    best_ev: float,
    league: str = "",
    tm_insights: PrematchInsights | None = None,
    home_form: FormSnapshot | None = None,
    away_form: FormSnapshot | None = None,
    football_data_key: str | None = None,
) -> MotivationReport:
    """
    Avalia se existe motivação independente para a aposta proposta.
    EV alto sem motivação → veto (trap).
    """
    bet_side = bet_side_from_market(best_market)
    fd_key = football_data_key or os.getenv("FOOTBALL_DATA_API_KEY", "")

    votes, clubelo_payload, table_payload = _collect_votes(
        home,
        away,
        league=league,
        bet_side=bet_side,
        tm=tm_insights,
        home_form=home_form,
        away_form=away_form,
        football_data_key=fd_key,
    )

    has_risk = any(not v.supports_market for v in votes)
    score, indep, labels = _score_votes(votes, bet_side)

    veto = best_ev >= _TRAP_EV and score == 0
    if has_risk and bet_side in ("home", "away"):
        veto = True

    if veto:
        stake_multiplier = 0.0
        should_bet = False
        alignment = "veto"
        summary = "EV alto sem motivação independente — não entrar (possível armadilha)."
    elif score >= 2 and indep >= 2:
        stake_multiplier = 1.0
        should_bet = True
        alignment = "strong"
        summary = f"{score} motivações alinhadas — stake integral."
    elif score == 1:
        stake_multiplier = 0.5
        should_bet = True
        alignment = "neutral"
        summary = "Uma motivação — reduzir stake 50%."
    else:
        stake_multiplier = 0.0
        should_bet = False
        alignment = "weak"
        summary = "Sem motivação clara para este mercado — não entrar."

    if has_risk and should_bet:
        stake_multiplier = min(stake_multiplier, 0.5)
        alignment = "weak"
        summary = "Plantel do lado apostado comprometido — stake reduzido."

    return MotivationReport(
        home=home,
        away=away,
        bet_market=best_market,
        bet_side=bet_side,
        bet_ev=best_ev,
        votes=votes,
        motivation_score=score,
        independent_categories=indep,
        labels=labels,
        stake_multiplier=stake_multiplier,
        veto=veto,
        should_bet=should_bet,
        alignment=alignment,
        summary=summary,
        clubelo=clubelo_payload,
        table_stakes=table_payload,
    )


def apply_motivation_stake(
    plan: EvStakePlan | None,
    report: MotivationReport,
) -> EvStakePlan | None:
    """Aplica multiplicador do gate ao plano de stake."""
    if not plan or report.stake_multiplier >= 0.999:
        return plan
    if report.stake_multiplier <= 0:
        return EvStakePlan(
            level=1,
            label="Bloqueado (Motivation Gate)",
            bankroll_pct=0.0,
            suggested_amount=0.0 if plan.suggested_amount is not None else None,
            ev_pct=plan.ev_pct,
        )

    scaled_pct = round(plan.bankroll_pct * report.stake_multiplier, 2)
    amount = None
    if plan.suggested_amount is not None:
        amount = round(plan.suggested_amount * report.stake_multiplier, 2)
    label = f"{plan.label} · Gate {int(report.stake_multiplier * 100)}%"
    return EvStakePlan(
        level=plan.level,
        label=label,
        bankroll_pct=scaled_pct,
        suggested_amount=amount,
        ev_pct=plan.ev_pct,
    )