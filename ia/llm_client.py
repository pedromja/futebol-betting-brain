"""Cliente LLM xAI — análise live JSON com router Fast/Deep."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from discovery.x_client import XSearchClient
from ia.llm_model_router import MODEL_DEEP, MODEL_FAST, select_llm_model

IA_LLM_MODEL = os.getenv("IA_LLM_MODEL", MODEL_DEEP)

IA_SYSTEM_PROMPT = """És o motor de IA live da app Futebol Betting Brain.
Analisas comentário ESPN, stats live e pressupostos pré-jogo.
Responde APENAS JSON válido (sem markdown) com este schema:
{
  "tips": [
    {
      "market": "nome do mercado (ex: Cantos Over, Vitória Fora)",
      "confidence_pct": 0-100,
      "stake_raw": 0-10,
      "prematch_alignment": "convergent|neutral|divergent",
      "phase_window": "J1|J2|J3|J4",
      "reasoning_pt": "explicação em português",
      "quote_en": "trecho exacto do comentário ESPN em inglês",
      "timing_note": "quando agir"
    }
  ],
  "action_forecasts": [
    {
      "team": "nome equipa",
      "metric": "corners|yellow_cards|goals|offsides|shots_on|fouls",
      "direction": "more|less",
      "horizon_minutes": 15,
      "confidence_pct": 0-100,
      "reasoning_pt": "português",
      "quote_en": "citação EN opcional"
    }
  ]
}

Regras:
- reasoning_pt em português; quote_en em inglês do comentário.
- Podes discordar do pré-jogo (divergent) mas reduz confidence_pct e stake_raw.
- stake_raw máximo 5 na fase inicial (10 = 10% banca).
- Só sugere mercados plausíveis para o minuto actual e fase J1-J4.
- action_forecasts: previsão mais/menos acções por equipa daqui para a frente.
- Se não houver valor, devolve tips: [] mas podes incluir action_forecasts.
- NÃO inventes odds — o sistema anexa odd real ESPN; foca-te em mercados com odds_hint no contexto.
- Para golos/over/under, só recomenda se o cenário live justificar edge vs a odd implícita do mercado."""


def _build_user_prompt(context: dict) -> str:
    return (
        "Analisa este jogo live e gera dicas.\n\n"
        f"CONTEXTO:\n{json.dumps(context, ensure_ascii=False, indent=2)}"
    )


class IaLlmClient:
    def __init__(self, api_key: str | None = None):
        self._key = api_key or os.getenv("XAI_API_KEY", "")

    @property
    def is_live(self) -> bool:
        return bool(self._key)

    def pick_model(self, context: dict) -> tuple[str, str]:
        """Escolhe modelo para este ciclo de análise."""
        if os.getenv("IA_LLM_MODEL"):
            return IA_LLM_MODEL, "env_override"
        return select_llm_model(context)

    def analyze_live(self, context: dict) -> dict:
        """Chama xAI e devolve dict com tips + action_forecasts."""
        if not self.is_live:
            return {"tips": [], "action_forecasts": [], "llm_status": "offline"}

        model, model_reason = self.pick_model(context)
        payload = {
            "model": model,
            "input": [
                {"role": "system", "content": IA_SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(context)},
            ],
        }
        req = urllib.request.Request(
            XSearchClient.API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="replace")
                err_obj = json.loads(detail) if detail else {}
                msg = err_obj.get("error") or err_obj.get("message") or detail[:200]
            except Exception:
                msg = str(exc)
            if "credits" in msg.lower() or "permission-denied" in msg.lower():
                status = "error: xai_sem_creditos"
            else:
                status = f"error: HTTP {exc.code} {msg[:120]}"
            return {
                "tips": [],
                "action_forecasts": [],
                "llm_status": status,
                "llm_model": model,
                "llm_model_reason": model_reason,
            }
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            return {
                "tips": [],
                "action_forecasts": [],
                "llm_status": f"error: {exc}",
                "llm_model": model,
                "llm_model_reason": model_reason,
            }

        text = XSearchClient._extract_text(body)
        parsed = XSearchClient.parse_json_object(text) or {}
        tips = parsed.get("tips") if isinstance(parsed.get("tips"), list) else []
        forecasts = (
            parsed.get("action_forecasts")
            if isinstance(parsed.get("action_forecasts"), list)
            else []
        )
        return {
            "tips": tips,
            "action_forecasts": forecasts,
            "llm_status": "ok",
            "llm_model": model,
            "llm_model_reason": model_reason,
            "raw_excerpt": text[:500] if text else "",
        }


def normalize_llm_output(raw: dict) -> dict:
    """Sanitiza saída LLM."""
    tips_out: list[dict] = []
    for tip in raw.get("tips") or []:
        if not isinstance(tip, dict):
            continue
        market = str(tip.get("market") or "").strip()
        if not market:
            continue
        align = str(tip.get("prematch_alignment") or "neutral").lower()
        if align not in ("convergent", "neutral", "divergent"):
            align = "neutral"
        phase = str(tip.get("phase_window") or "").upper()
        if phase not in ("J1", "J2", "J3", "J4"):
            phase = ""
        try:
            conf = float(tip.get("confidence_pct") or 0)
        except (TypeError, ValueError):
            conf = 0.0
        try:
            stake = float(tip.get("stake_raw") or 0)
        except (TypeError, ValueError):
            stake = 0.0
        tips_out.append(
            {
                "market": market,
                "confidence_pct": max(0.0, min(100.0, conf)),
                "stake_raw": max(0.0, min(10.0, stake)),
                "prematch_alignment": align,
                "phase_window": phase,
                "reasoning_pt": str(tip.get("reasoning_pt") or "").strip(),
                "quote_en": str(tip.get("quote_en") or "").strip(),
                "timing_note": str(tip.get("timing_note") or "").strip(),
            }
        )

    forecasts_out: list[dict] = []
    for row in raw.get("action_forecasts") or []:
        if not isinstance(row, dict):
            continue
        team = str(row.get("team") or "").strip()
        metric = str(row.get("metric") or "").strip().lower()
        direction = str(row.get("direction") or "").lower()
        if not team or direction not in ("more", "less"):
            continue
        try:
            conf = float(row.get("confidence_pct") or 0)
        except (TypeError, ValueError):
            conf = 0.0
        try:
            horizon = int(row.get("horizon_minutes") or 15)
        except (TypeError, ValueError):
            horizon = 15
        forecasts_out.append(
            {
                "team": team,
                "metric": metric or "actions",
                "direction": direction,
                "horizon_minutes": max(5, min(30, horizon)),
                "confidence_pct": max(0.0, min(100.0, conf)),
                "reasoning_pt": str(row.get("reasoning_pt") or "").strip(),
                "quote_en": str(row.get("quote_en") or "").strip(),
            }
        )

    return {
        "tips": tips_out,
        "action_forecasts": forecasts_out,
        "llm_status": raw.get("llm_status") or "ok",
        "llm_model": raw.get("llm_model"),
        "llm_model_reason": raw.get("llm_model_reason"),
    }