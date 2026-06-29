"""StudioKit's capability layer — defined once, exposed through both the MCP
server (mcp_server.py) and the standalone Claude agent (agent.py).

Each entry in TOOLS has a JSON-schema spec (for Claude's tool-use API) and a
handler `fn(bridge, **kwargs) -> str`. dispatch() runs a handler by name. The
handlers are the single source of truth for what StudioKit can do to FL Studio.
"""
from __future__ import annotations

import math
import time

from core.bridge import FLBridge
from core import theory
from core.midi import MidiPlayer
from config import MIDI_PORT

# One shared MIDI player; opens the port lazily per play() call.
_player = MidiPlayer(MIDI_PORT)


def _bpm(bridge: FLBridge, override) -> float:
    if override:
        return float(override)
    s = bridge.state().get("transport", {})
    return float(s.get("bpm") or 120.0)


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


# --- MIDI playback + theory (plays into FL via the virtual port) -------------

def list_midi_ports(bridge: FLBridge) -> str:
    ports = _player.ports()
    if not ports:
        return ("No MIDI output ports found. Install loopMIDI, create a port, and "
                "enable it as a MIDI input in FL Studio.")
    return "MIDI output ports:\n" + "\n".join(f"  - {p}" for p in ports)


def get_chord(bridge: FLBridge, root: str, quality: str = "maj", octave: int = 4) -> str:
    notes = theory.chord_notes(root, quality, octave)
    return f"{root}{quality}: " + ", ".join(theory.num_name(n) for n in notes)


def get_scale(bridge: FLBridge, root: str, name: str = "major", octave: int = 4) -> str:
    notes = theory.scale_notes(root, name, octave)
    return f"{root} {name}: " + ", ".join(theory.num_name(n) for n in notes)


def _maybe_humanize(events, amount):
    return theory.humanize(events, float(amount)) if amount else events


def _resolve_chord(key, c, minor, octave):
    """A progression item -> (root_name, quality). Item is a roman numeral string
    or a [root, quality] pair."""
    if isinstance(c, str):
        return theory.progression(key, [c], minor=minor, octave=octave)[0]
    return c[0], c[1]


def play_chord(bridge: FLBridge, root: str, quality: str = "maj", octave: int = 4,
               beats: float = 2.0, bpm: float | None = None, channel: int = 0,
               humanize: float = 0.0) -> str:
    notes = theory.chord_notes(root, quality, octave)
    events = theory.chord_events(notes, 0.0, float(beats))
    return _player.play(_maybe_humanize(events, humanize), _bpm(bridge, bpm), channel)


def play_progression(bridge: FLBridge, key: str, chords: list, minor: bool = False,
                     octave: int = 4, beats_per_chord: float = 2.0,
                     bpm: float | None = None, channel: int = 0,
                     humanize: float = 0.0) -> str:
    """chords as roman numerals (['i','iv','v','i']) or [root, quality] pairs."""
    events = []
    t = 0.0
    for c in chords:
        root, qual = _resolve_chord(key, c, minor, octave)
        events += theory.chord_events(theory.chord_notes(root, qual, octave),
                                      t, float(beats_per_chord))
        t += float(beats_per_chord)
    return _player.play(_maybe_humanize(events, humanize), _bpm(bridge, bpm), channel)


def play_melody(bridge: FLBridge, notes: list, bpm: float | None = None,
                channel: int = 0, humanize: float = 0.0) -> str:
    """notes as [name, beats] pairs played in sequence, e.g. [['C4',1],['E4',0.5]].
    Use 'rest' (or '') as the name for a rest."""
    events = []
    t = 0.0
    for item in notes:
        name, beats = item[0], float(item[1])
        if name and name.lower() != "rest":
            events.append((theory.note_num(name), t, beats, 95))
        t += beats
    return _player.play(_maybe_humanize(events, humanize), _bpm(bridge, bpm), channel)


def play_drums(bridge: FLBridge, pattern: str, bars: int = 1,
               bpm: float | None = None, channel: int = 0,
               fill: bool = False, humanize: float = 0.0) -> str:
    events = theory.drum_events(pattern, int(bars), fill=bool(fill))
    return _player.play(_maybe_humanize(events, humanize), _bpm(bridge, bpm), channel)


