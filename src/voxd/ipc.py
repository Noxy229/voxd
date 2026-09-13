"""Talking to the running daemon.

A Unix socket on Linux and macOS, a TCP socket bound to loopback on Windows,
which has no Unix sockets in a form Python exposes everywhere. Same line
protocol either way: send a command, read one reply, close.
"""

from __future__ import annotations

import json
import socket
import sys
import threading
from pathlib import Path

from .config import runtime_dir

IS_WINDOWS = sys.platform == "win32"
PORT_FILE_NAME = "daemon.port"
SOCKET_NAME = "daemon.sock"

COMMANDS = ("toggle", "raw-toggle", "start", "stop", "cancel", "insert-raw",
            "release", "status", "reload", "setup", "quit")


def socket_path() -> Path:
    return runtime_dir() / SOCKET_NAME


def port_path() -> Path:
    return runtime_dir() / PORT_FILE_NAME


# ------------------------------------------------------------------- server

class Server:
    def __init__(self, handlers: dict, log=print):
        self.handlers = handlers
        self.log = log
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self):
        runtime_dir().mkdir(parents=True, exist_ok=True)
        if IS_WINDOWS:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock.bind(("127.0.0.1", 0))
            port_path().write_text(str(self._sock.getsockname()[1]), "utf-8")
        else:
            p = socket_path()
            p.unlink(missing_ok=True)
            self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._sock.bind(str(p))
            p.chmod(0o600)
        self._sock.listen(8)
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        self.log(f"listening on {port_path() if IS_WINDOWS else socket_path()}")

    def _serve(self):
        while not self._stop.is_set():
            try:
                conn, _ = self._sock.accept()
            except OSError:
                break
            try:
                cmd = conn.recv(512).decode("utf-8", "replace").strip()
                handler = self.handlers.get(cmd)
                if handler is None:
                    reply = f"unknown command: {cmd}"
                else:
                    out = handler()
                    reply = (json.dumps(out, ensure_ascii=False)
                             if isinstance(out, (dict, list)) else str(out or "ok"))
                conn.sendall(reply.encode("utf-8"))
            except Exception as e:
                try:
                    conn.sendall(f"error: {e}".encode())
                except Exception:
                    pass
            finally:
                conn.close()

    def stop(self):
        self._stop.set()
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
        if not IS_WINDOWS:
            socket_path().unlink(missing_ok=True)
        else:
            port_path().unlink(missing_ok=True)


# ------------------------------------------------------------------- client

def send(command: str, timeout: float = 15) -> str:
    """Send one command. Raises ConnectionError when no daemon is listening."""
    s = socket.socket(socket.AF_INET if IS_WINDOWS else socket.AF_UNIX,
                      socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        if IS_WINDOWS:
            pf = port_path()
            if not pf.exists():
                raise ConnectionError("voxd is not running")
            s.connect(("127.0.0.1", int(pf.read_text().strip())))
        else:
            sp = socket_path()
            if not sp.exists():
                raise ConnectionError("voxd is not running")
            s.connect(str(sp))
        s.sendall(command.encode("utf-8"))
        return s.recv(65536).decode("utf-8", "replace")
    except (FileNotFoundError, ConnectionRefusedError) as e:
        raise ConnectionError("voxd is not running") from e
    finally:
        s.close()


def daemon_running() -> bool:
    try:
        send("status", timeout=3)
        return True
    except Exception:
        return False
