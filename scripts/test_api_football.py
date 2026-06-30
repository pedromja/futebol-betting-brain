#!/usr/bin/env python3
"""Testa endpoints económicos da API-Football (mínimo de pedidos)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.env import load_dotenv

load_dotenv(ROOT / ".env")

from discovery.api_football_client import ApiFootballClient


def main() -> int:
    client = ApiFootballClient()
    if not client.is_configured:
        print("API_FOOTBALL_KEY não definida.")
        print("Cria .env com: API_FOOTBALL_KEY=a_tua_chave")
        print("Ou: $env:API_FOOTBALL_KEY = '...'")
        return 1

    print("1) /status (1 pedido)")
    if not client.ping():
        print("   FALHA — chave inválida ou quota esgotada")
        return 1
    quota = client.quota_hint()
    if quota:
        print(f"   OK — {quota}")

    print("\n2) /fixtures?date=... (1–2 pedidos, cache 10 min)")
    fixtures = client.scan_fixtures(hours_ahead=48)
    print(f"   {len(fixtures)} jogos nas próximas 48h")
    for fx in fixtures[:5]:
        stage = f" ({fx.stage})" if fx.stage else ""
        print(f"   • {fx.kickoff[:16]} {fx.home} vs {fx.away} — {fx.league}{stage}")

    if fixtures:
        team = fixtures[0].home
        print(f"\n3) /fixtures?team=...&last=5 (1 pedido, stats de {team})")
        scores = client.team_form_scores(team, last_n=5)
        if scores:
            scored, conceded = scores
            n = len(scored)
            print(
                f"   {n} jogos | média {sum(scored)/n:.2f} marcados, "
                f"{sum(conceded)/n:.2f} sofridos"
            )
        else:
            print("   Sem histórico recente")

    print("\n4) /fixtures?live=all (1 pedido, cache 45s)")
    live = client.scan_live()
    print(f"   {len(live)} jogos ao vivo agora")
    for fx in live[:5]:
        print(
            f"   • {fx.minute}' {fx.score_label} {fx.home} vs {fx.away} — {fx.league}"
        )

    if live and live[0].fixture_id:
        fid = int(live[0].fixture_id)
        label = f"{live[0].home} vs {live[0].away}"
        print(f"\n5) /odds/live?fixture={fid} (1 pedido, cache 30s) — {label}")
        live_odds = client.fetch_live_odds(fid)
        if live_odds:
            print(
                f"   1X2: {live_odds.get('home_win')} / "
                f"{live_odds.get('draw')} / {live_odds.get('away_win')}"
            )
            print(f"   O/U 2.5: {live_odds.get('over_25')} / {live_odds.get('under_25')}")
        else:
            print("   Sem odds in-play (tenta ESPN ou pré-jogo no live-scan)")

    if live and live[0].fixture_id:
        fid = int(live[0].fixture_id)
        print(f"\n6) xG coverage — python scripts/check_live_xg_coverage.py --fixture {fid}")
        print("   (Fase 0: API xG vs estimativa interna)")

    print(
        "\nPedidos típicos: live-list=1 | live-scan=1+N "
        "(live odds 30s → ESPN → pré-jogo 1h)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())