"""Modelo de bot — configuração humana sobre o motor existente."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class BotCondition:
    category: str
    field: str
    operator: str
    value: Any
    label: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BotConfig:
    name: str
    mode: str = "prematch"
    description: str = ""
    active: bool = True
    notify: bool = True
    leagues: list[str] = field(default_factory=list)
    markets: list[str] = field(default_factory=list)
    min_score: float | None = None
    min_ev_pct: float | None = None
    max_stake_level: int | None = None
    minutes_before: int | None = None
    conditions: list[dict] = field(default_factory=list)
    template: str | None = None
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> BotConfig:
        known = {f.name for f in cls.__dataclass_fields__.values()}
        payload = {k: v for k, v in (data or {}).items() if k in known}
        if not payload.get("id"):
            payload["id"] = uuid4().hex[:12]
        return cls(**payload)