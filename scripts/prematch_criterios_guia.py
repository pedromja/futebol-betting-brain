#!/usr/bin/env python3
"""
Guia dos critérios pré-jogo — explicação simples, ecrã a ecrã.
Carrega numa tecla para avançar entre cada ecrã.

  python scripts/prematch_criterios_guia.py
  python scripts/prematch_criterios_guia.py --auto   # sem pausas (teste)
"""

from __future__ import annotations

import argparse
import sys

if sys.platform == "win32":
    import msvcrt
else:
    msvcrt = None  # type: ignore[assignment]

_WIDTH = 58

SCREENS: list[tuple[str, list[str]]] = [
    (
        "O que é o PRÉ-JOGO?",
        [
            "Imagina que vais ver um jogo de futebol AMANHÃ.",
            "O robot olha para esses jogos ANTES de começarem.",
            "Ainda não há golos — só há equipas, hora e preços (odds).",
            "",
            "O trabalho dele: escolher UM tipo de aposta por jogo,",
            "só quando está bastante confiante.",
        ],
    ),
    (
        "Passo 1 — Que jogos olhamos?",
        [
            "Primeiro procuramos jogos nas próximas 12 horas.",
            "",
            "Se não aparecer nenhum jogo a sério nessa janela,",
            "alargamos para 24 horas (para não ficar vazio).",
            "",
            "Jogos de mentira (demo) NÃO entram na PWA.",
            "Só jogos reais da internet (ESPN, etc.).",
        ],
    ),
    (
        "Passo 2 — Sem odds, sem análise",
        [
            "Odds = quanto a casa de apostas paga se acertares.",
            "",
            "Se o jogo não tiver preços disponíveis,",
            "o robot diz: «não dá para analisar» e salta o jogo.",
            "",
            "É como tentar comprar gelado numa loja fechada.",
        ],
    ),
    (
        "Passo 3 — Como são as equipas?",
        [
            "O robot vê estatísticas de cada equipa:",
            "  • golos que costumam MARCAR",
            "  • golos que costumam SOFRER",
            "  • jogos recentes que jogaram",
            "",
            "Poucos jogos recentes? Ficamos mais cautelosos.",
            "(No Mundial muitas equipas têm pouca história.)",
        ],
    ),
    (
        "Passo 4 — O «adivinhador» de golos (Poisson)",
        [
            "Com as stats, o robot calcula:",
            "  «Quantos golos espero da equipa da casa?»",
            "  «Quantos golos espero da equipa de fora?»",
            "",
            "Depois imagina TODOS os resultados possíveis",
            "(0-0, 1-0, 2-1, 3-2, …) e vê qual é mais provável.",
            "",
            "A equipa da casa tem pequena vantagem no modelo.",
        ],
    ),
    (
        "Passo 5 — Os mercados (tipos de aposta)",
        [
            "Para cada jogo testamos vários «mercados»:",
            "",
            "  Vitória Casa / Empate / Vitória Fora",
            "  Over 2.5 (3+ golos no total)",
            "  Under 2.5 (0, 1 ou 2 golos)",
            "  BTTS Sim (as duas marcam)",
            "  BTTS Não (pelo menos uma não marca)",
            "  Dupla hipótese (1X, X2, 12)",
            "",
            "Cada um recebe uma nota. Ficamos com o melhor.",
        ],
    ),
    (
        "Passo 6 — EV (valor esperado)",
        [
            "EV responde: «Se apostasse muitas vezes,",
            "ganhava dinheiro a longo prazo?»",
            "",
            "Compara:",
            "  • o que o NOSSO modelo acha provável",
            "  • o que a ODD da casa «acha»",
            "",
            "EV positivo = a odd parece generosa.",
            "EV negativo = a casa não paga o suficiente.",
            "",
            "POUCOS jogos recentes? O robot mistura o modelo",
            "com a odd — evita EV loucos tipo 94% com 3 jogos.",
            "",
            "A nota final usa 40% deste ingrediente.",
        ],
    ),
    (
        "Passo 7 — Confiança",
        [
            "Mesmo com boa odd, precisamos de confiar nos números.",
            "",
            "A confiança sobe quando:",
            "  • temos muitos jogos recentes das equipas",
            "  • a probabilidade não está «no meio» (50-50)",
            "",
            "A nota final usa 35% deste ingrediente.",
        ],
    ),
    (
        "Passo 8 — Forma recente",
        [
            "Olhamos se a equipa está «quente» ou «fria»:",
            "  • marca muito ultimamente?",
            "  • sofre muitos golos?",
            "",
            "Para Over/BTTS Sim → gostamos de ataque forte.",
            "Para Under/BTTS Não → gostamos de defesas sólidas.",
            "",
            "A nota final usa 25% deste ingrediente.",
        ],
    ),
    (
        "Passo 9 — A nota final (score)",
        [
            "Cada mercado ganha uma nota de 0 a 1:",
            "",
            "  40%  EV (valor da odd)",
            "  35%  Confiança nos dados",
            "  25%  Forma das equipas",
            "",
            "Exemplo: nota 0.72 = bastante boa.",
            "         nota 0.45 = fraca — não recomendamos.",
        ],
    ),
    (
        "Passo 10 — A nota mínima para dar dica",
        [
            "Por defeito precisamos de nota ≥ 0.55 (55%).",
            "",
            "Mas se as equipas têm POUCOS jogos recentes,",
            "subimos o exigência:",
            "",
            "  menos de 3 jogos  → +0.08  (precisa ~0.63)",
            "  menos de 5 jogos  → +0.04",
            "  menos de 8 jogos  → +0.02",
            "",
            "É como pedir nota mais alta quando não estudaste muito.",
        ],
    ),
    (
        "Passo 11 — Não repetir a mesma aposta",
        [
            "Se já lançámos «BTTS Não» no México vs Equador,",
            "NUNCA mais lançamos «BTTS Não» nesse jogo.",
            "",
            "Mesmo que a nota mude um bocadinho (0.71 → 0.79).",
            "",
            "Podemos sugerir OUTRO mercado no mesmo jogo",
            "se também for bom e ainda não tiver sido usado.",
        ],
    ),
    (
        "Passo 12 — Stake (quanto apostar)",
        [
            "Se a dica passar todos os testes, calculamos stake 1–10:",
            "",
            "  EV baixo   → stake 1–3  (aposta pequena)",
            "  EV médio   → stake 4–6",
            "  EV alto    → stake 7–10 (máxima confiança no valor)",
            "",
            "Se definires banca na PWA, mostra também € sugeridos.",
        ],
    ),
    (
        "Passo 13 — O que vês na PWA",
        [
            "Na tab Pré-jogo:",
            "",
            "  ◷ Lista de jogos nas próximas horas",
            "  ★ Melhor dica (se houver)",
            "  Tabela com ranking por EV",
            "",
            "Só aparece ★ quando:",
            "  ✓ nota ≥ mínimo",
            "  ✓ mercado ainda não foi usado nesse jogo",
            "  ✓ odd válida",
            "",
            "Pronto! Agora já sabes como o robot pensa.",
        ],
    ),
]


def _clear() -> None:
    if sys.platform == "win32":
        import os

        os.system("cls")
    else:
        print("\033[2J\033[H", end="")


def _box(title: str, lines: list[str]) -> str:
    top = "═" * _WIDTH
    out = [top, f"  {title}", top, ""]
    for line in lines:
        out.append(f"  {line}" if line else "")
    out.extend(["", top])
    return "\n".join(out)


def _wait_key(auto: bool) -> None:
    if auto:
        return
    print()
    print("  ── Carrega numa tecla para continuar ──")
    if msvcrt is not None:
        msvcrt.getch()
    else:
        input()


def run(*, auto: bool = False) -> None:
    total = len(SCREENS)
    for i, (title, lines) in enumerate(SCREENS, start=1):
        _clear()
        print()
        print(_box(f"[{i}/{total}] {title}", lines))
        if i < total:
            _wait_key(auto)
    _clear()
    print()
    print("  Fim do guia. Bom jogo e aposta com responsabilidade.")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Guia pré-jogo — linguagem simples")
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Avança sem pausas (útil para testes)",
    )
    args = parser.parse_args()
    try:
        run(auto=args.auto)
    except KeyboardInterrupt:
        print("\n  (interrompido)")


if __name__ == "__main__":
    main()