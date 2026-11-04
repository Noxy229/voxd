"""Conservative offline spelling, using packaged frequency dictionaries."""
from __future__ import annotations

import re
import threading

from .redact import rule_based

# URLs, email addresses, inline code, paths and identifiers are opaque.
_TOKEN = re.compile(r"`[^`]*`|(?:https?://|www\.)\S+|\S*[@/\\_\d]\S*|[^\W\d_]+", re.UNICODE)


class SpellingEditor:
    def __init__(self, language: str = 'de'):
        self.language = language
        self._spell = None
        self._lock = threading.RLock()

    def load(self):
        with self._lock:
            if self._spell is None:
                from spellchecker import SpellChecker
                self._spell = SpellChecker(language=self.language, distance=1)

    def edit(self, text: str) -> str:
        self.load()
        count = 0
        def replace(match):
            nonlocal count
            word = match.group()
            count += 1
            # Capitalized words can be names/German nouns. Ambiguity stays intact.
            if count > 2000 or not word.isalpha() or not word.islower() or not 4 <= len(word) <= 24:
                return word
            if word in self._spell:
                return word
            candidates = self._spell.candidates(word) or set()
            if len(candidates) != 1:
                return word
            candidate = next(iter(candidates))
            return candidate if self._spell.word_frequency[candidate] >= 50 else word
        with self._lock:
            out = _TOKEN.sub(replace, text)
            first = _TOKEN.match(out.lstrip())
            return rule_based(out, capitalize=bool(first and first.group().isalpha()))

    def unload(self):
        with self._lock:
            self._spell = None