def play_bassline(bridge: FLBridge, key: str, chords: list, minor: bool = False,
                  octave: int = 2, beats_per_chord: float = 2.0, style: str = "root",
                  bpm: float | None = None, channel: int = 0, humanize: float = 0.0) -> str:
    """PLAY a bassline that follows a chord progression. style: root (held root) |
    eighths (driving repeated roots) | octave (root/octave bounce) | walking (root-
    third-fifth-octave). chords like play_progression. octave 2 = a typical bass register."""
    events = []
    t = 0.0
    bpc = float(beats_per_chord)
    for c in chords:
        root, qual = _resolve_chord(key, c, minor, octave)
        notes = theory.chord_notes(root, qual, octave)
        base = notes[0]
        if style == "eighths":
            for k in range(max(1, int(bpc / 0.5))):
                events.append((base, t + k * 0.5, 0.45, 92))
        elif style == "octave":
            for k in range(max(1, int(bpc / 0.5))):
                events.append((base if k % 2 == 0 else base + 12, t + k * 0.5, 0.45, 92))
        elif style == "walking":
            tones = [notes[0], notes[min(1, len(notes) - 1)],
                     notes[min(2, len(notes) - 1)], base + 12]
            step = bpc / 4.0
            for k in range(4):
                events.append((tones[k], t + k * step, step * 0.9, 90))
        else:  # root
            events.append((base, t, bpc * 0.95, 92))
        t += bpc
    return _player.play(_maybe_humanize(events, humanize), _bpm(bridge, bpm), channel)


def play_arpeggio(bridge: FLBridge, root: str, quality: str = "min7", octave: int = 4,
                  direction: str = "up", note_beats: float = 0.25, repeats: int = 4,
                  bpm: float | None = None, channel: int = 0, humanize: float = 0.0) -> str:
    """PLAY a chord as an arpeggio (one note at a time). direction: up | down | updown.
    note_beats = length of each note (0.25 = sixteenths). repeats = how many cycles."""
    notes = theory.chord_notes(root, quality, octave)
    if direction == "down":
        seq = list(reversed(notes))
    elif direction == "updown" and len(notes) > 2:
        seq = notes + list(reversed(notes[1:-1]))
    else:
        seq = notes
    events = []
    t = 0.0
    nb = float(note_beats)
    for _ in range(int(repeats)):
        for p in seq:
            events.append((p, t, nb * 0.9, 92))
            t += nb
    return _player.play(_maybe_humanize(events, humanize), _bpm(bridge, bpm), channel)


def play_song(bridge: FLBridge, sections: list, bpm: float | None = None,
              channel: int = 0, humanize: float = 0.0) -> str:
    """PLAY a multi-section arrangement back to back on one part — lay down a whole
    structure (intro/verse/chorus) in a single take. Each section is an object:
      {"chords": ["i","iv","v","i"], "key":"A", "minor":true, "beats_per_chord":2, "repeat":2}
      {"drums": "boom_bap", "bars": 4, "fill": true}
      {"melody": [["C4",1],["E4",1]]}
    Sections play in order; 'repeat' loops a section. Arm recording first."""
    events = []
    t = 0.0
    for sec in sections:
        for _ in range(int(sec.get("repeat", 1))):
            if "chords" in sec:
                key = sec.get("key", "C")
                minor = bool(sec.get("minor", False))
                octv = int(sec.get("octave", 4))
                bpc = float(sec.get("beats_per_chord", 2.0))
                for c in sec["chords"]:
                    root, qual = _resolve_chord(key, c, minor, octv)
                    events += theory.chord_events(theory.chord_notes(root, qual, octv), t, bpc)
                    t += bpc
            elif "drums" in sec:
                bars = int(sec.get("bars", 1))
                de = theory.drum_events(sec["drums"], bars, fill=bool(sec.get("fill", False)))
                events += [(p, t + s, d, v) for (p, s, d, v) in de]
                t += bars * 4.0
            elif "melody" in sec:
                for item in sec["melody"]:
                    name, beats = item[0], float(item[1])
                    if name and name.lower() != "rest":
                        events.append((theory.note_num(name), t, beats, 95))
                    t += beats
    if not events:
        return "Empty song — no sections produced notes."
    return _player.play(_maybe_humanize(events, humanize), _bpm(bridge, bpm), channel)


# --- Mixing assistant --------------------------------------------------------

def _db(amp: float) -> float:
    return 20.0 * math.log10(max(float(amp), 1e-6))


