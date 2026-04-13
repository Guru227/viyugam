"""test_engine_client.py — Tests for engine/client.py."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from viyugam.engine.client import get_client, text_of


def test_get_client_uses_env_var():
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key-123"}):
        client = get_client()
        assert client is not None


def test_get_client_falls_back_to_config(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    mock_cfg = MagicMock()
    mock_cfg.api_key = "config-key-456"
    with patch("viyugam.engine.client.os.environ", {"OTHER": "x"}):
        with patch("viyugam.storage.load_config", return_value=mock_cfg):
            client = get_client()
            assert client is not None


def test_text_of_extracts_text():
    mock_block = MagicMock()
    mock_block.text = "Hello world"
    # Simulate isinstance check for TextBlock
    from anthropic.types import TextBlock
    mock_response = MagicMock()
    real_block = TextBlock(text="Hello world", type="text")
    mock_response.content = [real_block]
    result = text_of(mock_response)
    assert result == "Hello world"


def test_text_of_empty_response():
    mock_response = MagicMock()
    mock_response.content = []
    result = text_of(mock_response)
    assert result == ""
