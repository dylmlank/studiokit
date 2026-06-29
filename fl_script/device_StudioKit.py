# StudioKit — FL Studio MIDI Controller Script
# Install: copy this folder to
#   Documents/Image-Line/FL Studio/Settings/Hardware/StudioKit/
# Then select "StudioKit" as a controller in FL Studio > Options > MIDI Settings.
#
# It broadcasts project state to the StudioKit app on 9500 and applies commands
# received on 9501. The app (MCP server or agent) is what Claude drives.

import socket
import json
import time

import mixer
import transport
import channels
import patterns
import ui

HOST = "127.0.0.1"       # StudioKit app IP
SEND_PORT = 9500          # state broadcasts TO the app
RECV_PORT = 9501          # commands FROM the app
STATE_INTERVAL = 0.05     # ~20 Hz
MAX_TRACKS = 32

_send_sock = None
_recv_sock = None
_last_state_time = 0


def OnInit():
    global _send_sock, _recv_sock
    try:
        _send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        _recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        _recv_sock.bind(("0.0.0.0", RECV_PORT))
        _recv_sock.setblocking(False)
        ui.setHintMsg("StudioKit: Connected")
    except Exception as e:
        print("StudioKit init error: " + str(e))


def OnDeInit():
    try:
        if _send_sock:
            _send_sock.close()
        if _recv_sock:
            _recv_sock.close()
    except Exception:
        pass


def OnIdle():
    global _last_state_time
    _poll_commands()
    now = time.time()
    if now - _last_state_time >= STATE_INTERVAL:
        _broadcast_state()
        _last_state_time = now


def OnRefresh(flags):
    _broadcast_state()


def OnMidiMsg(event):
    event.handled = False


def _broadcast_state():
    if not _send_sock:
        return
    try:
        data = json.dumps({"type": "state", "payload": _build_state()}).encode()
        _send_sock.sendto(data, (HOST, SEND_PORT))
    except Exception:
        pass


def _build_state():
    tracks = []
    count = min(mixer.trackCount(), MAX_TRACKS)
    for i in range(count):
        name, vol, pan, muted = "", 0.0, 0.0, False
        pk_l, pk_r = 0.0, 0.0
        try:
            name = mixer.getTrackName(i)
        except Exception:
            pass
        try:
            vol = mixer.getTrackVolume(i)
        except Exception:
            pass
        try:
            pan = mixer.getTrackPan(i)
        except Exception:
            pass
        try:
            muted = mixer.isTrackMuted(i)
        except Exception:
            pass
        try:
            pk_l = mixer.getTrackPeaks(i, 0)
            pk_r = mixer.getTrackPeaks(i, 1)
        except Exception:
            pass
        tracks.append({"i": i, "n": name, "v": round(vol, 4),
                       "p": round(pan, 4), "m": muted,
                       "pl": round(pk_l, 4), "pr": round(pk_r, 4)})

    t_playing = t_recording = False
    t_bpm, t_pos = 120.0, 0.0
    try:
        t_playing = transport.isPlaying()
    except Exception:
        pass
    try:
        t_recording = transport.isRecording()
    except Exception:
        pass
    try:
        t_bpm = transport.getTempo()
    except Exception:
        pass
    try:
        t_pos = transport.getSongPos(2)  # mode 2 = bars
    except Exception:
        pass

    pat_idx, pat_name = 0, ""
    try:
        pat_idx = patterns.patternNumber()
        pat_name = patterns.getPatternName(pat_idx)
    except Exception:
        pass

    return {
        "mixer": {"tracks": tracks},
        "transport": {"playing": t_playing, "recording": t_recording,
                      "bpm": round(t_bpm, 2), "pos": round(t_pos, 2)},
        "pattern": {"idx": pat_idx, "name": pat_name},
    }


def _poll_commands():
    if not _recv_sock:
        return
    for _ in range(20):
        try:
            data, _ = _recv_sock.recvfrom(4096)
            _dispatch(json.loads(data.decode()).get("payload", {}))
        except BlockingIOError:
            break
        except Exception:
            break


def _dispatch(p):
    action = p.get("action", "")
    try:
        if action == "set_tempo":
            transport.setTempo(p["value"])
        elif action == "play":
            transport.start()
        elif action == "stop":
            transport.stop()
        elif action == "record":
            transport.record()
        elif action == "set_mixer_volume":
            mixer.setTrackVolume(p["track"], p["value"])
        elif action == "set_mixer_pan":
            mixer.setTrackPan(p["track"], p["value"])
        elif action == "toggle_mute":
            mixer.muteTrack(p["track"])
        elif action == "set_channel_volume":
            channels.setChannelVolume(p["channel"], p["value"])
        elif action == "set_step":
            channels.setGridBit(p["channel"], p["step"], p["value"])
        elif action == "clear_steps":
            for s in range(p.get("steps", 16)):
                channels.setGridBit(p["channel"], s, 0)
        elif action == "select_pattern":
            patterns.jumpToPattern(p["pattern"])
    except Exception as e:
        print("StudioKit cmd error: " + action + " - " + str(e))
