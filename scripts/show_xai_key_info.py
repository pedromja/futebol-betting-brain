"""Mostra origem da XAI_API_KEY (mascarada)."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def mask(key: str) -> str:
    if not key:
        return "(vazia)"
    if len(key) <= 12:
        return f"{key[:4]}...{key[-2:]}"
    return f"{key[:8]}...{key[-6:]}"


def main() -> None:
    env_path = ROOT / ".env"
    env_key = ""
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("XAI_API_KEY="):
                env_key = line.split("=", 1)[1].strip().strip('"').strip("'")

    shell_key = os.getenv("XAI_API_KEY", "")

    hist_key = ""
    hist = Path(r"C:\Users\pedro\.grok\sessions\C%3A%5C\prompt_history.jsonl")
    if hist.exists():
        for line in hist.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            m = re.search(r"xai-[A-Za-z0-9]+", row.get("prompt", ""))
            if m:
                hist_key = m.group(0)

    print("Chave activa no motor IA (local):")
    active = env_key or shell_key
    if env_key:
        print(f"  fonte: .env")
        print(f"  mascarada: {mask(env_key)}")
        print(f"  comprimento: {len(env_key)}")
    elif shell_key:
        print(f"  fonte: variavel de ambiente do processo")
        print(f"  mascarada: {mask(shell_key)}")
    else:
        print("  (nenhuma — llm_status=offline)")

    if hist_key:
        print(f"\nChave colada numa sessao Grok antiga:")
        print(f"  mascarada: {mask(hist_key)}")
        if active:
            print(f"  igual a .env: {'sim' if active == hist_key else 'nao'}")

    print("\nRender (producao):")
    print("  llm_status=offline → XAI_API_KEY ainda NAO esta no Environment do servico")


if __name__ == "__main__":
    main()