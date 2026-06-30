r"""StudioKit companion — a small always-on-top prompt window that floats next to FL
Studio and drives it live.

FL's scripting can't host a text-prompt UI, so this window is the way to "talk" to
your session: type "make a 90 BPM boom-bap beat, then play an Am7-Dm7-G7 progression
with some humanize", hit Send, and Claude controls FL through StudioKit's tools
(tempo, transport, mixer, step sequencer, MIDI chords/bass/arps/drums, mixing).

Run it:
    uv run --python 3.12 --with anthropic --with mido --with python-rtmidi python companion.py

API key: set ANTHROPIC_API_KEY, or put it in `E:\studiokit\.env` as
    ANTHROPIC_API_KEY=sk-ant-...
The window opens either way and tells you if the key (or FL) isn't connected.
"""
from __future__ import annotations

import os
import queue
import sys
import threading
from pathlib import Path


def _app_dir() -> Path:
    """Folder the program lives in (next to the .exe when frozen)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def _load_env():
    env = _app_dir() / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()

import tkinter as tk  # noqa: E402
from tkinter import scrolledtext  # noqa: E402

from config import MODEL  # noqa: E402
from core import FLBridge, TOOLS, dispatch  # noqa: E402

SYSTEM = (
    "You are StudioKit, wired into the user's live FL Studio session. Control tempo, "
    "transport (arm record, play, stop), the mixer, channels, and the step sequencer, "
    "and play MIDI chords/progressions/basslines/arpeggios/drums/whole arrangements "
    "into a record-armed channel. Call get_status first if you need the tempo or "
    "layout. To capture played MIDI, the user must arm recording on a channel and have "
    "the loopMIDI port enabled as an FL input. Keep replies short; act with the tools."
)


def run_agent(bridge, prompt: str, log) -> None:
    import anthropic
    client = anthropic.Anthropic()
    messages = [{"role": "user", "content": prompt}]
    while True:
        resp = client.messages.create(
            model=MODEL, max_tokens=4096, thinking={"type": "adaptive"},
            system=SYSTEM, tools=TOOLS, messages=messages)
        messages.append({"role": "assistant", "content": resp.content})
        for b in resp.content:
            if b.type == "text" and b.text.strip():
                log(b.text.strip())
        if resp.stop_reason != "tool_use":
            return
        results = []
        for b in resp.content:
            if b.type == "tool_use":
                out = dispatch(bridge, b.name, b.input)
                log(f"  · {b.name} -> {str(out)[:160]}")
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": str(out)})
        messages.append({"role": "user", "content": results})


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.q: queue.Queue = queue.Queue()
        self.bridge = FLBridge()
        root.title("StudioKit")
        root.geometry("520x500")
        root.attributes("-topmost", True)

        self.have_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
        if not self.have_key:
            tk.Label(root, bg="#7a1f1f", fg="white", anchor="w",
                     text=(" No ANTHROPIC_API_KEY. Add it to E:\\studiokit\\.env "
                           "(ANTHROPIC_API_KEY=sk-ant-...) and reopen.")).pack(fill="x")

        self.status = tk.Label(root, anchor="w", fg="#555",
                               text="Checking FL Studio connection…")
        self.status.pack(fill="x", padx=8, pady=(6, 0))

        tk.Label(root, text="Prompt:", anchor="w").pack(fill="x", padx=8, pady=(8, 0))
        self.prompt = tk.Text(root, height=4, wrap="word")
        self.prompt.pack(fill="x", padx=8)
        self.prompt.insert("1.0", "set 90 BPM and play an Am7 - Dm7 - G7 progression with humanize")

        self.go = tk.Button(root, text="Send", command=self.send)
        self.go.pack(fill="x", padx=8, pady=6)

        self.out = scrolledtext.ScrolledText(root, height=16, state="disabled", wrap="word")
        self.out.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.root.after(100, self._drain)
        self._refresh_status()

    def _refresh_status(self):
        if self.bridge.connected():
            self.status.configure(text="● FL Studio connected", fg="#1a7f1a")
        else:
            self.status.configure(
                text="○ FL not detected — open FL with the StudioKit controller enabled",
                fg="#7a5a1f")
        self.root.after(2000, self._refresh_status)

    def log(self, msg: str):
        self.q.put(msg)

    def _drain(self):
        while not self.q.empty():
            msg = self.q.get()
            if msg == "__DONE__":
                self.go.configure(state="normal", text="Send")
                continue
            self.out.configure(state="normal")
            self.out.insert("end", msg + "\n")
            self.out.see("end")
            self.out.configure(state="disabled")
        self.root.after(100, self._drain)

    def send(self):
        if not self.have_key:
            self.log("Add your API key to E:\\studiokit\\.env first.")
            return
        prompt = self.prompt.get("1.0", "end").strip()
        if not prompt:
            self.log("Type a prompt first.")
            return
        self.go.configure(state="disabled", text="Working…")
        self.log(f"> {prompt}")

        def worker():
            try:
                run_agent(self.bridge, prompt, self.log)
            except Exception as e:
                self.log(f"Error: {e}")
            finally:
                self.log("__DONE__")

        threading.Thread(target=worker, daemon=True).start()


def _selftest():
    """Verify a frozen build can load everything it needs, then exit. Writes
    selftest.json next to the program. Run as: StudioKit.exe --selftest"""
    import json
    result = {"app": "StudioKit", "frozen": bool(getattr(sys, "frozen", False))}
    try:
        import anthropic
        anthropic.Anthropic(api_key="selftest")
        result["anthropic"] = anthropic.__version__
    except Exception as e:
        result["anthropic"] = f"FAIL: {e}"
    try:
        import mido
        mido.get_output_names()
        result["midi"] = "ok"
    except Exception as e:
        result["midi"] = f"FAIL: {e}"
    try:
        root = tk.Tk()
        App(root)
        root.update()
        root.destroy()
        result["ui"] = "ok"
    except Exception as e:
        result["ui"] = f"FAIL: {e}"
    (_app_dir() / "selftest.json").write_text(json.dumps(result), encoding="utf-8")
    print(json.dumps(result))


def main():
    if "--selftest" in sys.argv:
        _selftest()
        return
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
