"""The editing pass: turning what was said into what was meant.

The recogniser writes down "no, Wednesday" because that is what it heard. This
stage recognises that as an instruction the speaker gave to themselves, applies
it, and removes it.

Runs against a local llama.cpp server, started on demand and unloaded again
after an idle period so nothing sits in memory between dictations.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_PORT = 8612

LEVEL_RULES = {
    "minimal":
        "3. Change NOTHING else. Wording, sentence structure and register stay "
        "exactly as spoken.",
    "moderate":
        "3. Remove filler words (uh, um, like, you know, I mean, sort of, "
        "basically). Leave wording and register otherwise untouched.",
    "strong":
        "3. Remove filler words (uh, um, like, you know, I mean, sort of, "
        "basically) and smooth the result into clean written prose: fix "
        "grammar, order the sentence properly, turn spoken register into "
        "written register. NEVER change the meaning, never invent anything, "
        "never drop information.",
}

SYSTEM_PROMPT = """You are a dictation editor. The input is the raw, unedited
transcript of someone speaking. Your output is the finished text and nothing
else - no greeting, no commentary, no quotation marks around it.

RULE ZERO, ABOVE ALL OTHERS: NEVER TRANSLATE. The output must be in exactly the
same language as the input. German input produces German output. French input
produces French output. These instructions are written in English; that says
nothing about what language you should answer in. If you find yourself writing
in a different language than the input, you have made a serious mistake.

1. APPLY SELF-CORRECTIONS. The speaker corrects themselves mid-sentence. Carry
   out the correction and delete the instruction itself. Typical forms, in any
   language: "no, scratch that", "delete that", "uh, I mean", "not X but Y",
   "let me start over", "put ... instead", "hold on, actually",
   "nee, das raus", "streich das", "ich meine", "Moment, anders".
2. APPLY SPOKEN PUNCTUATION COMMANDS in whatever language they were spoken:
   period / full stop / Punkt, comma / Komma, question mark / Fragezeichen,
   colon / Doppelpunkt, new line / neue Zeile, new paragraph / neuer Absatz,
   open quote / in Anfuehrungszeichen, capitalise / gross schreiben.
{level_rule}
4. If the input has no discernible content, return it unchanged.

Examples. Note that each output is in the same language as its input:

Input: please write uh that the meeting is on tuesday no wednesday wednesday at three period
Output: The meeting is on Wednesday at three.

Input: schreib bitte aeh dass das meeting am dienstag stattfindet nee mittwoch mittwoch um drei punkt
Output: Das Meeting findet am Mittwoch um drei Uhr statt.

Input: so i wanted to say the bug is in the parser no wait not the parser the lexer and it is in the escape sequences period
Output: The bug is not in the parser but in the lexer, in the escape sequences.

Input: also ich wollte sagen dass der bug im parser liegt nee quatsch nicht im parser im lexer und zwar bei den escape sequenzen punkt
Output: Der Bug liegt nicht im Parser, sondern im Lexer, und zwar bei den Escape-Sequenzen.

Input: hey could you send me the file question mark new line thanks
Output: Hey, could you send me the file?
Thanks

