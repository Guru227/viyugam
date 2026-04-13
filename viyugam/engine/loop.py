"""engine/loop.py — Shared tool-calling loop for Anthropic API.

Translates the cognitive-service pattern: call API -> detect tool_use blocks
-> execute via dispatch -> append tool_result -> loop until end_turn.
"""
from __future__ import annotations

import json
from typing import Callable

from .client import get_client


def run_tool_calling_loop(
    *,
    system: str,
    messages: list[dict],
    tools: list[dict],
    tool_dispatch: dict[str, Callable],
    max_rounds: int = 5,
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 4096,
    on_text: Callable[[str], None] | None = None,
    connector=None,
) -> tuple[str, dict[str, list]]:
    """Run a tool-calling loop with the Anthropic API.

    Returns:
        (final_text, tool_results_dict)
        - final_text: the last text response from the model
        - tool_results_dict: {tool_name: [result, ...]} for all tool calls made
    """
    client = get_client()
    all_tool_results: dict[str, list] = {}

    for _round in range(max_rounds):
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,  # type: ignore[arg-type]
            tools=tools if tools else [],  # type: ignore[arg-type]
        )

        # Collect any text blocks
        text_parts: list[str] = []
        tool_use_blocks: list = []

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_use_blocks.append(block)

        combined_text = "\n".join(text_parts)

        # If no tool_use blocks, we're done
        if not tool_use_blocks:
            if on_text and combined_text:
                on_text(combined_text)
            return combined_text, all_tool_results

        # If model produced text alongside tool calls, notify
        if on_text and combined_text:
            on_text(combined_text)

        # Append assistant message with all content blocks
        messages.append({"role": "assistant", "content": response.content})

        # Execute each tool and build result messages
        tool_result_blocks: list[dict] = []
        for tool_block in tool_use_blocks:
            tool_name = tool_block.name
            tool_input = tool_block.input
            tool_id = tool_block.id

            executor = tool_dispatch.get(tool_name)
            if executor is None:
                result = {"error": f"Unknown tool: {tool_name}"}
            else:
                try:
                    result = executor(tool_input, connector=connector)
                except Exception as e:
                    result = {"error": str(e)}

            # Track results
            all_tool_results.setdefault(tool_name, []).append(result)

            tool_result_blocks.append({
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": json.dumps(result, default=str),
            })

        messages.append({"role": "user", "content": tool_result_blocks})

        # If stop_reason is end_turn despite tool_use blocks, stop
        if response.stop_reason == "end_turn":
            return combined_text, all_tool_results

    # Exhausted max_rounds — return whatever we have
    return combined_text, all_tool_results
