"""StudioKit MCP server — exposes FL Studio control as MCP tools so Claude
Desktop can drive your DAW in plain language.

Add to claude_desktop_config.json:

    "studiokit": {
      "command": "C:\\\\Users\\\\dylan\\\\.local\\\\bin\\\\uv.exe",
      "args": ["run", "--python", "3.12", "--with", "mcp",
               "python", "E:\\\\studiokit\\\\mcp_server.py"]
    }

Each tool here is a thin typed wrapper over a core.tools handler — the behaviour
lives in core/tools.py, shared with the standalone agent.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from core import FLBridge
import core.tools as T

mcp = FastMCP("studiokit")
bridge = FLBridge()


@mcp.tool()
def get_status() -> str:
    """Read FL Studio's live state: tempo, play/record, position, tracks, pattern."""
    return T.get_status(bridge)


@mcp.tool()
def list_tracks() -> str:
    """List mixer tracks with names, volume, pan, and mute state."""
    return T.list_tracks(bridge)


@mcp.tool()
def set_tempo(bpm: float) -> str:
    """Set the project tempo in BPM."""
    return T.set_tempo(bridge, bpm)


@mcp.tool()
def transport(action: str) -> str:
    """Transport control: 'record' to arm, 'play' to start, 'stop' to halt."""
    return T.transport(bridge, action)


@mcp.tool()
def set_track_volume(track: int, value: float) -> str:
    """Set a mixer track's volume (0.0-~1.25, 1.0 = unity)."""
    return T.set_track_volume(bridge, track, value)


@mcp.tool()
def set_track_pan(track: int, value: float) -> str:
    """Set a mixer track's pan (-1.0 left to 1.0 right)."""
    return T.set_track_pan(bridge, track, value)


@mcp.tool()
def mute_track(track: int) -> str:
    """Toggle mute on a mixer track."""
    return T.mute_track(bridge, track)


@mcp.tool()
def set_channel_volume(channel: int, value: float) -> str:
    """Set an instrument/sample channel's volume (0.0-1.0)."""
    return T.set_channel_volume(bridge, channel, value)


@mcp.tool()
def program_step(channel: int, step: int, on: bool = True) -> str:
    """Set one step sequencer cell on a channel on/off (steps 0-indexed)."""
    return T.program_step(bridge, channel, step, on)


@mcp.tool()
def clear_channel_steps(channel: int, steps: int = 16) -> str:
    """Clear all steps on a channel."""
    return T.clear_channel_steps(bridge, channel, steps)


@mcp.tool()
def select_pattern(pattern: int) -> str:
    """Jump to a pattern by index."""
    return T.select_pattern(bridge, pattern)


if __name__ == "__main__":
    mcp.run()