Input: der server laeuft auf port achttausend moment anders auf port dreitausend punkt
Output: Der Server laeuft auf Port 3000."""


def build_prompt(level: str) -> str:
    rule = LEVEL_RULES.get(level, LEVEL_RULES["strong"])
    return SYSTEM_PROMPT.format(level_rule=rule)


class RedactionUnavailable(RuntimeError):
    pass


# ------------------------------------------------------------- rule fallback

_FILLER = re.compile(r"\b(uh+|um+|erm|ähm?|öh)\b[,]?\s*", re.IGNORECASE)


def rule_based(text: str) -> str:
    """Used when no language model is configured.

    Deliberately timid: strip fillers, tidy spacing, capitalise sentences. It
    cannot do self-corrections — claiming otherwise would be worse than doing
    nothing, because the user would trust an edit that never happened.
    """
    out = _FILLER.sub("", text).strip()
    out = re.sub(r"\s+([,.!?;:])", r"\1", out)
    out = re.sub(r"\s{2,}", " ", out)
    if out and out[0].islower():
        out = out[0].upper() + out[1:]
    return out


# ----------------------------------------------------------------- the model

class Redactor:
    """Owns the llama.cpp server: starts it on demand, unloads it when idle."""

    def __init__(self, model_path: Path | None, level: str = "strong",
                 device: str = "gpu", port: int = DEFAULT_PORT,
                 idle_unload_sec: int = 90, threads: int = 0,
                 cpu_affinity: str = "", log=print):
        self.model_path = Path(model_path) if model_path else None
        self.level = level
        self.device = device
        self.port = port
        self.idle_unload_sec = idle_unload_sec
        self.threads = threads
        self.cpu_affinity = cpu_affinity
        self.log = log
        self._proc = None
        self._lock = threading.RLock()
        self._last_used = 0.0
        self._watch = threading.Thread(target=self._idle_watch, daemon=True)
        self._watch.start()

    # -- availability ---------------------------------------------------
    @property
    def enabled(self) -> bool:
        return bool(self.model_path and self.model_path.exists()
                    and shutil.which("llama-server"))

    def why_unavailable(self) -> str:
        if not self.model_path:
            return "no editing model configured"
        if not self.model_path.exists():
            return f"model file missing: {self.model_path}"
        if not shutil.which("llama-server"):
            return "llama-server not found on PATH"
        return ""

    # -- server ---------------------------------------------------------
    def _argv(self) -> list[str]:
        argv = ["llama-server", "-m", str(self.model_path),
                "--host", "127.0.0.1", "--port", str(self.port),
                "-c", "8192", "--no-webui", "--jinja"]
        if self.device == "gpu":
            argv += ["-ngl", "99"]
        else:
            argv += ["-ngl", "0", "-t", str(self.threads or 8)]
        if self.cpu_affinity and shutil.which("taskset"):
            argv = ["taskset", "-c", self.cpu_affinity] + argv
        return argv

    def _healthy(self) -> bool:
        try:
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{self.port}/health", timeout=1) as r:
                return b'"ok"' in r.read()
        except Exception:
            return False

    def ensure(self, timeout: float = 180) -> bool:
        with self._lock:
            self._last_used = time.time()
            if self._proc and self._proc.poll() is None and self._healthy():
                return True
            if not self.enabled:
                return False
            if self._proc and self._proc.poll() is not None:
                self._proc = None
            if self._proc is None:
                self.log(f"starting editing model ({self.device})")
                self._proc = subprocess.Popen(
                    self._argv(), stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, start_new_session=True)
            deadline = time.time() + timeout
            while time.time() < deadline:
                if self._proc.poll() is not None:
                    self.log("editing model exited while starting")
                    self._proc = None
                    return False
                if self._healthy():
                    return True
                time.sleep(0.2)
            return False

    def unload(self):
        with self._lock:
            if self._proc is not None:
                self.log("unloading editing model")
                try:
                    self._proc.terminate()
                    self._proc.wait(timeout=4)
                except Exception:
                    try:
                        self._proc.kill()
                    except Exception:
                        pass
                self._proc = None

    def touch(self):
        self._last_used = time.time()

    def _idle_watch(self):
        while True:
            time.sleep(5)
            with self._lock:
                if (self._proc is not None
                        and time.time() - self._last_used > self.idle_unload_sec):
                    self.unload()

    # -- the actual edit -------------------------------------------------
    def edit(self, raw: str, timeout: float = 180) -> str:
        if not raw.strip():
            return raw
        if not self.ensure():
            raise RedactionUnavailable(self.why_unavailable()
                                       or "editing model did not start")
        payload = {
            "messages": [{"role": "system", "content": build_prompt(self.level)},
                         {"role": "user", "content": raw}],
            "temperature": 0.2,
            "top_p": 0.9,
            "max_tokens": 2048,
            "stream": False,
            # Qwen3 base models support a thinking mode; unwanted here.
            "chat_template_kwargs": {"enable_thinking": False},
        }
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/v1/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read())
        out = data["choices"][0]["message"]["content"]
        out = re.sub(r"<think>.*?</think>", "", out, flags=re.S)
        self.touch()
        return out.strip().strip('"').strip()


# ------------------------------------------------------------------ guardrail

def within_bounds(raw: str, edited: str, max_growth: float = 2.5,
                  min_shrink: float = 0.3) -> tuple[bool, str]:
    """Reject an edit that drifted too far in length from what was said.

    This is the safety net that keeps the language model from quietly putting
    words in the user's mouth. Returns (ok, reason).
    """
    if not edited.strip():
        return False, "editing returned nothing"
    ratio = len(edited) / max(1, len(raw))
    if ratio > max_growth:
        return False, f"edit grew {ratio:.1f}x"
    if ratio < min_shrink:
        return False, f"edit shrank to {ratio:.1f}x"
    return True, ""
