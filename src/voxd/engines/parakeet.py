"""Parakeet TDT v3 via sherpa-onnx.

The default engine. It runs in-process, so there is no server to start, no port
to pick and no HTTP round trip. Measured on an i5-13600KF: 15x real time on
8 threads, and still 5x on only two cores — which is what makes a graphics card
optional rather than required.
"""

from __future__ import annotations

import array
import os
import time
from pathlib import Path

from . import Engine, EngineError, Transcript, clean


class ParakeetEngine(Engine):
    name = "parakeet"

    # sherpa-onnx wants the three graphs plus the token table.
    FILES = ("encoder.int8.onnx", "decoder.int8.onnx", "joiner.int8.onnx",
             "tokens.txt")

    def __init__(self, model_dir, **kw):
        super().__init__(model_dir, **kw)
        self._rec = None

    @classmethod
    def available(cls) -> tuple[bool, str]:
        try:
            import sherpa_onnx  # noqa: F401
            return True, ""
        except Exception as e:
            return False, f"sherpa-onnx is not installed ({e})"

    def _resolve(self) -> dict[str, Path]:
        d = Path(self.model_dir)
        found = {}
        for want in self.FILES:
            p = d / want
            if not p.exists():
                # Non-quantised builds drop the ".int8" infix.
                alt = d / want.replace(".int8", "")
                if alt.exists():
                    p = alt
                else:
                    raise EngineError(f"model file missing: {p}")
            found[want] = p
        return found

    def _thread_count(self) -> int:
        if self.threads > 0:
            return self.threads
        cpus = os.cpu_count() or 4
        # More than eight threads buys very little here and takes cores away
        # from whatever else the machine is doing.
        return max(2, min(8, cpus // 2))

    def load(self):
        if self.loaded:
            return
        ok, why = self.available()
        if not ok:
            raise EngineError(why)
        import sherpa_onnx

        f = self._resolve()
        t0 = time.time()
        self._rec = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=str(f["encoder.int8.onnx"]),
            decoder=str(f["decoder.int8.onnx"]),
            joiner=str(f["joiner.int8.onnx"]),
            tokens=str(f["tokens.txt"]),
            num_threads=self._thread_count(),
            model_type="nemo_transducer",
            feature_dim=128,
            debug=False,
        )
        self.load_seconds = time.time() - t0
        self.loaded = True

    def transcribe(self, pcm: bytes, sample_rate: int = 16000) -> Transcript:
        if not self.loaded:
            self.load()
        samples = array.array("h")
        samples.frombytes(pcm[: len(pcm) // 2 * 2])
        if not samples:
            return Transcript("", 0.0, 0.0, self.name, self.device)

        seconds = len(samples) / sample_rate
        t0 = time.time()
        stream = self._rec.create_stream()
        stream.accept_waveform(sample_rate, [s / 32768.0 for s in samples])
        self._rec.decode_stream(stream)
        elapsed = time.time() - t0
        return Transcript(clean(stream.result.text), seconds, elapsed,
                          self.name, self.device)

    def unload(self):
        self._rec = None
        self.loaded = False
