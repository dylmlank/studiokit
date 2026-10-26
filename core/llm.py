"""Anthropic Messages API chat loop shared by the standalone agent and the companion window.

Uses the native Anthropic SDK with claude-opus-4-8. Tools are authored once in
core.tools with Anthropic-style `input_schema` and dispatched via core.tools.dispatch.
"""
from __future__ import annotations

import json
import os
from typing import Callable

import anthropic

from config import MODEL


def make_client() -> anthropic.Anthropic:
    """Build an Anthropic client, or raise a clear error if unconfigured."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError(
            "No Anthropic API key — add ANTHROPIC_API_KEY=sk-ant-... to .env")
    return anthropic.Anthropic(api_key=key)


def run_loop(client: anthropic.Anthropic, tools: list, dispatch_fn: Callable[[str, dict], str],
             system: str, messages: list, log: Callable[[str], None],
             max_tokens: int = 4096) -> None:
    """Drive the model until it stops calling tools. `messages` is mutated in
    place so multi-turn history carries across calls. `dispatch_fn(name, args)`
    runs a tool and returns its text result."""
    # Convert tools to Anthropic format (they already are, just ensure list structure)
    anthropic_tools = [
        {
            "name": t["name"],
            "description": t.get("description", ""),
            "input_schema": t["input_schema"]
        }
        for t in tools
    ]

    while True:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system,
            tools=anthropic_tools,
            messages=messages
        )

        # Process response and log any text
        if resp.content:
            for block in resp.content:
                if hasattr(block, "text"):
                    text = block.text.strip()
                    if text:
                        log(text)

        # Check if model wants to call tools
        tool_calls = [block for block in resp.content
                     if block.type == "tool_use"]

        if not tool_calls:
            return

        # Add assistant response to messages
        messages.append({
            "role": "assistant",
            "content": resp.content
        })

        # Execute each tool call and add results
        tool_results = []
        for tc in tool_calls:
            try:
                args = tc.input if isinstance(tc.input, dict) else {}
            except (AttributeError, TypeError):
                args = {}

            out = dispatch_fn(tc.name, args)
            log(f"  · {tc.name} -> {str(out)[:160]}")
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tc.id,
                "content": str(out)
            })

        # Add tool results to messages
        messages.append({
            "role": "user",
            "content": tool_results
        })
