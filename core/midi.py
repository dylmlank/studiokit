"""Real-time MIDI playback into FL Studio via a virtual MIDI port.

FL's controller API can't author the piano roll, so StudioKit *plays* notes the
way a keyboard would: it sends MIDI to a virtual port (e.g. a loopMIDI port) that
FL listens to as a MIDI input. Arm recording on a channel in FL and the notes
land in the piano roll. Needs `mido` + `python-rtmidi`.

Setup once:
  1. Install loopMIDI (tobias-erichsen.de/software/loopmidi.html) and create a
     port (any name; StudioKit matches on STUDIOKIT_MIDI_PORT, default 'loopMIDI').
  2. In FL: Options > MIDI Settings, enable that port as an INPUT (set a port
     number / 'Enable').
"""
from __future__ import annotations

import time

try:
    import mido
except ImportError:  # surfaced as a friendly tool message
    mido = None


class MidiPlayer:
    def __init__(self, port_match: str):
        self.port_match = port_match

    def ports(self) -> list[str]:
        return list(mido.get_output_names()) if mido else []

    def _open(self):
        if mido is None:
            raise RuntimeError("mido / python-rtmidi not installed "
                               "(pip install mido python-rtmidi).")
        names = mido.get_output_names()
        match = next((n for n in names if self.port_match.lower() in n.lower()), None)
        if match is None:
            raise RuntimeError(
                f"No MIDI output matching {self.port_match!r}. Available: {names or '(none)'}. "
                "Install loopMIDI, create a port, and enable it as a MIDI input in FL.")
        return mido.open_output(match)

    def play(self, events: list[tuple], bpm: float, channel: int = 0) -> str:
        """Play note events in real time so FL can record them.

        events: list of (pitch, start_beat, dur_beats, velocity).
        """
        if not events:
            return "No notes to play."
        spb = 60.0 / float(bpm)
        timeline: list[tuple] = []
        for pitch, start, dur, vel in events:
            timeline.append((start * spb, 1, int(pitch), int(vel)))
            timeline.append(((start + dur) * spb, 0, int(pitch), 0))
        timeline.sort(key=lambda x: (x[0], x[1]))  # note-offs before ons at same t

        out = self._open()
        try:
            t0 = time.time()
            for when, on, pitch, vel in timeline:
                delay = when - (time.time() - t0)
                if delay > 0:
                    time.sleep(delay)
                kind = "note_on" if on else "note_off"
                out.send(mido.Message(kind, note=pitch, velocity=vel, channel=channel))
            time.sleep(0.05)
            for _, on, pitch, _ in timeline:  # safety: ensure all notes off
                if on:
                    out.send(mido.Message("note_off", note=pitch, velocity=0, channel=channel))
        finally:
            out.close()
        return f"Played {len(events)} notes at {bpm} BPM."
