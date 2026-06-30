"""Dump IA thinking for a live game — context ESPN + reasoning LLM."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_env = ROOT / ".env"
if _env.exists():
    for _line in _env.read_text(encoding="utf-8").splitlines():
        if "=" in _line and not _line.strip().startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

from discovery.espn_live_scanner import EspnLiveScanner
from ia.autonomous_engine import analyze_game, build_llm_context


def _match_fx(games, needle: str):
    needle = needle.lower()
    for fx in games:
        blob = f"{fx.home} {fx.away}".lower()
        if needle in blob or all(part in blob for part in needle.split()):
            return fx
    return None


def main() -> None:
    needle = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "france sweden"
    scanner = EspnLiveScanner()
    games = scanner.scan()
    fx = _match_fx(games, needle)
    if not fx:
        print(f"Jogo não encontrado in-play para: {needle!r}")
        print("Jogos live ESPN:")
        for g in games:
            print(
                f"  {g.espn_event_id} [{g.espn_league_code}] "
                f"{g.home} vs {g.away} {g.minute}' {g.home_score}-{g.away_score}"
            )
        sys.exit(1)

    print("=" * 72)
    print(f"JOGO: {fx.home} vs {fx.away}")
    print(
        f"ESPN: {fx.espn_event_id} / {fx.espn_league_code} | "
        f"{fx.minute}' | {fx.home_score}-{fx.away_score}"
    )
    print("=" * 72)

    ctx = build_llm_context(fx)
    print("\n## CONTEXTO ENVIADO AO LLM\n")
    print(json.dumps(ctx, ensure_ascii=False, indent=2))

    if not os.getenv("XAI_API_KEY"):
        print("\n## IA LLM: OFFLINE (XAI_API_KEY não configurada)\n")
        sys.exit(0)

    print("\n## PENSAMENTO DA IA (reasoning_pt + quotes ESPN)\n")
    from ia.llm_client import IaLlmClient

    client = IaLlmClient()
    model, reason = client.pick_model(ctx)
    print(f"Modelo escolhido: {model} ({reason})\n")
    out = analyze_game(fx, force=True)
    print(json.dumps(out, ensure_ascii=False, indent=2))

    rejected = out.get("rejected_tips") or []
    if rejected:
        print("\n## DICAS REJEITADAS (gate/cooldown)\n")
        print(json.dumps(rejected, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()