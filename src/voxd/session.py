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
from dataclasses import dataclass

from . import audio, catalog
from .config import INJECT_CACHE, MODEL_DIR, Config
from .engines import Engine, EngineError
from .engines import build as build_engine
from .inject import Injector
from .redact import (
    RedactionUnavailable,
    Redactor,
    rule_based,
    spoken_punctuation,
    within_bounds,
)
from .spelling import SpellingEditor

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
        self.suspended = False
        self.raw_mode = False
        self.last: Result | None = None

        self._recorder: audio.Recorder | None = None
        self._stop_time = 0.0
        self._engine: Engine | None = None
        self._engine_key: tuple | None = None
        self._lock = threading.RLock()
        self._control = threading.RLock()
        self._busy = False
        self._closed = False
        self._workers = set()

        self.injector = Injector(INJECT_CACHE,
                                 cfg.get("inject.order"),
                                 cfg.get("inject.focus_delay_ms", 40),
                                 log=self.log)
        self.redactor = self._build_redactor()
        self.spelling = SpellingEditor(cfg.get("edit.language", "de"))

    # ------------------------------------------------------------ wiring
    def _build_redactor(self) -> Redactor:
        model_id = self.cfg.get("edit.model") if self.cfg.get("edit.mode") == "llm" else None
        model = catalog.get(model_id) if model_id else None
        path = None
        if model and model.files:
            path = MODEL_DIR / model.id / model.files[0].name
        return Redactor(path,
                        level=self.cfg.get("edit.level", "strong"),
                        device=self.cfg.get("edit.device", "cpu"),
                        port=self.cfg.get("edit.port", 8612),
                        idle_unload_sec=self.cfg.get("edit.idle_unload_sec", 0),
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
                with self._lock:
                    if self._closed:
                        return
                    self._get_engine().load()
                    if self.cfg.get("edit.enabled", True):
                        if self.cfg.get("edit.mode") == "spelling":
                            self.spelling.load()
                        elif not self.redactor.ensure():
                            self.log("recogniser ready; editing model unavailable")
                            return
                self.log("models ready")
            except Exception as e:
                self.log(f"recogniser could not be loaded: {e}")
        self._spawn(run)

    # ---------------------------------------------------------- control
    def toggle(self, raw: bool = False):
        with self._control:
            return self._toggle(raw)

    def _toggle(self, raw: bool = False):
        if self.recording:
            self.stop()
        else:
            self.start(raw)

    def start(self, raw: bool = False):
        with self._control:
            return self._start(raw)

    def _start(self, raw: bool = False):
        if self.recording or self._busy or self._closed or self.suspended:
            return
        self.raw_mode = raw
        self.recording = True
        device = self.cfg.get("audio.device")
        if device == "":
            device = None
        self._recorder = audio.Recorder(device, on_block=self._on_block)
        self._recorder.start()
        if self._recorder.error:
            self.recording = False
            self._recorder.stop()
            self.cb.on_state("problem", f"Cannot record: {self._recorder.error}", 0.0)
            return
        self.cb.on_state("listening", "", 0.0)
        # Loading the models while the user is still speaking is what keeps a
        # cold start from costing anything noticeable.
        self._spawn(self._warm)

    def _warm(self):
        try:
            with self._lock:
                if self._closed:
                    return
                self._get_engine().load()
        except Exception as e:
            self.log(f"recogniser not ready: {e}")
        with self._lock:
            if not self._closed and not self.raw_mode and self.cfg.get("edit.enabled", True):
                if self.cfg.get("edit.mode") == "spelling":
                    self.spelling.load()
                else:
                    self.redactor.ensure()

    def _on_block(self, chunk: bytes):
        if self.recording:
            self.cb.on_state("listening", "", audio.peak(chunk))

    def cancel(self):
        with self._control:
            return self._cancel()

    def _cancel(self):
        if not self.recording:
            return
        self.recording = False
        if self._recorder:
            self._recorder.stop()
            self._recorder = None
        self.cb.on_state("cancelled", "", 0.0)

    def stop(self):
        with self._control:
            return self._stop()

    def _stop(self):
        if not self.recording:
            return
        self.recording = False
        self._stop_time = time.time()
        pcm = self._recorder.stop() if self._recorder else b""
        self._recorder = None
        self._busy = True
        raw_mode = self.raw_mode
        def finish():
            try:
                with self._lock:
                    self._finish(pcm, raw_mode)
            except Exception as e:
                self.log(f"dictation failed: {type(e).__name__}")
                self.cb.on_state("problem", "Dictation failed", 0.0)
            finally:
                with self._control:
                    self._busy = False
        self._spawn(finish)

    # ----------------------------------------------------------- pipeline
    def _finish(self, pcm: bytes, raw_mode: bool = False):
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
            with self._lock:
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
        want_edit = not raw_mode and self.cfg.get("edit.enabled", True)
        if want_edit:
            self.cb.on_state("thinking", result.raw, 0.0)
            result.final, result.note, result.edit_seconds = self._edit(result.raw)

        self.last = result
        if self._closed:
            return
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
                 f"[{transcript.engine}/{result.note}/{result.method}]")
        self.cb.on_result(result)

    def _edit(self, raw: str) -> tuple[str, str, float]:
        raw = spoken_punctuation(raw)
        t0 = time.time()
        if self.cfg.get("edit.mode") == "spelling":
            try:
                return self.spelling.edit(raw), "dictionary + rules", time.time() - t0
            except Exception as e:
                self.log(f"spelling unavailable: {type(e).__name__}")
                return rule_based(raw), "punctuation only", time.time() - t0
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

    def _spawn(self, target):
        def run():
            try:
                target()
            finally:
                with self._control:
                    self._workers.discard(threading.current_thread())
        worker = threading.Thread(target=run, daemon=True)
        with self._control:
            if self._closed:
                return
            self._workers.add(worker)
            worker.start()

    def reconfigure(self, cfg):
        with self._control:
            if self.recording or self._busy or self._workers:
                return False
            self.release()
            self.redactor.close()
            self.spelling.unload()
            self.spelling = SpellingEditor(cfg.get("edit.language", "de"))
            self.cfg = cfg
            self.redactor = self._build_redactor()
            self.injector = Injector(INJECT_CACHE, cfg.get("inject.order"),
                                     cfg.get("inject.focus_delay_ms", 40), log=self.log)
        self.preload()
        return True

    def close(self):
        with self._control:
            self._closed = True
            self.cancel()
            workers = list(self._workers)
        for worker in workers:
            worker.join()
        self.release()
        self.redactor.close()

    def release(self):
        """Drop everything from memory — models included."""
        with self._control:
            if self.recording or self._busy or self._workers:
                return False
        with self._lock:
            if self._engine is not None:
                self._engine.unload()
            self.redactor.unload()
            self.spelling.unload()
        return True

    def status(self) -> dict:
        return {
            "recording": self.recording,
            "engine": self.cfg.get("asr.model"),
            "engine_loaded": bool(self._engine and self._engine.loaded),
            "editing": "dictionary + rules" if self.cfg.get("edit.mode") == "spelling"
                       else self.cfg.get("edit.level") if self.redactor.enabled
                       else f"off ({self.redactor.why_unavailable()})",
            "busy": self._busy,
        }
