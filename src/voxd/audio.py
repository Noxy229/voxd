"""Audioaufnahme, plattformuebergreifend.

Bevorzugt wird `sounddevice` (PortAudio), weil es auf Windows, Linux und macOS
dasselbe tut. Fehlt PortAudio - auf Linux keine Seltenheit - wird auf
`pw-record` bzw. `parec` zurueckgefallen, die auf jedem PipeWire- oder
PulseAudio-System vorhanden sind.
"""

from __future__ import annotations

import array
import math
import shutil
import subprocess
import sys
import threading
import time

SAMPLE_RATE = 16000
CHANNELS = 1
BLOCK = 1600            # 100 ms

IS_WINDOWS = sys.platform == "win32"


# ------------------------------------------------------------------ Backend

def _have_sounddevice() -> bool:
    try:
        import sounddevice  # noqa: F401
        return True
    except Exception:
        return False


def _linux_tool() -> list[str] | None:
    if shutil.which("pw-record"):
        return ["pw-record"]
    if shutil.which("parec"):
        return ["parec"]
    return None


def backend_name() -> str:
    if _have_sounddevice():
        return "sounddevice"
    tool = _linux_tool()
    return tool[0] if tool else "keins"


# ------------------------------------------------------------------ Geraete

def list_input_devices() -> list[dict]:
    """[{id, label, default}] - id ist fuer das jeweilige Backend gueltig."""
    if _have_sounddevice():
        try:
            import sounddevice as sd
            default_in = sd.default.device[0] if sd.default.device else None
            out = []
            for i, d in enumerate(sd.query_devices()):
                if d.get("max_input_channels", 0) < 1:
                    continue
                out.append({"id": i, "label": d["name"].strip(),
                            "default": i == default_in})
            if out:
                return out
        except Exception:
            pass

    # PipeWire/PulseAudio-Quellen (Monitore weglassen - das sind Lautsprecher)
    if shutil.which("pactl"):
        try:
            txt = subprocess.run(["pactl", "list", "short", "sources"],
                                 capture_output=True, text=True, timeout=4).stdout
            default = subprocess.run(["pactl", "get-default-source"],
                                     capture_output=True, text=True, timeout=4).stdout.strip()
            out = []
            for ln in txt.splitlines():
                parts = ln.split("\t")
                if len(parts) < 2 or parts[1].endswith(".monitor"):
                    continue
                out.append({"id": parts[1], "label": _pretty(parts[1]),
                            "default": parts[1] == default})
            return out
        except Exception:
            pass
    return []


def _pretty(node: str) -> str:
    """Aus 'alsa_input.usb-Focusrite_Scarlett_Solo_USB_Y7U...-00.HiFi__Mic1__source'
    etwas machen, das ein Mensch wiedererkennt."""
    if ".pci-" in node or node.startswith("alsa_input.pci"):
        return "Onboard-Audio"
    s = node
    for pre in ("alsa_input.", "alsa_output."):
        s = s.removeprefix(pre)
    s = s.replace("usb-", "").replace("pci-", "")
    s = s.split("-00.")[0] if "-00." in node else s
    port = ""
    if "__" in node:
        bits = [b for b in node.split("__") if b and b not in ("source", "HiFi")]
        if bits:
            port = f" ({bits[-1]})"
    s = s.replace("_", " ").strip()
    # Seriennummern am Ende abschneiden - die helfen niemandem.
    words = [w for w in s.split() if not (len(w) > 8 and any(c.isdigit() for c in w))]
    return (" ".join(words) or s)[:48] + port


# ------------------------------------------------------------- Aufnahme

