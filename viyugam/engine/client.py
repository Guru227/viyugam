"""engine/client.py — Shared Anthropic client and helpers.

Replaces the duplicated ``_client()`` across all 12 agent files.
"""
from __future__ import annotations

import os
from typing import Any

import anthropic
from anthropic.types import TextBlock

_cached_client: anthropic.Anthropic | None = None
_cached_key: str | None = None


def get_client() -> anthropic.Anthropic:
    """Return a cached Anthropic client, refreshing if the API key changed."""
    global _cached_client, _cached_key
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        try:
            from viyugam.storage import load_config
            cfg = load_config()
            key = cfg.api_key
        except Exception:
            pass
    if _cached_client is not None and key == _cached_key:
        return _cached_client
    _cached_key = key
    _cached_client = anthropic.Anthropic(api_key=key)
    return _cached_client


def text_of(response: Any) -> str:
    """Extract text from the first TextBlock in an API response."""
    for block in response.content:
        if isinstance(block, TextBlock):
            return block.text
    return ""
