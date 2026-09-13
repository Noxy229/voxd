"""Speech recognition engines behind one interface.

Two very different things sit behind `Engine`: sherpa-onnx runs in-process as a
library, whisper.cpp runs as a subprocess with an HTTP API. Everything above
this layer only sees `load()`, `transcribe()` and `unload()`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Recognisers occasionally emit a stock phrase when handed silence or noise —
# subtitle credits are the classic case. Nobody dictates these.
GHOST = re.compile(
    r"^\W*("
    r"subtitles?\s+(by|for)|subs?\s+by|amara\.org|transcri(pt|bed)\s+by|"
    r"thanks?\s+for\s+watching|untertitel(ung)?\s+(von|des|im auftrag)|"
    r"untertitel\s+der|copyright\s|www\.|©\s"
    r")",
    re.IGNORECASE,
)

BRACKETED = re.compile(
    r"[\[(]\s*(music|applause|laughter|silence|inaudible|noise|"
    r"musik|applaus|lachen|stille)\s*[\])]", re.IGNORECASE)


def clean(text: str) -> str:
    """Strip the artefacts every recogniser produces, regardless of engine."""
    lines = [ln.strip() for ln in text.replace("\r", "").split("\n")]
    kept = [ln for ln in lines if ln and not GHOST.match(ln)]
    out = " ".join(kept)
    out = BRACKETED.sub("", out)
    return re.sub(r"\s+", " ", out).strip()


@dataclass
class Transcript:
    text: str
    seconds: float = 0.0            # duration of the audio
    elapsed: float = 0.0            # wall time spent recognising
    engine: str = ""
    device: str = ""

    @property
    def realtime_factor(self) -> float:
        return (self.seconds / self.elapsed) if self.elapsed > 0 else 0.0


class EngineError(RuntimeError):
    pass


class Engine:
    """Interface. `load()` may be slow; `transcribe()` must be safe to call
    repeatedly from one background thread."""

    name = "engine"

    def __init__(self, model_dir, device: str = "cpu", threads: int = 0,
                 language: str = "auto"):
        self.model_dir = model_dir
        self.device = device
        self.threads = threads
        self.language = language
        self.loaded = False

    def load(self):
        raise NotImplementedError

    def transcribe(self, pcm: bytes, sample_rate: int = 16000) -> Transcript:
        raise NotImplementedError

    def unload(self):
        self.loaded = False

    @classmethod
    def available(cls) -> tuple[bool, str]:
        """(usable, reason if not)."""
        return True, ""


def build(engine_name: str, model_dir, **kw) -> Engine:
    if engine_name == "parakeet":
        from .parakeet import ParakeetEngine
        return ParakeetEngine(model_dir, **kw)
    if engine_name == "whispercpp":
        from .whispercpp import WhisperCppEngine
        return WhisperCppEngine(model_dir, **kw)
    raise EngineError(f"unknown engine: {engine_name}")