def _sample_peaks(bridge: FLBridge, seconds: float) -> dict:
    """Hold the max peak (L/R combined) per mixer track over a short window."""
    peaks: dict[int, float] = {}
    t0 = time.time()
    while time.time() - t0 < seconds:
        for tr in bridge.state().get("mixer", {}).get("tracks", []):
            i = tr["i"]
            p = max(tr.get("pl", 0.0), tr.get("pr", 0.0))
            peaks[i] = max(peaks.get(i, 0.0), p)
        time.sleep(0.05)
    return peaks


def read_levels(bridge: FLBridge, seconds: float = 2.0) -> str:
    """Sample mixer peak levels over a few seconds. Play audio first so there's
    signal. Returns peak dBFS + current volume per track for you to balance."""
    if not bridge.connected():
        return "FL Studio not connected."
    peaks = _sample_peaks(bridge, float(seconds))
    state = {tr["i"]: tr for tr in bridge.state().get("mixer", {}).get("tracks", [])}
    lines = []
    for i in sorted(peaks):
        tr = state.get(i, {})
        pk = peaks[i]
        flag = "  CLIP!" if pk >= 1.0 else ("  (silent)" if pk < 1e-4 else "")
        lines.append(f"  [{i}] {tr.get('n') or '-':<14} peak={_db(pk):6.1f} dBFS  "
                     f"vol={tr.get('v')}{flag}")
    return "Levels (peak over %.1fs):\n" % seconds + "\n".join(lines)


