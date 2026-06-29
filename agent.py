"""StudioKit standalone agent — talk to Claude in your terminal and it drives
FL Studio through the same tools the MCP server exposes.

    set ANTHROPIC_API_KEY=...        (Windows: setx, or a .env loaded by your shell)
    python agent.py                  # interactive
    python agent.py "make a 90 BPM boom-bap beat on channels 0 and 1"

Uses the Anthropic SDK manual tool-use loop with claude-opus-4-8 and adaptive
thinking. The tool set comes from core.tools.TOOLS; results are dispatched via
core.tools.dispatch — one definition, shared with mcp_server.py.
"""
from __future__ import annotations

import sys

import anthropic

from config import MODEL
from core import FLBridge, TOOLS, dispatch

SYSTEM = (
    "You are StudioKit, a music production assistant wired directly into the user's "
    "FL Studio session over a live link. You can read project state and control "
    "tempo, transport (including arming recording), the mixer, channel volumes, and "
    "the step sequencer. When asked to make a beat, program the relevant step-"
    "sequencer cells on the named channels (16 steps per bar, 0-indexed). Call "
    "get_status first if you need to know the current tempo or track layout. Keep "
    "replies short; act with the tools rather than describing what you would do."
)


def run(bridge: FLBridge, client: anthropic.Anthropic, user_text: str,
        history: list) -> list:
    history.append({"role": "user", "content": user_text})
    while True:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            thinking={"type": "adaptive"},
            system=SYSTEM,
            tools=TOOLS,
            messages=history,
        )
        history.append({"role": "assistant", "content": resp.content})

        for block in resp.content:
            if block.type == "text" and block.text.strip():
                print(f"\n{block.text.strip()}\n")

        if resp.stop_reason != "tool_use":
            return history

        results = []
        for block in resp.content:
            if block.type == "tool_use":
                out = dispatch(bridge, block.name, block.input)
                print(f"  · {block.name}({block.input}) -> {out}")
                results.append({"type": "tool_result", "tool_use_id": block.id,
                                "content": out})
        history.append({"role": "user", "content": results})


def main() -> int:
    bridge = FLBridge()
    client = anthropic.Anthropic()
    history: list = []

    if len(sys.argv) > 1:
        run(bridge, client, " ".join(sys.argv[1:]), history)
        return 0

    print("StudioKit agent — describe what you want in FL Studio (Ctrl+C to quit).")
    try:
        while True:
            text = input("\n> ").strip()
            if text:
                run(bridge, client, text, history)
    except (KeyboardInterrupt, EOFError):
        print("\nbye")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
