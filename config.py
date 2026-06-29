"""Shared settings for StudioKit. Env vars override the defaults."""
from __future__ import annotations

import os

# UDP link to the StudioKit FL Studio controller script.
FL_HOST = os.environ.get("STUDIOKIT_HOST", "127.0.0.1")
STATE_PORT = int(os.environ.get("STUDIOKIT_STATE_PORT", "9500"))  # FL -> us
CMD_PORT = int(os.environ.get("STUDIOKIT_CMD_PORT", "9501"))      # us -> FL

# Virtual MIDI port name (substring) that FL listens to as an input. Create one
# with loopMIDI; StudioKit plays chords/melodies/drums into it for FL to record.
MIDI_PORT = os.environ.get("STUDIOKIT_MIDI_PORT", "loopMIDI")

# Claude model for the standalone agent (claude-opus-4-8 is the latest Opus).
MODEL = os.environ.get("STUDIOKIT_MODEL", "claude-opus-4-8")
