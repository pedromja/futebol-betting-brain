#!/usr/bin/env python3
"""
Fase 0 — cobertura de xG ao vivo (API-Football).

Percorre jogos live, pede /fixtures/statistics e regista:
  - se a API devolve expected goals
  - xG estimado interno (fallback sem API de xG)
  - ligas com / sem cobertura

Uso:
  python scripts/check_live_xg_coverage.py
  python scripts/check_live_xg_coverage.py --max 8 --save
  python scripts/check_live_xg_coverage.py --fixture 1234567

Custo API: 1 pedido (live=all, cache 45s) + 1 pedido por jogo analisado.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.env import load_dotenv

load_dotenv(ROOT / ".env")

from discovery.api_football_client import ApiFootballClient
from discovery.match_stats import inspect_fixture_xg_coverage

REPORT_PATH = ROOT / "data" / "xg_coverage_report.json"


def _pct(num: int, den: int) -> str:
    if den == 0:
        return "—"
    return f"{100 * num / den:.0f}%"


def main() -> int:
    parser = argparse.ArgumentParser(description="Auditoria xG ao vivo — Fase 0")
    parser.add_argument(
        "--max",
        type=int,
        default=0,
        help="Máximo de jogos live a analisar (default 0 — usa --fixture ou --max N)",
    )
    parser.add_argument(
        "--fixture",
        type=int,
        default=0,
        help="Analisar um fixture_id específico em vez de scan live",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help=f"Guardar relatório JSON em {REPORT_PATH.relative_to(ROOT)}",
    )
    parser.add_argument(
        "--league",
        type=str,
        default="",
        help="Filtrar jogos live por texto na liga (ex: World, Primeira)",
    )
    args = parser.parse_args()

    client = ApiFootballClient()
    if not client.is_configured:
        print("API_FOOTBALL_KEY não definida — ver .env.example")
        return 1

    print("=== Fase 0: cobertura xG ao vivo ===\n")
    quota = client.quota_hint()
    if quota:
        print(f"Quota: {quota}\n")

    fixtures_info: list[dict] = []
    api_requests = 0

    if args.fixture > 0:
        fixtures_to_check = [
            {
                "fixture_id": args.fixture,
                "home": "?",
                "away": "?",
                "league": "manual",
                "minute": 0,
                "score": "—",
            }
        ]
    else:
        live = client.scan_live()
        api_requests += 1
        league_key = args.league.strip().lower()
        if league_key:
            live = [f for f in live if league_key in f"{f.league} {f.stage}".lower()]

        with_id = [f for f in live if f.fixture_id and f.source == "api-football"]
        print(f"Jogos ao vivo: {len(live)} ({len(with_id)} com fixture_id API-Football)")
        if args.max <= 0:
            print(
                "\nNenhum jogo analisado (default --max 0 para poupar quota)."
            )
            print("  python scripts/check_live_xg_coverage.py --fixture ID")
            print("  python scripts/check_live_xg_coverage.py --max 3")
            if with_id:
                sample = with_id[0]
                print(
                    f"\nExemplo: --fixture {sample.fixture_id}  "
                    f"({sample.home} vs {sample.away})"
                )
            return 0
        if not with_id:
            print("\nNenhum jogo com fixture_id — fonte ESPN não suporta estatísticas.")
            print("Tenta durante jogos cobertos pela API-Football (Mundial, ligas europeias).")
            return 0

        fixtures_to_check = []
        for fx in with_id[: max(1, args.max)]:
            fixtures_to_check.append(
                {
                    "fixture_id": int(fx.fixture_id),
                    "home": fx.home,
                    "away": fx.away,
                    "league": fx.league,
                    "minute": fx.minute,
                    "score": fx.score_label,
                }
            )

    rows: list[dict] = []
    for info in fixtures_to_check:
        fid = info["fixture_id"]
        coverage = inspect_fixture_xg_coverage(client, fid)
        api_requests += 1
        if not coverage:
            rows.append({**info, "error": "sem estatísticas"})
            continue
        rows.append({**info, **coverage})

    # Tabela
    print(f"\n{'Liga':<28} {'Jogo':<32} {'API xG':<8} {'Fonte':<12} {'xG H-A':<12} {'SOT':<8}")
    print("-" * 96)
    for r in rows:
        if r.get("error"):
            label = f"{r.get('home', '?')} vs {r.get('away', '?')}"
            print(f"{r.get('league', '—'):<28} {label:<32} {'—':<8} {'—':<12} {'—':<12} {r['error']}")
            continue
        api_xg = "sim" if r["home_api_xg"] or r["away_api_xg"] else "não"
        src = r.get("bundle_xg_source", "none")
        xg_pair = f"{r.get('home_xg_final', '—')}-{r.get('away_xg_final', '—')}"
        sot = f"{r.get('home_shots_on', '—')}-{r.get('away_shots_on', '—')}"
        label = f"{r['home_team']} vs {r['away_team']}"
        league = (r.get("league") or "—")[:28]
        print(f"{league:<28} {label:<32} {api_xg:<8} {src:<12} {xg_pair:<12} {sot:<8}")

    # Resumo
    valid = [r for r in rows if not r.get("error")]
    n = len(valid)
    api_count = sum(1 for r in valid if r.get("home_api_xg") or r.get("away_api_xg"))
    est_count = sum(1 for r in valid if r.get("bundle_xg_source") == "estimated")
    mixed = sum(1 for r in valid if r.get("bundle_xg_source") == "mixed")
    none_count = sum(1 for r in valid if r.get("bundle_xg_source") == "none")

    print("\n--- Resumo ---")
    print(f"Jogos analisados:     {n}")
    print(f"xG da API:            {api_count} ({_pct(api_count, n)})")
    print(f"Só estimativa interna:{est_count} ({_pct(est_count, n)})")
    print(f"Misto (API+est.):     {mixed}")
    print(f"Sem xG:               {none_count}")
    print(f"Pedidos API (aprox.): {api_requests}")

    by_league: dict[str, dict] = {}
    for r in valid:
        lg = r.get("league") or "unknown"
        bucket = by_league.setdefault(lg, {"total": 0, "api_xg": 0, "estimated": 0})
        bucket["total"] += 1
        if r.get("home_api_xg") or r.get("away_api_xg"):
            bucket["api_xg"] += 1
        if r.get("bundle_xg_source") == "estimated":
            bucket["estimated"] += 1

    if by_league:
        print("\nPor liga:")
        for lg, b in sorted(by_league.items(), key=lambda x: -x[1]["total"]):
            print(
                f"  • {lg}: {b['total']} jogos | "
                f"API xG {b['api_xg']}/{b['total']} | "
                f"estimado {b['estimated']}/{b['total']}"
            )

    print("\nFallback interno (quando API não envia xG):")
    print("  xG ≈ 0.10×à_baliza + 0.05×fora + 0.03×bloqueados + 0.02×cantos")
    print("  → ver discovery/xg_estimate.py")

    if args.save:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        report = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "api_requests_approx": api_requests,
            "summary": {
                "total": n,
                "api_xg": api_count,
                "estimated_only": est_count,
                "mixed": mixed,
                "none": none_count,
            },
            "by_league": by_league,
            "matches": rows,
        }
        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\nRelatório guardado: {REPORT_PATH}")

    if n and api_count == 0 and est_count > 0:
        print(
            "\nNota: API não devolveu xG nestes jogos — a PWA usa estimativa interna."
        )
    elif n and api_count == 0 and none_count == n:
        print(
            "\nNota: sem remates nem xG — liga pode não ter statistics ao vivo."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())