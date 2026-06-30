"""Gate de produção — aplica restrições da auditoria IA aos bots."""

from __future__ import annotations

from bots.ia_audit import check_ia_blocked, is_ia_bot, load_ia_audit


def filter_ia_bot_matches(
    bot,
    matches: list[dict],
    *,
    audit=None,
) -> tuple[list[dict], list[dict]]:
    """
    Separa jogos permitidos vs bloqueados por auditoria.
    Devolve (permitidos, bloqueados_com_motivo).
    """
    if not is_ia_bot(getattr(bot, "template", None), getattr(bot, "name", None)):
        return matches, []

    state = audit or load_ia_audit()
    allowed: list[dict] = []
    blocked: list[dict] = []

    for match in matches:
        hit, reason = check_ia_blocked(
            template=getattr(bot, "template", None),
            match=match,
            audit=state,
        )
        if hit:
            m = {**match, "ia_restricted": True, "ia_block_reason": reason}
            blocked.append(m)
        else:
            m = {**match, "ia_restricted": False}
            allowed.append(m)

    return allowed, blocked


def apply_ia_gate_to_hits(hits: list[dict], *, audit=None) -> list[dict]:
    """Remove matches bloqueados; anota hits com resumo de auditoria."""
    state = audit or load_ia_audit()
    out: list[dict] = []

    for hit in hits:
        bot_template = hit.get("template")
        bot_name = hit.get("bot_name")
        if not is_ia_bot(bot_template, bot_name):
            out.append(hit)
            continue

        matches = hit.get("matches") or []
        allowed = []
        for m in matches:
            blocked, reason = check_ia_blocked(
                template=bot_template,
                match=m,
                audit=state,
            )
            if blocked:
                continue
            allowed.append({**m, "ia_audit_active": state.active})

        if not allowed:
            continue
        enriched = {**hit, "matches": allowed, "ia_audit_active": state.active}
        if state.knowledge:
            enriched["ia_knowledge_hint"] = state.knowledge[0]
        out.append(enriched)

    return out