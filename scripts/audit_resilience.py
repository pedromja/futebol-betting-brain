"""Auditoria: PSG vs Nice e outras equipas."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.resilience import dampen_news_impact, get_team_profile
from news.types import NewsCategory

RAW_STAR = 0.48


def main() -> None:
    print("=== AUDITORIA PSG vs Nice — Lesão jogador-estrela ===\n")
    for team in ["Paris Saint-Germain", "Nice", "Benfica", "Estoril"]:
        p = get_team_profile(team)
        r = dampen_news_impact(RAW_STAR, team, NewsCategory.KEY_PLAYER_INJURY)
        pct = r.effective_impact / RAW_STAR * 100
        print(f"{team}:")
        print(f"  Eixos: D={p.squad_depth:.2f} I={p.institutional:.2f} F={p.financial:.2f}")
        print(f"  S_c={r.axis_score:.2f} → R_c={r.resilience:.2f}")
        print(f"  I_bruto={RAW_STAR:.3f} → I_efetivo={r.effective_impact:.3f} ({pct:.0f}% do bruto)\n")

    psg = dampen_news_impact(RAW_STAR, "Paris Saint-Germain", NewsCategory.KEY_PLAYER_INJURY)
    nice = dampen_news_impact(RAW_STAR, "Nice", NewsCategory.KEY_PLAYER_INJURY)
    ratio = nice.effective_impact / psg.effective_impact
    print(f"Nice sofre {ratio:.1f}× mais impacto que PSG na mesma lesão de estrela\n")

    print("=== Crise no balneário (α baixo — equipas grandes também sofrem) ===")
    for team in ["Paris Saint-Germain", "Nice"]:
        r = dampen_news_impact(0.40, team, NewsCategory.DRESSING_ROOM_CRISIS)
        print(f"{team}: I_efetivo={r.effective_impact:.3f} (R_c={r.resilience:.2f}, α={r.damping_alpha})")


if __name__ == "__main__":
    main()