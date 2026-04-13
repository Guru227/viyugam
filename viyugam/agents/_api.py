"""Shared Anthropic API helpers — compatibility shim.

All agent modules now import from ``viyugam.engine.client`` directly.
This module re-exports the same symbols so any straggling imports still work.
"""
from __future__ import annotations

from viyugam.engine.client import get_client as _client  # noqa: F401
from viyugam.engine.client import text_of  # noqa: F401
