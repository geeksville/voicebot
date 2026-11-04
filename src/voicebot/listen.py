"""The audio-in loop: utterances -> gate -> responder -> emit(log).

Framework-free and hardware-free: it drives a :class:`~voicebot.audio.
TranscriptSource` through an :class:`~voicebot.gate.UtteranceGate` and an
injected :class:`~voicebot.responder.Responder`, calling ``respond`` on a
**worker thread** so the audio side never blocks on the LLM round-trip
(plan Q5: one item in flight; when the worker is busy the *older* pending
utterance is dropped in favour of the newest). ``inline=True`` runs it
synchronously — tests use that for deterministic ordering.

See ``docs/plans/audioin.md``.
"""

from __future__ import annotations

import json
import logging
import queue
import threading
from collections.abc import Callable
from dataclasses import dataclass

from .audio import Utterance
from .gate import UtteranceGate
from .responder import Responder

log = logging.getLogger(__name__)

KIND_HEARD = "heard"
KIND_REPLY = "reply"
KIND_SKIP = "skip"

_CLOSED = object()


@dataclass(frozen=True)
class ListenEvent:
    """One thing that happened while listening — the unit we log/emit."""

    kind: str  # KIND_HEARD | KIND_REPLY | KIND_SKIP
    text: str = ""  # the utterance as heard
    reply: str = ""  # the quip (kind == KIND_REPLY)
    reason: str = ""  # skip reason (kind == KIND_SKIP); "keep" otherwise
    model: str = ""

    def as_dict(self) -> dict[str, str]:
        """The ``--json`` shape."""
        return {
            "event": self.kind,
            "heard": self.text,
            "reply": self.reply,
            "reason": self.reason,
            "model": self.model,
        }


Emitter = Callable[[ListenEvent], None]


def log_emitter(event: ListenEvent) -> None:
    """The default emitter: ``HEARD`` / ``REPLY`` / ``SKIP`` log lines."""
    if event.kind == KIND_REPLY:
        log.info("REPLY: %s", event.reply)
    elif event.kind == KIND_SKIP:
        log.info("SKIP(%s): %s", event.reason, event.text)
    else:
        log.info("HEARD: %s", event.text)


def json_emitter(event: ListenEvent) -> None:
    """Emit each event as one JSON object on stdout."""
    print(json.dumps(event.as_dict()), flush=True)


class Listener:
    """Drive a :class:`TranscriptSource` through the gate and the responder.

    The responder call (an HTTP round-trip) runs on a worker thread so the
    audio side never blocks on the network; the queue holds one item in flight
    plus a small backlog, and drops the oldest pending item if it ever fills.
    ``inline=True`` runs it synchronously on the calling thread instead — used
    for deterministic replay (``listen --fake``) and by tests.
    """

    def __init__(
        self,
        responder: Responder,
        gate: UtteranceGate,
        *,
        emit: Emitter | None = None,
        max_queued: int = 2,
        inline: bool = False,
    ) -> None:
        self._responder = responder
        self._gate = gate
        self._emit = emit or log_emitter
        self._inline = inline
        self._queue: queue.Queue = queue.Queue(maxsize=max(1, int(max_queued)))
        self._thread: threading.Thread | None = None
        self._closed = False

    # -- lifecycle ---------------------------------------------------------

    def _start(self) -> None:
        if self._inline or self._thread is not None:
            return
        self._thread = threading.Thread(target=self._worker, name="voicebot-reply", daemon=True)
        self._thread.start()

    def close(self) -> None:
        """Drain in-flight replies and stop the worker (idempotent)."""
        if self._closed:
            return
        self._closed = True
        if self._thread is None:
            return
        self._queue.put(_CLOSED)  # blocks only until a slot frees — we drain
        self._thread.join()
        self._thread = None

    # -- the loop ----------------------------------------------------------

    def run(self, source) -> None:
        """Consume *source* to exhaustion, then close it and the worker."""
        self._start()
        try:
            for utterance in source.lines():
                self._handle(utterance)
        finally:
            try:
                source.close()
            finally:
                self.close()

    def _handle(self, utterance: Utterance) -> None:
        self._emit(ListenEvent(KIND_HEARD, text=utterance.text))
        decision = self._gate.decide(utterance.text, duration_s=utterance.duration_s)
        if not decision.keep:
            self._emit(ListenEvent(KIND_SKIP, text=utterance.text, reason=decision.reason))
            return
        self._submit(utterance)

    def _submit(self, utterance: Utterance) -> None:
        if self._inline:
            self._answer(utterance)
            return
        try:
            self._queue.put_nowait(utterance)
        except queue.Full:
            # Drop the *oldest* pending utterance and keep the newest.
            try:
                self._queue.get_nowait()
            except queue.Empty:  # pragma: no cover - race, nothing to drop
                pass
            try:
                self._queue.put_nowait(utterance)
            except queue.Full:  # pragma: no cover - worker ate the slot
                pass

    def _worker(self) -> None:
        while True:
            item = self._queue.get()
            if item is _CLOSED:
                return
            try:
                self._answer(item)
            except Exception:  # a bad reply must not kill the loop
                log.exception("reply failed")

    def _answer(self, utterance: Utterance) -> None:
        reply = self._responder.respond(utterance.text)
        if reply.skip:
            self._emit(
                ListenEvent(KIND_SKIP, text=utterance.text, reason="notfunny", model=reply.model)
            )
        else:
            self._emit(
                ListenEvent(KIND_REPLY, text=utterance.text, reply=reply.text, model=reply.model)
            )
