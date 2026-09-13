"""The dictation state machine.

Deliberately free of Qt. The overlay subscribes through callbacks, so this can
be driven from a test without a display — which is how the pipeline gets
verified end to end.

    idle ──start──▶ recording ──stop──▶ transcribing ──▶ editing ──▶ inserting
      ▲                  │                                              │
      └──────── cancel ──┴──────────────────────────────────────────────┘
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import audio, catalog
from .config import Config, INJECT_CACHE, MODEL_DIR
from .engines import Engine, EngineError, build as build_engine
from .inject import Injector
from .redact import Redactor, RedactionUnavailable, rule_based, within_bounds

MAX_RECORD_SEC = 600
MIN_RECORD_SEC = 0.35
SILENCE_PEAK = 0.004        # below this the microphone is effectively dead


@dataclass
class Result:
    raw: str = ""
    final: str = ""
    note: str = ""              # "edited", "raw", or why the edit was rejected
    method: str | None = None   # which injection rung worked
    app: str = ""
    seconds: float = 0.0        # audio duration
    asr_seconds: float = 0.0
    edit_seconds: float = 0.0
    total_seconds: float = 0.0  # from stop to text in the field
    error: str = ""

    @property
    def ok(self) -> bool:
        return bool(self.final) and not self.error


@dataclass
class Callbacks:
    """Everything the UI needs. All fire on a worker thread."""
    on_state: callable = lambda state, text, level: None
    on_result: callable = lambda result: None
    on_log: callable = print


class Session:
    def __init__(self, cfg: Config, callbacks: Callbacks | None = None,
                 inject_enabled: bool = True):
        self.cfg = cfg
        # Tests drive the pipeline with recorded audio; typing the result into
        # whatever window happens to be focused would be a nasty surprise.
        self.inject_enabled = inject_enabled
        self.cb = callbacks or Callbacks()
        self.log = self.cb.on_log

        self.recording = False
        self.raw_mode = False
        self.last: Result | None = None

        self._recorder: audio.Recorder | None = None
        self._stop_time = 0.0
        self._engine: Engine | None = None
        self._engine_key: tuple | None = None
        self._lock = threading.Lock()

        self.injector = Injector(INJECT_CACHE,
                                 cfg.get("inject.order"),
                                 cfg.get("inject.focus_delay_ms", 40),
                                 log=self.log)
        self.redactor = self._build_redactor()

    # ------------------------------------------------------------ wiring
    def _build_redactor(self) -> Redactor:
        model_id = self.cfg.get("edit.model")
        model = catalog.get(model_id) if model_id else None
        path = None
        if model and model.files:
            path = MODEL_DIR / model.id / model.files[0].name
        return Redactor(path,
                        level=self.cfg.get("edit.level", "strong"),
                        device=self.cfg.get("edit.device", "gpu"),
                        port=self.cfg.get("edit.port", 8612),
                        idle_unload_sec=self.cfg.get("edit.idle_unload_sec", 90),
                        log=self.log)

    def _get_engine(self) -> Engine:
        """Build (and keep) the engine the config asks for."""
        model_id = self.cfg.get("asr.model")
        device = self.cfg.get("asr.device", "cpu")
        key = (model_id, device)
        with self._lock:
            if self._engine is not None and self._engine_key == key:
                return self._engine
            if self._engine is not None:
                self._engine.unload()
            model = catalog.get(model_id)
            if model is None:
                raise EngineError(f"unknown model in config: {model_id}")
            kw = dict(device=device, threads=self.cfg.get("asr.threads", 0),
                      language=self.cfg.get("asr.language", "auto"))
            if model.engine == "whispercpp":
                kw["model_file"] = model.files[0].name
            self._engine = build_engine(model.engine, MODEL_DIR / model.id, **kw)
            self._engine_key = key
            return self._engine

    def preload(self):
        """Warm the recogniser in the background so the first dictation is not
        slower than every later one."""
        def run():
            try:
                self._get_engine().load()
                self.log("recogniser ready")
            except Exception as e:
                self.log(f"recogniser could not be loaded: {e}")
        threading.Thread(target=run, daemon=True).start()

    # ---------------------------------------------------------- control
    def toggle(self, raw: bool = False):
        if self.recording:
            self.stop()
        else:
            self.start(raw)

    def start(self, raw: bool = False):
        if self.recording:
            return
        self.raw_mode = raw
        self.recording = True
        device = self.cfg.get("audio.device") or None
        self._recorder = audio.Recorder(device, on_block=self._on_block)
        self._recorder.start()
        if self._recorder.error:
            self.recording = False
            self.cb.on_state("problem", f"Cannot record: {self._recorder.error}", 0.0)
            return
        self.cb.on_state("listening", "", 0.0)
        # Loading the models while the user is still speaking is what keeps a
        # cold start from costing anything noticeable.
        threading.Thread(target=self._warm, daemon=True).start()

    def _warm(self):
        try:
            self._get_engine().load()
        except Exception as e:
            self.log(f"recogniser not ready: {e}")
        if not self.raw_mode and self.cfg.get("edit.enabled", True):
            self.redactor.ensure()

    def _on_block(self, chunk: bytes):
        if self.recording:
            self.cb.on_state("listening", "", audio.peak(chunk))

    def cancel(self):
        if not self.recording:
            return
        self.recording = False
        if self._recorder:
            self._recorder.stop()
            self._recorder = None
        self.cb.on_state("cancelled", "", 0.0)

    def stop(self):
        if not self.recording:
            return
        self.recording = False
        self._stop_time = time.time()
        pcm = self._recorder.stop() if self._recorder else b""
        self._recorder = None
        threading.Thread(target=self._finish, args=(pcm,), daemon=True).start()

    # ----------------------------------------------------------- pipeline
    def _finish(self, pcm: bytes):
        result = Result()
        result.seconds = len(pcm) / (audio.SAMPLE_RATE * 2)

        if result.seconds < MIN_RECORD_SEC:
            result.error = "too short"
            self.cb.on_state("problem", "Too short", 0.0)
            self.cb.on_result(result)
            return

        # Distinguish "said nothing" from "microphone is dead" — otherwise
        # people debug the recogniser when the real problem is a gain knob.
        if audio.peak(pcm) < SILENCE_PEAK:
            result.error = "no signal"
            self.cb.on_state("problem", "Microphone muted or gain too low", 0.0)
            self.cb.on_result(result)
            return

        self.cb.on_state("thinking", "", 0.0)
        try:
            transcript = self._get_engine().transcribe(pcm)
        except Exception as e:
            result.error = f"recognition failed: {e}"
            self.log(result.error)
            self.cb.on_state("problem", str(e)[:120], 0.0)
            self.cb.on_result(result)
            return

        result.raw = transcript.text
        result.asr_seconds = transcript.elapsed
        if not result.raw:
            result.error = "nothing recognised"
            self.cb.on_state("problem", "Nothing recognised", 0.0)
            self.cb.on_result(result)
            return

        result.final, result.note = result.raw, "raw"
        want_edit = not self.raw_mode and self.cfg.get("edit.enabled", True)
        if want_edit:
            self.cb.on_state("thinking", result.raw, 0.0)
            result.final, result.note, result.edit_seconds = self._edit(result.raw)

        self.last = result
        self.cb.on_state("done", result.final, 0.0)
        if not self.inject_enabled:
            result.method, result.app = "disabled", ""
            result.total_seconds = time.time() - self._stop_time
            self.last = result
            self.cb.on_result(result)
            return

        outcome = self.injector.inject(result.final)
        result.method, result.app = outcome.method, outcome.app
        result.total_seconds = time.time() - self._stop_time

        if not outcome.ok:
            # Never lose the text just because no rung could type it.
            self.injector.copy_to_clipboard(result.final)
            result.error = outcome.error
            self.cb.on_state("problem", "Could not type — text is in the clipboard", 0.0)

        self.log(f"done in {result.total_seconds:.2f}s "
                 f"[{transcript.engine}/{result.note}/{result.method}] "
                 f"{result.final[:60]!r}")
        self.cb.on_result(result)

    def _edit(self, raw: str) -> tuple[str, str, float]:
        t0 = time.time()
        if not self.redactor.enabled:
            # No model configured: do the little that can be done honestly,
            # and say so rather than implying corrections were applied.
            return rule_based(raw), "punctuation only", time.time() - t0
        try:
            candidate = self.redactor.edit(raw)
        except RedactionUnavailable as e:
            self.log(f"editing unavailable: {e}")
            return raw, "raw (editor unavailable)", time.time() - t0
        except Exception as e:
            self.log(f"editing failed: {e}")
            return raw, "raw (editing failed)", time.time() - t0

        ok, why = within_bounds(raw, candidate,
                                self.cfg.get("edit.max_growth", 2.5),
                                self.cfg.get("edit.min_shrink", 0.3))
        if not ok:
            self.log(f"edit rejected: {why}")
            return raw, f"raw ({why})", time.time() - t0
        return candidate, "edited", time.time() - t0

    # ------------------------------------------------------------- misc
    def insert_last_raw(self):
        """Re-insert the unedited version of the last dictation."""
        if self.last and self.last.raw:
            self.injector.inject(self.last.raw)

    def release(self):
        """Drop everything from memory — models included."""
        with self._lock:
            if self._engine is not None:
                self._engine.unload()
        self.redactor.unload()

    def status(self) -> dict:
        return {
            "recording": self.recording,
            "engine": self.cfg.get("asr.model"),
            "engine_loaded": bool(self._engine and self._engine.loaded),
            "editing": self.cfg.get("edit.level") if self.redactor.enabled
                       else f"off ({self.redactor.why_unavailable()})",
            "last": (self.last.final[:80] if self.last else ""),
        }
