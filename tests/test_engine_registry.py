"""test_engine_registry.py — Tests for the tool registry and builder functions."""
from __future__ import annotations

from viyugam.engine.tools.registry import (
    TOOL_REGISTRY,
    ToolCategory,
    ToolSpec,
    build_all_read_tools,
    build_tools_for_agent,
)


def test_registry_has_30_tools():
    assert len(TOOL_REGISTRY) == 30


def test_all_specs_are_toolspec():
    for name, spec in TOOL_REGISTRY.items():
        assert isinstance(spec, ToolSpec), f"{name} is not ToolSpec"
        assert spec.name == name
        assert spec.domain != ""
        assert spec.category in (ToolCategory.READ, ToolCategory.WRITE)


def test_build_tools_for_agent_filters_by_domain():
    decls, dispatch = build_tools_for_agent(["task"])
    names = [d["name"] for d in decls]
    assert "get_tasks" in names
    assert "save_task" in names
    assert "get_goals" not in names
    # dispatch keys match declaration names
    assert set(names) == set(dispatch.keys())


def test_build_tools_for_agent_multi_domain():
    decls, dispatch = build_tools_for_agent(["task", "goal", "finance"])
    names = [d["name"] for d in decls]
    assert "get_tasks" in names
    assert "get_goals" in names
    assert "get_budget_summary" in names


def test_build_tools_for_agent_empty_domain():
    decls, dispatch = build_tools_for_agent([])
    assert decls == []
    assert dispatch == {}


def test_build_all_read_tools():
    decls, dispatch = build_all_read_tools()
    # Should include only READ tools
    for name in dispatch:
        assert TOOL_REGISTRY[name].category == ToolCategory.READ
    # Should not include WRITE tools
    write_names = {name for name, spec in TOOL_REGISTRY.items() if spec.category == ToolCategory.WRITE}
    for wn in write_names:
        assert wn not in dispatch


def test_executors_are_callable():
    _, dispatch = build_all_read_tools()
    for name, fn in dispatch.items():
        assert callable(fn), f"Executor for {name} is not callable"