class Recorder:
    """Nimmt fortlaufend auf und sammelt 16-Bit-PCM bei 16 kHz mono."""

    def __init__(self, device=None, on_block=None):
        self.device = device
        self.on_block = on_block          # callback(bytes) je Block
        self.pcm = bytearray()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._proc = None
        self._stream = None
        self._thread = None
        self.error: str | None = None

    # -- Steuerung ----------------------------------------------------
    def start(self):
        self._stop.clear()
        with self._lock:
            self.pcm = bytearray()
        if _have_sounddevice():
            self._start_sd()
        else:
            self._thread = threading.Thread(target=self._run_cli, daemon=True)
            self._thread.start()

    def stop(self) -> bytes:
        self._stop.set()
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        if self._proc is not None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=2)
            except Exception:
                pass
            self._proc = None
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        with self._lock:
            return bytes(self.pcm)

    def snapshot(self) -> bytes:
        with self._lock:
            return bytes(self.pcm)

    @property
    def seconds(self) -> float:
        with self._lock:
            return len(self.pcm) / (SAMPLE_RATE * 2)

    # -- Backends -----------------------------------------------------
    def _feed(self, chunk: bytes):
        with self._lock:
            self.pcm.extend(chunk)
        if self.on_block:
            self.on_block(chunk)

    def _start_sd(self):
        import sounddevice as sd

        def cb(indata, _frames, _t, status):
            if self._stop.is_set():
                return
            self._feed(bytes(indata))

        try:
            self._stream = sd.RawInputStream(
                samplerate=SAMPLE_RATE, blocksize=BLOCK, device=self.device,
                channels=CHANNELS, dtype="int16", callback=cb)
            self._stream.start()
        except Exception as e:
            self.error = str(e)
            self._stream = None

    def _run_cli(self):
        tool = _linux_tool()
        if not tool:
            self.error = "Keine Aufnahmemöglichkeit gefunden (PortAudio, pw-record, parec)"
            return
        if tool[0] == "pw-record":
            cmd = ["pw-record", "--raw", "--rate", str(SAMPLE_RATE),
                   "--channels", str(CHANNELS), "--format", "s16",
                   "--latency", "20ms"]
            if self.device:
                cmd.append(f"--target={self.device}")
            cmd.append("-")
        else:
            cmd = ["parec", "--rate", str(SAMPLE_RATE), "--channels", str(CHANNELS),
                   "--format=s16le"]
            if self.device:
                cmd += ["-d", str(self.device)]
        try:
            self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                          stderr=subprocess.DEVNULL)
        except Exception as e:
            self.error = str(e)
            return
        while not self._stop.is_set():
            chunk = self._proc.stdout.read(BLOCK * 2)
            if not chunk:
                break
            self._feed(chunk)


# -------------------------------------------------------------- Auswertung

def peak(pcm: bytes) -> float:
    """Spitzenpegel 0..1."""
    if len(pcm) < 2:
        return 0.0
    a = array.array("h")
    a.frombytes(pcm[: len(pcm) // 2 * 2])
    return (max(map(abs, a)) / 32768.0) if a else 0.0


def rms_dbfs(pcm: bytes) -> float:
    if len(pcm) < 2:
        return -99.0
    a = array.array("h")
    a.frombytes(pcm[: len(pcm) // 2 * 2])
    if not a:
        return -99.0
    r = math.sqrt(sum(x * x for x in a) / len(a))
    return 20 * math.log10(r / 32768) if r > 0 else -99.0


class LevelMonitor:
    """Laufender Pegel fuer die Anzeige im Einrichtungsassistenten."""

    def __init__(self, device, on_level):
        self.rec = Recorder(device, on_block=lambda c: on_level(peak(c)))

    def start(self):
        self.rec.start()

    def stop(self):
        self.rec.stop()


def quick_test(device, callback, seconds: float = 5.0):
    """Kurz aufnehmen und beurteilen. `callback(ok: bool, text: str)`."""

    def run():
        rec = Recorder(device)
        rec.start()
        if rec.error:
            callback(False, f"Aufnahme nicht möglich: {rec.error}")
            return
        time.sleep(seconds)
        pcm = rec.stop()
        if rec.error:
            callback(False, f"Aufnahme nicht möglich: {rec.error}")
            return
        if len(pcm) < SAMPLE_RATE:
            callback(False, "Es kamen fast keine Daten an — dieses Gerät liefert nichts.")
            return
        pk, db = peak(pcm), rms_dbfs(pcm)
        if pk < 0.004:
            callback(False, "Kein Signal. Das Mikrofon ist stumm oder der Eingang "
                            "ist der falsche.")
        elif pk > 0.98:
            callback(False, f"Übersteuert (Spitze {pk:.2f}). Bitte die Eingangs"
                            f"verstärkung herunterdrehen.")
        elif db < -45:
            callback(False, f"Sehr leise ({db:.0f} dBFS). Erkennung wird darunter "
                            f"leiden — bitte lauter einstellen.")
        else:
            callback(True, f"Gut: {db:.0f} dBFS, Spitze {pk:.2f}. Das reicht.")

    threading.Thread(target=run, daemon=True).start()


def wav_bytes(pcm: bytes, rate: int = SAMPLE_RATE) -> bytes:
    n = len(pcm)
    h = (b"RIFF" + (36 + n).to_bytes(4, "little") + b"WAVEfmt "
         + (16).to_bytes(4, "little") + (1).to_bytes(2, "little")
         + (1).to_bytes(2, "little") + rate.to_bytes(4, "little")
         + (rate * 2).to_bytes(4, "little") + (2).to_bytes(2, "little")
         + (16).to_bytes(2, "little") + b"data" + n.to_bytes(4, "little"))
    return h + pcm


if __name__ == "__main__":
    print("Backend:", backend_name())
    for d in list_input_devices():
        print(("*" if d["default"] else " "), d["id"], "->", d["label"])
