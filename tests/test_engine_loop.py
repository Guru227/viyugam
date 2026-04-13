"""test_engine_loop.py — Tests for the shared tool-calling loop."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from viyugam.engine.loop import run_tool_calling_loop


def _make_text_response(text: str):
    """Create a mock API response with just a text block."""
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = text
    response = MagicMock()
    response.content = [text_block]
    response.stop_reason = "end_turn"
    return response


def _make_tool_use_response(tool_name: str, tool_input: dict, tool_id: str = "tu_123"):
    """Create a mock API response with a tool_use block."""
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = tool_name
    tool_block.input = tool_input
    tool_block.id = tool_id
    response = MagicMock()
    response.content = [tool_block]
    response.stop_reason = "tool_use"
    return response


def test_simple_text_response():
    """Loop returns immediately when the model produces only text."""
    with patch("viyugam.engine.loop.get_client") as mock_get:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_text_response("Hello!")
        mock_get.return_value = mock_client

        text, results = run_tool_calling_loop(
            system="test", messages=[], tools=[], tool_dispatch={},
        )
        assert text == "Hello!"
        assert results == {}
        assert mock_client.messages.create.call_count == 1


def test_tool_use_then_text():
    """Loop executes a tool, re-submits, then gets final text."""
    tool_resp = _make_tool_use_response("get_tasks", {})
    text_resp = _make_text_response("You have 3 tasks today.")

    with patch("viyugam.engine.loop.get_client") as mock_get:
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [tool_resp, text_resp]
        mock_get.return_value = mock_client

        def fake_get_tasks(args, *, connector=None):
            return {"tasks": [{"title": "Task 1"}, {"title": "Task 2"}, {"title": "Task 3"}]}

        text, results = run_tool_calling_loop(
            system="test",
            messages=[{"role": "user", "content": "Show tasks"}],
            tools=[{"name": "get_tasks"}],
            tool_dispatch={"get_tasks": fake_get_tasks},
        )
        assert text == "You have 3 tasks today."
        assert "get_tasks" in results
        assert len(results["get_tasks"]) == 1
        assert mock_client.messages.create.call_count == 2


def test_unknown_tool_returns_error():
    """Unknown tool name produces an error result but loop continues."""
    tool_resp = _make_tool_use_response("nonexistent_tool", {})
    text_resp = _make_text_response("Sorry, I couldn't do that.")

    with patch("viyugam.engine.loop.get_client") as mock_get:
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [tool_resp, text_resp]
        mock_get.return_value = mock_client

        text, results = run_tool_calling_loop(
            system="test",
            messages=[],
            tools=[],
            tool_dispatch={},
        )
        assert "nonexistent_tool" in results
        assert "error" in results["nonexistent_tool"][0]


def test_max_rounds_respected():
    """Loop stops after max_rounds even if model keeps requesting tools."""
    tool_resp = _make_tool_use_response("get_tasks", {})

    with patch("viyugam.engine.loop.get_client") as mock_get:
        mock_client = MagicMock()
        # Always return tool_use — should stop after max_rounds
        mock_client.messages.create.return_value = tool_resp
        mock_get.return_value = mock_client

        text, results = run_tool_calling_loop(
            system="test",
            messages=[],
            tools=[{"name": "get_tasks"}],
            tool_dispatch={"get_tasks": lambda args, **kw: {"tasks": []}},
            max_rounds=3,
        )
        assert mock_client.messages.create.call_count == 3


def test_on_text_callback():
    """on_text callback is called with the final text."""
    captured = []

    with patch("viyugam.engine.loop.get_client") as mock_get:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_text_response("Callback text")
        mock_get.return_value = mock_client

        text, _ = run_tool_calling_loop(
            system="test",
            messages=[],
            tools=[],
            tool_dispatch={},
            on_text=captured.append,
        )
        assert "Callback text" in captured


def test_executor_exception_caught():
    """If an executor raises, the error is captured and sent back to the model."""
    tool_resp = _make_tool_use_response("save_task", {"title": "Test"})
    text_resp = _make_text_response("There was an error saving.")

    with patch("viyugam.engine.loop.get_client") as mock_get:
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [tool_resp, text_resp]
        mock_get.return_value = mock_client

        def bad_executor(args, **kw):
            raise ValueError("disk full")

        text, results = run_tool_calling_loop(
            system="test",
            messages=[],
            tools=[{"name": "save_task"}],
            tool_dispatch={"save_task": bad_executor},
        )
        assert "save_task" in results
        assert "disk full" in results["save_task"][0]["error"]


def test_connector_passed_to_executor():
    """The connector kwarg is forwarded to executors."""
    tool_resp = _make_tool_use_response("get_tasks", {})
    text_resp = _make_text_response("Done")

    with patch("viyugam.engine.loop.get_client") as mock_get:
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [tool_resp, text_resp]
        mock_get.return_value = mock_client

        received_connector = []

        def spy_executor(args, *, connector=None):
            received_connector.append(connector)
            return {"tasks": []}

        fake_connector = MagicMock()
        run_tool_calling_loop(
            system="test",
            messages=[],
            tools=[{"name": "get_tasks"}],
            tool_dispatch={"get_tasks": spy_executor},
            connector=fake_connector,
        )
        assert received_connector[0] is fake_connector
