"""test_engine_state.py — Tests for engine/state.py."""
from __future__ import annotations

from viyugam.engine.state import AgentState, ContextPacket, build_context


def test_context_packet_defaults():
    ctx = ContextPacket()
    assert ctx.user_name == ""
    assert ctx.today == ""
    assert ctx.resilience == "flow"
    assert ctx.values == {}
    assert ctx.energy_pattern is None
    assert ctx.gps_context is None


def test_agent_state_defaults():
    state = AgentState()
    assert state.messages == []
    assert isinstance(state.context, ContextPacket)
    assert state.scratchpad == {}
    assert state.tool_results == {}
    assert state.next_agent is None
    assert state.focus_hint is None
    assert state.session_type is None


def test_build_context_returns_packet():
    ctx = build_context()
    assert isinstance(ctx, ContextPacket)
    assert ctx.today != ""
    assert ctx.current_time != ""
    assert ctx.day_name != ""
    assert ctx.config is not None


def test_build_context_loads_values():
    ctx = build_context()
    # Values should be a dict (may be empty if no values.yaml in test env)
    assert isinstance(ctx.values, dict)
