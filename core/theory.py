"""Music theory helpers — turn names/roman numerals into MIDI note events.

A note event is (pitch, start_beat, dur_beats, velocity). MIDI convention here is
C4 = 60 (FL Studio default). These feed core.midi.MidiPlayer so Claude can play
chords, progressions, melodies, and drum patterns into a record-armed FL channel.
"""
from __future__ import annotations

import random as _random

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_ALIAS = {"DB": "C#", "EB": "D#", "GB": "F#", "AB": "G#", "BB": "A#"}

SCALES = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "phrygian": [0, 1, 3, 5, 7, 8, 10],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "harmonic_minor": [0, 2, 3, 5, 7, 8, 11],
    "pentatonic_minor": [0, 3, 5, 7, 10],
    "pentatonic_major": [0, 2, 4, 7, 9],
    "blues": [0, 3, 5, 6, 7, 10],
}

CHORDS = {
    "maj": [0, 4, 7], "min": [0, 3, 7], "dim": [0, 3, 6], "aug": [0, 4, 8],
    "sus2": [0, 2, 7], "sus4": [0, 5, 7],
    "maj7": [0, 4, 7, 11], "min7": [0, 3, 7, 10], "7": [0, 4, 7, 10],
    "dim7": [0, 3, 6, 9], "m7b5": [0, 3, 6, 10], "6": [0, 4, 7, 9],
    "min6": [0, 3, 7, 9], "add9": [0, 4, 7, 14], "min9": [0, 3, 7, 10, 14],
    "maj9": [0, 4, 7, 11, 14],
}

# General MIDI drum map (channel 10 sounds; works with most FL drum plugins).
DRUM = {"kick": 36, "snare": 38, "clap": 39, "hat": 42, "closed_hat": 42,
        "open_hat": 46, "rim": 37, "tom": 45, "crash": 49, "ride": 51}

# 16-step patterns (step indices that fire each drum).
DRUM_PATTERNS = {
    "boom_bap": {"kick": [0, 6, 8], "snare": [4, 12],
                 "hat": [0, 2, 4, 6, 8, 10, 12, 14]},
    "trap": {"kick": [0, 7, 10], "snare": [4, 12],
             "hat": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]},
    "house": {"kick": [0, 4, 8, 12], "clap": [4, 12],
              "open_hat": [2, 6, 10, 14]},
    "rock": {"kick": [0, 8], "snare": [4, 12],
             "hat": [0, 2, 4, 6, 8, 10, 12, 14]},
    "funk": {"kick": [0, 3, 6, 10], "snare": [4, 12],
             "hat": [0, 2, 4, 6, 8, 10, 12, 14], "open_hat": [7, 15]},
    "dnb": {"kick": [0, 10], "snare": [4, 12],
            "hat": [0, 2, 4, 6, 8, 10, 12, 14]},
    "afrobeat": {"kick": [0, 6, 8, 14], "rim": [2, 10],
                 "hat": list(range(16))},
}

# Diatonic triad qualities by scale degree (major / natural minor).
_MAJOR_QUAL = ["maj", "min", "min", "maj", "maj", "min", "dim"]
_MINOR_QUAL = ["min", "dim", "maj", "min", "min", "maj", "maj"]
_ROMAN = {"i": 0, "ii": 1, "iii": 2, "iv": 3, "v": 4, "vi": 5, "vii": 6}


def note_num(name: str, octave: int | None = None) -> int:
    """'C', 'C#', 'Db', or 'C4' -> MIDI number (C4 = 60)."""
    name = name.strip()
    if name and name[-1].isdigit():
        octave = int(name[-1])
        name = name[:-1]
    if octave is None:
        octave = 4
    key = name.upper()
    key = _ALIAS.get(key, key)
    if key not in NOTE_NAMES:
        raise ValueError(f"Unknown note {name!r}")
    return 12 * (octave + 1) + NOTE_NAMES.index(key)


def num_name(num: int) -> str:
    return NOTE_NAMES[num % 12] + str(num // 12 - 1)


def chord_notes(root: str, quality: str = "maj", octave: int = 4) -> list[int]:
    if quality not in CHORDS:
        raise ValueError(f"Unknown chord quality {quality!r}")
    base = note_num(root, octave)
    return [base + i for i in CHORDS[quality]]


def scale_notes(root: str, name: str = "major", octave: int = 4) -> list[int]:
    if name not in SCALES:
        raise ValueError(f"Unknown scale {name!r}")
    base = note_num(root, octave)
    return [base + i for i in SCALES[name]]


def progression(key: str, romans: list[str], minor: bool = False,
                octave: int = 4) -> list[tuple[str, str]]:
    """['i','iv','v'] in a key -> [(root_name, quality), ...] (diatonic triads)."""
    deg = scale_notes(key, "minor" if minor else "major", octave)
    quals = _MINOR_QUAL if minor else _MAJOR_QUAL
    out = []
    for r in romans:
        d = _ROMAN.get(r.lower().lstrip("b#"))
        if d is None:
            continue
        out.append((num_name(deg[d]), quals[d]))
    return out


def chord_events(pitches: list[int], start: float, dur: float,
                 vel: int = 90) -> list[tuple]:
    return [(p, start, dur, vel) for p in pitches]


def drum_events(pattern: str, bars: int = 1, vel: int = 100,
                fill: bool = False) -> list[tuple]:
    """16-step pattern -> events. Each step = 0.25 beat (16 per bar). fill=True adds
    a snare build on the last bar's final beat (a transition into the next section)."""
    pat = DRUM_PATTERNS.get(pattern)
    if pat is None:
        raise ValueError(f"Unknown drum pattern {pattern!r}. "
                         f"Try: {', '.join(DRUM_PATTERNS)}")
    events = []
    for bar in range(bars):
        for drum, steps in pat.items():
            note = DRUM[drum]
            for s in steps:
                events.append((note, (bar * 16 + s) * 0.25, 0.1, vel))
        if fill and bar == bars - 1:
            for s in (12, 13, 14, 15):
                events.append((DRUM["snare"], (bar * 16 + s) * 0.25, 0.1,
                               min(127, vel + (s - 11) * 6)))
    return events


def humanize(events: list[tuple], amount: float = 0.5) -> list[tuple]:
    """Jitter note start times and velocities for a less robotic, more human feel.
    amount 0..1 scales the jitter (timing up to ~40ms-equivalent in beats; vel ~22)."""
    if amount <= 0:
        return events
    t_amt = 0.04 * amount
    v_amt = 22 * amount
    out = []
    for (p, start, dur, vel) in events:
        ns = max(0.0, start + _random.uniform(-t_amt, t_amt))
        nv = int(max(1, min(127, vel + _random.uniform(-v_amt, v_amt))))
        out.append((p, ns, dur, nv))
    return out
