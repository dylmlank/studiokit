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


@mcp.tool()
def list_midi_ports() -> str:
    """List virtual MIDI output ports (FL must listen to the matched one)."""
    return T.list_midi_ports(bridge)


@mcp.tool()
def get_chord(root: str, quality: str = "maj", octave: int = 4) -> str:
    """Get a chord's note names without playing it."""
    return T.get_chord(bridge, root, quality, octave)


@mcp.tool()
def get_scale(root: str, name: str = "major", octave: int = 4) -> str:
    """Get a scale's notes (major, minor, dorian, pentatonic_minor, blues, ...)."""
    return T.get_scale(bridge, root, name, octave)


@mcp.tool()
def play_chord(root: str, quality: str = "maj", octave: int = 4,
               beats: float = 2.0, bpm: float = 0, channel: int = 0) -> str:
    """PLAY a chord into FL (arm recording first). bpm=0 uses the project tempo."""
    return T.play_chord(bridge, root, quality, octave, beats, bpm or None, channel)


@mcp.tool()
def play_progression(key: str, chords: list, minor: bool = False, octave: int = 4,
                     beats_per_chord: float = 2.0, bpm: float = 0, channel: int = 0) -> str:
    """PLAY a chord progression — roman numerals (['i','iv','v','i']) or [root,quality] pairs."""
    return T.play_progression(bridge, key, chords, minor, octave, beats_per_chord,
                              bpm or None, channel)


@mcp.tool()
def play_melody(notes: list, bpm: float = 0, channel: int = 0) -> str:
    """PLAY a melody — [name, beats] pairs, e.g. [['C4',1],['E4',0.5]] ('rest' = silence)."""
    return T.play_melody(bridge, notes, bpm or None, channel)


@mcp.tool()
def play_drums(pattern: str, bars: int = 1, bpm: float = 0, channel: int = 0) -> str:
    """PLAY a drum pattern (boom_bap, trap, house, rock) for N bars. Arm recording first."""
    return T.play_drums(bridge, pattern, bars, bpm or None, channel)


if __name__ == "__main__":
    mcp.run()
