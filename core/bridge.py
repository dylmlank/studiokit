"""UDP bridge to the StudioKit FL Studio controller script.

FL Studio's controller API is one-way: the script broadcasts JSON state to us on
STATE_PORT (we cache the latest), and we fire JSON commands at it on CMD_PORT
(there's no return value — FL just applies them). A daemon thread keeps the
cached state fresh so tools can read tempo / tracks / transport without blocking.
Wire format matches device_StudioKit.py: {"type": "command", "payload": {...}}.
"""
from __future__ import annotations

import json
import socket
import threading
import time

from config import FL_HOST, STATE_PORT, CMD_PORT


class FLBridge:
    def __init__(self) -> None:
        self._state: dict = {}
        self._state_ts: float = 0.0
        self._lock = threading.Lock()

        self._cmd_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self._listen = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._listen.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._listen.bind(("0.0.0.0", STATE_PORT))
        self._listen.settimeout(0.5)

        self._running = True
        self._thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._thread.start()

    def _recv_loop(self) -> None:
        while self._running:
            try:
                data, _ = self._listen.recvfrom(65535)
                msg = json.loads(data.decode())
                if msg.get("type") == "state":
                    with self._lock:
                        self._state = msg.get("payload", {})
                        self._state_ts = time.time()
            except socket.timeout:
                continue
            except Exception:
                continue

    def send(self, action: str, **params) -> None:
        """Fire a command at FL Studio (no acknowledgement)."""
        payload = {"action": action, **params}
        data = json.dumps({"type": "command", "payload": payload}).encode()
        try:
            self._cmd_sock.sendto(data, (FL_HOST, CMD_PORT))
        except OSError:
            pass

    def state(self) -> dict:
        with self._lock:
            return dict(self._state)

    def connected(self) -> bool:
        """True if FL broadcast state within the last second."""
        with self._lock:
            return (time.time() - self._state_ts) < 1.0

    def close(self) -> None:
        self._running = False
        try:
            self._cmd_sock.close()
            self._listen.close()
        except OSError:
            pass
