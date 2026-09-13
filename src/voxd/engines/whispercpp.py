"""Whisper via whisper.cpp's HTTP server.

The optional engine, for people who want Whisper's accuracy and have a graphics
card to run it on. It needs the `whisper-server` binary on PATH.

Note on language: setting `language` to "auto" costs an extra encoder pass —
measured at 1317 ms versus 650 ms for a fixed language on the same audio and
hardware. Parakeet is multilingual without that penalty, which is one more
reason it is the default.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from . import Engine, EngineError, Transcript, clean

DEFAULT_PORT = 8611


def wav_bytes(pcm: bytes, rate: int = 16000) -> bytes:
    n = len(pcm)
    return (b"RIFF" + (36 + n).to_bytes(4, "little") + b"WAVEfmt "
            + (16).to_bytes(4, "little") + (1).to_bytes(2, "little")
            + (1).to_bytes(2, "little") + rate.to_bytes(4, "little")
            + (rate * 2).to_bytes(4, "little") + (2).to_bytes(2, "little")
            + (16).to_bytes(2, "little") + b"data" + n.to_bytes(4, "little")
            + pcm)


class WhisperCppEngine(Engine):
    name = "whispercpp"

    def __init__(self, model_dir, model_file: str = "ggml-large-v3-turbo.bin",
                 vad_file: str = "ggml-silero-v6.2.0.bin",
                 port: int = DEFAULT_PORT, **kw):
        super().__init__(model_dir, **kw)
        self.model_file = model_file
        self.vad_file = vad_file
        self.port = port
        self._proc = None

    @classmethod
    def available(cls) -> tuple[bool, str]:
        if shutil.which("whisper-server"):
            return True, ""
        return False, ("whisper-server not found on PATH — install whisper.cpp "
                       "or use the Parakeet engine")

    # -- server lifecycle ----------------------------------------------
    def _argv(self) -> list[str]:
        d = Path(self.model_dir)
        model = d / self.model_file
        if not model.exists():
            raise EngineError(f"model file missing: {model}")
        argv = ["whisper-server", "-m", str(model),
                "--host", "127.0.0.1", "--port", str(self.port),
                "-t", str(self.threads or 8),
                "-l", self.language, "-nt", "-sns"]
        vad = d / self.vad_file
        if vad.exists():
            argv += ["--vad", "-vm", str(vad)]
        if self.device != "gpu":
            argv.append("-ng")
        return argv

    def _wait_ready(self, timeout: float = 90) -> bool:
        deadline = time.time() + timeout
        url = f"http://127.0.0.1:{self.port}/"
        while time.time() < deadline:
            if self._proc and self._proc.poll() is not None:
                return False            # server died while starting
            try:
                urllib.request.urlopen(url, timeout=0.5)
                return True
            except urllib.error.HTTPError:
                return True             # answering at all means it is up
            except Exception:
                time.sleep(0.15)
        return False

    def load(self):
        if self.loaded:
            return
        ok, why = self.available()
        if not ok:
            raise EngineError(why)
        t0 = time.time()
        self._proc = subprocess.Popen(self._argv(), stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL,
                                      start_new_session=True)
        if not self._wait_ready():
            self.unload()
            raise EngineError("whisper-server did not come up")
        self.load_seconds = time.time() - t0
        self.loaded = True

    def unload(self):
        if self._proc is not None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=4)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None
        self.loaded = False

    # -- inference ------------------------------------------------------
    def transcribe(self, pcm: bytes, sample_rate: int = 16000) -> Transcript:
        if not self.loaded:
            self.load()
        seconds = len(pcm) / (sample_rate * 2)
        boundary = "----voxd" + uuid.uuid4().hex
        parts = []
        for key, val in (("temperature", "0.0"), ("response_format", "json"),
                         ("language", self.language)):
            parts.append(
                f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"'
                f"\r\n\r\n{val}\r\n".encode())
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
            f'filename="a.wav"\r\nContent-Type: audio/wav\r\n\r\n'.encode()
            + wav_bytes(pcm, sample_rate) + b"\r\n")
        parts.append(f"--{boundary}--\r\n".encode())

        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/inference", data=b"".join(parts),
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                payload = json.loads(r.read())
        except Exception as e:
            raise EngineError(f"whisper-server request failed: {e}") from e
        elapsed = time.time() - t0
        return Transcript(clean(payload.get("text", "")), seconds, elapsed,
                          self.name, self.device)
