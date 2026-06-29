# StudioKit

Claude-powered control of **FL Studio** — produce and record by talking to Claude.
One capability layer, exposed two ways:

- **MCP server** (`mcp_server.py`) — chat in **Claude Desktop**; it calls the tools.
- **Standalone agent** (`agent.py`) — a terminal agent using the Anthropic API.

Both drive the same FL Studio session through a tiny UDP link.

## How it fits together

```
Claude Desktop ─┐                          ┌─ FL Studio
                ├─ mcp_server.py ─┐        │  (device_StudioKit.py
Anthropic API ──┘                 ├─ core/ │   controller script)
 (agent.py) ──────────────────────┘  tools └──UDP 9500 state / 9501 cmds
```

`core/tools.py` is the single source of truth for what StudioKit can do; the MCP
server and the agent are two front-ends onto it.

## What Claude can do

Read live state (tempo, transport, mixer, pattern) and control: **tempo**,
**transport** (arm record / play / stop), **mixer** volume + pan + mute, **channel**
volumes, and the **step sequencer** (program beats cell-by-cell), plus pattern
selection. So *"make a 90 BPM boom-bap beat on channels 0 and 1, then arm
recording"* becomes a sequence of tool calls.

> **Honest scope:** FL Studio's controller API is control-oriented, not full
> project authoring — StudioKit drives a project you've set up (channels/instruments
> loaded). It programs steps, mixes, and runs transport; it can't instantiate
> plugins or draw piano-roll melodies from scratch. Great for beat-making,
> mixing, and hands-free recording.

## Setup

**1. Install the FL Studio controller script (once)**
Copy `fl_script\device_StudioKit.py` into a folder named `StudioKit` under
`Documents\Image-Line\FL Studio\Settings\Hardware\StudioKit\`, then in FL Studio:
**Options → MIDI Settings**, find **StudioKit** in the controller list and enable it.
It links over localhost UDP (9500/9501) — no MIDI hardware needed.

**2. Install Python deps**
```bash
cd E:\studiokit
uv run --python 3.12 --with anthropic --with mcp python -c "print('ok')"
# or: pip install -r requirements.txt
```

**3a. Use it in Claude Desktop (MCP)**
Add to `%APPDATA%\Claude\claude_desktop_config.json` under `mcpServers`:
```json
"studiokit": {
  "command": "C:\\Users\\dylan\\.local\\bin\\uv.exe",
  "args": ["run", "--python", "3.12", "--with", "mcp",
           "python", "E:\\studiokit\\mcp_server.py"]
}
```
Restart Claude Desktop, then ask: *"Using studiokit, set the tempo to 90 and put a
kick on steps 0, 4, 8, 12 of channel 0."*

**3b. Or use the terminal agent**
```bash
set ANTHROPIC_API_KEY=sk-ant-...
uv run --python 3.12 --with anthropic python agent.py "make a 90 BPM beat and arm recording"
```

## Layout

| Path | What it is |
| --- | --- |
| `core/bridge.py` | UDP link to FL (caches state, fires commands) |
| `core/tools.py` | the capability layer (handlers + tool schemas) |
| `fl_script/device_StudioKit.py` | FL Studio controller script (the transport) |
| `mcp_server.py` | FastMCP server for Claude Desktop |
| `agent.py` | standalone Anthropic-API agent |
| `config.py` | host/ports + model |