def auto_balance(bridge: FLBridge, target_db: float = -12.0, strength: float = 0.5,
                 seconds: float = 2.0) -> str:
    """Nudge each non-master track's fader toward target_db based on its measured
    peak. Approximate (FL's fader curve isn't linear) and damped by `strength` —
    run a couple of times, or use read_levels and set_track_volume for precision."""
    if not bridge.connected():
        return "FL Studio not connected."
    peaks = _sample_peaks(bridge, float(seconds))
    state = {tr["i"]: tr for tr in bridge.state().get("mixer", {}).get("tracks", [])}
    moved = []
    for i, pk in sorted(peaks.items()):
        if i == 0 or pk < 1e-3:  # skip master and silent tracks
            continue
        cur_vol = float(state.get(i, {}).get("v", 0.8))
        factor = 10 ** ((target_db - _db(pk)) / 20.0 * float(strength))
        new_vol = max(0.0, min(1.0, cur_vol * factor))
        bridge.send("set_mixer_volume", track=i, value=new_vol)
        moved.append(f"[{i}] {cur_vol:.3f}->{new_vol:.3f}")
    if not moved:
        return "Nothing to balance (no signal — play audio first)."
    return f"Nudged toward {target_db} dBFS: " + ", ".join(moved)


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
    "list_midi_ports": list_midi_ports,
    "get_chord": get_chord,
    "get_scale": get_scale,
    "play_chord": play_chord,
    "play_progression": play_progression,
    "play_melody": play_melody,
    "play_drums": play_drums,
    "play_bassline": play_bassline,
    "play_arpeggio": play_arpeggio,
    "play_song": play_song,
    "read_levels": read_levels,
    "auto_balance": auto_balance,
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
    {"name": "list_midi_ports",
     "description": "List virtual MIDI output ports. Use this if note playback fails — FL must listen to the matched port as a MIDI input.",
     "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "get_chord",
     "description": "Get the note names of a chord without playing it (for reasoning). quality e.g. maj, min, min7, maj7, 7, sus4, add9.",
     "input_schema": {"type": "object", "properties": {
         "root": {"type": "string"}, "quality": {"type": "string"}, "octave": {"type": "integer"}},
      "required": ["root"]}},
    {"name": "get_scale",
     "description": "Get the notes of a scale (major, minor, dorian, pentatonic_minor, blues, ...).",
     "input_schema": {"type": "object", "properties": {
         "root": {"type": "string"}, "name": {"type": "string"}, "octave": {"type": "integer"}},
      "required": ["root"]}},
    {"name": "play_chord",
     "description": "PLAY a chord into FL (arm recording on a channel first). quality e.g. min7. beats = how long to hold. humanize 0..1 loosens timing/velocity.",
     "input_schema": {"type": "object", "properties": {
         "root": {"type": "string"}, "quality": {"type": "string"}, "octave": {"type": "integer"},
         "beats": {"type": "number"}, "bpm": {"type": "number"}, "channel": {"type": "integer"},
         "humanize": {"type": "number"}},
      "required": ["root"]}},
    {"name": "play_progression",
     "description": "PLAY a chord progression. chords = roman numerals like ['i','iv','v','i'] in the given key (set minor=true for a minor key), or [root,quality] pairs like [['F','min7'],['Bb','maj7']]. humanize 0..1 for a human feel. Arm recording first.",
     "input_schema": {"type": "object", "properties": {
         "key": {"type": "string"}, "chords": {"type": "array"},
         "minor": {"type": "boolean"}, "octave": {"type": "integer"},
         "beats_per_chord": {"type": "number"}, "bpm": {"type": "number"}, "channel": {"type": "integer"},
         "humanize": {"type": "number"}},
      "required": ["key", "chords"]}},
    {"name": "play_melody",
     "description": "PLAY a melody. notes = [name, beats] pairs in sequence, e.g. [['C4',1],['E4',0.5],['rest',0.5],['G4',1]]. Use 'rest' for silence. humanize 0..1 optional. Arm recording first.",
     "input_schema": {"type": "object", "properties": {
         "notes": {"type": "array"}, "bpm": {"type": "number"}, "channel": {"type": "integer"},
         "humanize": {"type": "number"}},
      "required": ["notes"]}},
    {"name": "play_drums",
     "description": "PLAY a drum pattern via MIDI (boom_bap, trap, house, rock, funk, dnb, afrobeat) for N bars. fill=true adds a snare build on the last bar. humanize 0..1 for swing/feel. Arm recording on a drum channel first.",
     "input_schema": {"type": "object", "properties": {
         "pattern": {"type": "string"}, "bars": {"type": "integer"},
         "bpm": {"type": "number"}, "channel": {"type": "integer"},
         "fill": {"type": "boolean"}, "humanize": {"type": "number"}},
      "required": ["pattern"]}},
    {"name": "play_bassline",
     "description": "PLAY a bassline that follows a chord progression. style: root | eighths | octave | walking. chords like play_progression. octave 2 ~ bass register. humanize 0..1. Arm a bass channel first.",
     "input_schema": {"type": "object", "properties": {
         "key": {"type": "string"}, "chords": {"type": "array"}, "minor": {"type": "boolean"},
         "octave": {"type": "integer"}, "beats_per_chord": {"type": "number"},
         "style": {"type": "string"}, "bpm": {"type": "number"}, "channel": {"type": "integer"},
         "humanize": {"type": "number"}},
      "required": ["key", "chords"]}},
    {"name": "play_arpeggio",
     "description": "PLAY a chord as an arpeggio (one note at a time). direction: up|down|updown. note_beats = each note's length (0.25 = sixteenths). repeats = cycles. humanize 0..1. Arm recording first.",
     "input_schema": {"type": "object", "properties": {
         "root": {"type": "string"}, "quality": {"type": "string"}, "octave": {"type": "integer"},
         "direction": {"type": "string"}, "note_beats": {"type": "number"}, "repeats": {"type": "integer"},
         "bpm": {"type": "number"}, "channel": {"type": "integer"}, "humanize": {"type": "number"}},
      "required": ["root"]}},
    {"name": "play_song",
     "description": "PLAY a multi-section arrangement back to back on one part — lay down a whole structure in one take. sections = list of objects like {\"chords\":[\"i\",\"iv\"],\"key\":\"A\",\"minor\":true,\"beats_per_chord\":2,\"repeat\":2}, {\"drums\":\"boom_bap\",\"bars\":4,\"fill\":true}, or {\"melody\":[[\"C4\",1]]}. Arm recording first.",
     "input_schema": {"type": "object", "properties": {
         "sections": {"type": "array"}, "bpm": {"type": "number"}, "channel": {"type": "integer"},
         "humanize": {"type": "number"}},
      "required": ["sections"]}},
    {"name": "read_levels",
     "description": "Sample mixer peak levels (dBFS) and current volumes over a few seconds — for mixing. Start playback first so there's signal, then read this to decide gain moves.",
     "input_schema": {"type": "object", "properties": {"seconds": {"type": "number"}}, "required": []}},
    {"name": "auto_balance",
     "description": "Nudge each non-master track's fader toward target_db (default -12 dBFS) based on measured peaks. Approximate + damped; run while audio plays. For precise control use read_levels + set_track_volume.",
     "input_schema": {"type": "object", "properties": {
         "target_db": {"type": "number"}, "strength": {"type": "number"}, "seconds": {"type": "number"}},
      "required": []}},
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
