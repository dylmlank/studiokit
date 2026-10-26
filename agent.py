r"""StudioKit standalone agent — talk to a model in your terminal and it drives
FL Studio through the same tools the MCP server exposes.

    # in E:\studiokit\.env (or the environment):
    #   ANTHROPIC_API_KEY=sk-ant-...
    #   STUDIOKIT_MODEL=claude-opus-4-8             (optional; default is claude-opus-4-8)
    python agent.py                  # interactive
    python agent.py "make a 90 BPM boom-bap beat on channels 0 and 1"

Generation runs through the native Anthropic API (core.llm). The tool
set comes from core.tools.TOOLS; results are dispatched via core.tools.dispatch —
one definition, shared with mcp_server.py.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _load_env() -> None:
    env = Path(__file__).parent / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()

from core import FLBridge, TOOLS, dispatch  # noqa: E402
from core.llm import make_client, run_loop  # noqa: E402

SYSTEM = (
    "You are StudioKit, a music production assistant wired directly into the user's "
    "FL Studio session over a live link. You can read project state and control "
    "tempo, transport (including arming recording), the mixer, channel volumes, and "
    "the step sequencer. When asked to make a beat, program the relevant step-"
    "sequencer cells on the named channels (16 steps per bar, 0-indexed). Call "
    "get_status first if you need to know the current tempo or track layout. Keep "
    "replies short; act with the tools rather than describing what you would do."
)


def main() -> int:
    bridge = FLBridge()
    client = make_client()
    history: list = []

    def drive(text: str) -> None:
        history.append({"role": "user", "content": text})
        run_loop(client, TOOLS, lambda n, a: dispatch(bridge, n, a),
                 SYSTEM, history, print, max_tokens=4096)

    if len(sys.argv) > 1:
        drive(" ".join(sys.argv[1:]))
        return 0

    print("StudioKit agent — describe what you want in FL Studio (Ctrl+C to quit).")
    try:
        while True:
            text = input("\n> ").strip()
            if text:
                drive(text)
    except (KeyboardInterrupt, EOFError):
        print("\nbye")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
