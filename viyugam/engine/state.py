"""engine/state.py — Structured context and agent state.

ContextPacket is read-only per-turn context built once from storage.
AgentState is mutable state flowing through agent execution.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass
class ContextPacket:
    """Read-only snapshot of the user's current context."""
    user_name: str = ""
    today: str = ""
    current_time: str = ""
    day_name: str = ""
    season: dict | None = None
    resilience: str = "flow"
    values: dict = field(default_factory=dict)
    energy_pattern: dict | None = None
    constitution: str = ""
    gps_context: Any = None  # PriorityContext from priority.py
    config: Any = None       # ViyugamConfig


@dataclass
class AgentState:
    """Mutable state flowing through agent execution."""
    messages: list[dict] = field(default_factory=list)
    context: ContextPacket = field(default_factory=ContextPacket)
    scratchpad: dict = field(default_factory=dict)
    tool_results: dict[str, list] = field(default_factory=dict)
    next_agent: str | None = None
    focus_hint: str | None = None
    session_type: str | None = None


def build_context() -> ContextPacket:
    """Build a ContextPacket from storage — one call, replaces scattered context-building."""
    from viyugam.storage import (
        check_resilience,
        load_config,
        load_constitution,
        load_state,
        load_values,
    )

    config = load_config()
    state = load_state()
    values = load_values()
    constitution = load_constitution()
    resilience = check_resilience(state)

    now = datetime.now()
    today = date.today()

    season_dict: dict | None = None
    if config.season:
        season_dict = {
            "name": config.season.name,
            "focus": config.season.focus.value if hasattr(config.season.focus, "value") else str(config.season.focus),
        }

    # Energy pattern (best-effort, cached)
    energy: dict | None = None
    try:
        from viyugam.storage import get_energy_pattern
        energy = get_energy_pattern() or None
    except Exception:
        pass

    # GPS context (best-effort)
    gps: Any = None
    try:
        from viyugam.priority import get_context as _get_priority_context
        gps = _get_priority_context()
    except Exception:
        pass

    return ContextPacket(
        user_name=config.user_name or "",
        today=today.isoformat(),
        current_time=now.strftime("%H:%M"),
        day_name=now.strftime("%A"),
        season=season_dict,
        resilience=resilience.value if hasattr(resilience, "value") else str(resilience),
        values=values,
        energy_pattern=energy,
        constitution=constitution,
        gps_context=gps,
        config=config,
    )
