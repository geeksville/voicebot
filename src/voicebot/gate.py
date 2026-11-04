"""The utterance gate: which finished utterances are worth answering.

The plan's rule (``docs/plans/audioin.md``, Q3): answer only when a finished
utterance has at least a few *content* words — pure filler ("uh", "hmm", …) and
very short fragments are logged and dropped — and never fire twice on the same
thing inside a debounce window. Pure logic: no I/O, no dependencies.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass

#: Words that carry no content on their own. An utterance made only of these is
#: not worth answering, however many of them there are.
FILLER = frozenset(
    {
        "uh",
        "um",
        "uhm",
        "uhhuh",
        "hmm",
        "hm",
        "mm",
        "mhm",
        "mmm",
        "er",
        "erm",
        "ah",
        "eh",
        "oh",
        "ooh",
        "aha",
        "ha",
        "haha",
        "yeah",
        "yep",
        "yup",
        "nah",
        "ok",
        "okay",
        "so",
        "well",
        "like",
        "right",
        "hey",
    }
)

_WORD_RE = re.compile(r"[a-z0-9][a-z0-9']*")


def content_words(text: str) -> list[str]:
    """The content-bearing words in *text* (lowercased, filler removed)."""
    return [w for w in _WORD_RE.findall(text.lower()) if w not in FILLER]


@dataclass(frozen=True)
class Decision:
    """Whether to answer an utterance, and — if not — why."""

    keep: bool
    reason: str  # "keep" | "too_short" | "too_brief" | "repeat"


class UtteranceGate:
    """Word/short-utterance thresholds plus a repeat-debounce window.

    ``min_words`` counts *content* words (filler stripped). ``min_duration_s``
    is only applied when a duration is actually known (the STT engine supplies
    one; the ``--fake`` replay does not). ``debounce_s`` suppresses an
    utterance identical to the previous one inside that many seconds.
    """

    def __init__(
        self,
        *,
        min_words: int = 3,
        min_duration_s: float = 0.0,
        debounce_s: float = 0.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._min_words = max(0, int(min_words))
        self._min_duration_s = max(0.0, float(min_duration_s))
        self._debounce_s = max(0.0, float(debounce_s))
        self._clock = clock
        self._last: str | None = None
        self._last_at = 0.0

    def decide(self, text: str, *, duration_s: float | None = None) -> Decision:
        """Return whether *text* should be answered."""
        words = content_words(text)
        if len(words) < self._min_words:
            return Decision(False, "too_short")
        if duration_s is not None and self._min_duration_s and duration_s < self._min_duration_s:
            return Decision(False, "too_brief")
        now = self._clock()
        normalized = " ".join(words)
        if (
            self._debounce_s
            and self._last is not None
            and normalized == self._last
            and (now - self._last_at) < self._debounce_s
        ):
            # Keep suppressing repeats until the window has fully elapsed.
            self._last_at = now
            return Decision(False, "repeat")
        self._last = normalized
        self._last_at = now
        return Decision(True, "keep")
