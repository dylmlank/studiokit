"""StudioKit's capability layer — defined once, exposed through both the MCP
server (mcp_server.py) and the standalone Claude agent (agent.py).

Each entry in TOOLS has a JSON-schema spec (for Claude's tool-use API) and a
handler `fn(bridge, **kwargs) -> str`. dispatch() runs a handler by name. The
handlers are the single source of truth for what StudioKit can do to FL Studio.
"""
from __future__ import annotations

from core.bridge import FLBridge


def _fmt_status(s: dict) -> str:
    t = s.get("transport", {})
    p = s.get("pattern", {})
    tracks = s.get("mixer", {}).get("tracks", [])
    return (
        f"tempo={t.get('bpm')} BPM | playing={t.get('playing')} | "
        f"recording={t.get('recording')} | pos={t.get('pos')} bars | "
        f"mixer_tracks={len(tracks)} | pattern={p.get('name')!r}"
    )


def get_status(bridge: FLBridge) -> str:
    if not bridge.connected():
        return ("FL Studio is not connected. Open FL Studio and enable the StudioKit "
                "controller script (Options > MIDI Settings).")
    return _fmt_status(bridge.state())


def list_tracks(bridge: FLBridge) -> str:
    if not bridge.connected():
        return "FL Studio not connected."
    tracks = bridge.state().get("mixer", {}).get("tracks", [])
    if not tracks:
        return "No mixer tracks reported yet."
    lines = [f"  [{t['i']}] {t['n'] or '(unnamed)'}  vol={t['v']} pan={t['p']} "
             f"{'MUTED' if t['m'] else ''}" for t in tracks]
    return "Mixer tracks:\n" + "\n".join(lines)


def set_tempo(bridge: FLBridge, bpm: float) -> str:
    bridge.send("set_tempo", value=float(bpm))
    return f"Tempo set to {bpm} BPM."


def transport(bridge: FLBridge, action: str) -> str:
    if action not in ("play", "stop", "record"):
        return f"Unknown transport action {action!r} (use play|stop|record)."
    bridge.send(action)
    return f"Transport: {action}."


def set_track_volume(bridge: FLBridge, track: int, value: float) -> str:
    bridge.send("set_mixer_volume", track=int(track), value=float(value))
    return f"Mixer track {track} volume -> {value}."


def set_track_pan(bridge: FLBridge, track: int, value: float) -> str:
    bridge.send("set_mixer_pan", track=int(track), value=float(value))
    return f"Mixer track {track} pan -> {value}."


def mute_track(bridge: FLBridge, track: int) -> str:
    bridge.send("toggle_mute", track=int(track))
    return f"Toggled mute on mixer track {track}."


def set_channel_volume(bridge: FLBridge, channel: int, value: float) -> str:
    bridge.send("set_channel_volume", channel=int(channel), value=float(value))
    return f"Channel {channel} volume -> {value}."


def program_step(bridge: FLBridge, channel: int, step: int, on: bool = True) -> str:
    bridge.send("set_step", channel=int(channel), step=int(step), value=1 if on else 0)
    return f"Step {step} on channel {channel} -> {'on' if on else 'off'}."


def clear_channel_steps(bridge: FLBridge, channel: int, steps: int = 16) -> str:
    bridge.send("clear_steps", channel=int(channel), steps=int(steps))
    return f"Cleared {steps} steps on channel {channel}."


def select_pattern(bridge: FLBridge, pattern: int) -> str:
    bridge.send("select_pattern", pattern=int(pattern))
    return f"Selected pattern {pattern}."


# name -> handler
_HANDLERS = {
    "get_status": get_status,
    "list_tracks": list_tracks,
    "set_tempo": set_tempo,
    "transport": transport,
    "set_track_volume": set_track_volume,
    "set_track_pan": set_track_pan,
    "mute_track": mute_track,
    "set_channel_volume": set_channel_volume,
    "program_step": program_step,
    "clear_channel_steps": clear_channel_steps,
    "select_pattern": select_pattern,
}

# JSON-schema specs for Claude's tool-use API. Kept next to the handlers so the
# two front-ends share one definition.
TOOLS = [
    {"name": "get_status",
     "description": "Read FL Studio's live state: tempo, play/record status, song position, mixer track count, current pattern.",
     "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "list_tracks",
     "description": "List the FL Studio mixer tracks with their names, volumes, pan, and mute state.",
     "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "set_tempo",
     "description": "Set the project tempo in beats per minute.",
     "input_schema": {"type": "object",
                      "properties": {"bpm": {"type": "number", "description": "Tempo in BPM, e.g. 120"}},
                      "required": ["bpm"]}},
    {"name": "transport",
     "description": "Control the transport. Use 'record' to arm recording, then 'play' to start capturing, 'stop' to halt.",
     "input_schema": {"type": "object",
                      "properties": {"action": {"type": "string", "enum": ["play", "stop", "record"]}},
                      "required": ["action"]}},
    {"name": "set_track_volume",
     "description": "Set a mixer track's volume (0.0 silent to 1.0 unity, up to ~1.25 max).",
     "input_schema": {"type": "object",
                      "properties": {"track": {"type": "integer"}, "value": {"type": "number"}},
                      "required": ["track", "value"]}},
    {"name": "set_track_pan",
     "description": "Set a mixer track's pan from -1.0 (left) to 1.0 (right).",
     "input_schema": {"type": "object",
                      "properties": {"track": {"type": "integer"}, "value": {"type": "number"}},
                      "required": ["track", "value"]}},
    {"name": "mute_track",
     "description": "Toggle mute on a mixer track.",
     "input_schema": {"type": "object", "properties": {"track": {"type": "integer"}}, "required": ["track"]}},
    {"name": "set_channel_volume",
     "description": "Set an instrument/sample channel's volume (0.0 to 1.0).",
     "input_schema": {"type": "object",
                      "properties": {"channel": {"type": "integer"}, "value": {"type": "number"}},
                      "required": ["channel", "value"]}},
    {"name": "program_step",
     "description": "Program one step in the step sequencer: set a grid cell on a channel on or off. Steps are 0-indexed (0-15 for a 16-step pattern).",
     "input_schema": {"type": "object",
                      "properties": {"channel": {"type": "integer"}, "step": {"type": "integer"},
                                     "on": {"type": "boolean", "default": True}},
                      "required": ["channel", "step"]}},
    {"name": "clear_channel_steps",
     "description": "Clear all steps on a channel in the step sequencer.",
     "input_schema": {"type": "object",
                      "properties": {"channel": {"type": "integer"}, "steps": {"type": "integer", "default": 16}},
                      "required": ["channel"]}},
    {"name": "select_pattern",
     "description": "Jump to a pattern by index.",
     "input_schema": {"type": "object", "properties": {"pattern": {"type": "integer"}}, "required": ["pattern"]}},
]


def dispatch(bridge: FLBridge, name: str, arguments: dict) -> str:
    """Run a tool by name with the given arguments. Returns a text result."""
    handler = _HANDLERS.get(name)
    if handler is None:
        return f"Unknown tool: {name}"
    try:
        return handler(bridge, **(arguments or {}))
    except Exception as e:  # surface tool errors back to the model
        return f"Error in {name}: {e}"
