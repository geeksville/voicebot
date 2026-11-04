"""Microphone capture + speech-to-text — the "audio in" stage.

This is the only module that imports ``moonshine_voice`` / ``sounddevice`` (and
it does so lazily, so importing :mod:`voicebot` — and the test suite — never
needs them). Everything else talks to the tiny :class:`TranscriptSource` seam
below, which is what makes the loop testable with no mic, no model and no
network.

Mic: a Seeed reSpeaker XVF3800 USB array in production, addressed by name so it
is found whatever PortAudio index it lands on. Engine: Moonshine Voice's
``MicTranscriber``, which already does VAD, streaming and its own worker-thread
capture + resampling to 16 kHz — we only configure it and bridge its finished
lines onto a queue. See ``docs/plans/audioin.md``.
"""

from __future__ import annotations

import logging
import queue
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TextIO, runtime_checkable

from .server import VoicebotError

log = logging.getLogger(__name__)


class AudioError(VoicebotError):
    """The microphone could not be opened, or the STT engine could not start."""


@dataclass(frozen=True)
class Utterance:
    """One finished thing a person said, as produced by the STT engine."""

    text: str
    duration_s: float | None = None


_CLOSED = object()


@runtime_checkable
class TranscriptSource(Protocol):
    """The audio seam: a blocking stream of finished utterances."""

    def lines(self) -> Iterator[Utterance]:
        """Block and yield finished utterances until :meth:`close`."""
        ...

    def close(self) -> None:
        """Stop the source and release the microphone."""
        ...


class FakeTranscriptSource:
    """Replay a scripted list of utterances — tests and ``listen --fake``.

    Needs no audio hardware and no model, so it drives the whole loop in CI.
    """

    def __init__(self, utterances: Iterable[str | Utterance]) -> None:
        self._items = [u if isinstance(u, Utterance) else Utterance(str(u)) for u in utterances]
        self.closed = False

    def lines(self) -> Iterator[Utterance]:
        yield from self._items

    def close(self) -> None:
        self.closed = True


def read_lines(stream: TextIO) -> list[str]:
    """The non-blank, whitespace-trimmed lines of *stream* (for ``--fake``)."""
    return [stripped for raw in stream if (stripped := raw.strip())]


#: Friendly ``--model-arch`` names -> Moonshine ``ModelArch`` attribute. The
#: streaming variants are what we want; every English alias maps to one.
_MOONSHINE_ARCHES = {
    "tiny": "TINY_STREAMING",
    "tiny-streaming": "TINY_STREAMING",
    "tinystreaming": "TINY_STREAMING",
    "base": "BASE_STREAMING",
    "base-streaming": "BASE_STREAMING",
    "basestreaming": "BASE_STREAMING",
    "small": "SMALL_STREAMING",
    "small-streaming": "SMALL_STREAMING",
    "smallstreaming": "SMALL_STREAMING",
    "medium": "MEDIUM_STREAMING",
    "medium-streaming": "MEDIUM_STREAMING",
    "mediumstreaming": "MEDIUM_STREAMING",
}


def resolve_device(hint: str | None, *, device: int | str | None = None) -> int | str | None:
    """Pick a PortAudio capture device.

    An explicit *device* (index or name substring) always wins. Otherwise the
    first input device whose name contains *hint* (case-insensitive) is used —
    that is how the reSpeaker XVF3800 is found whatever index it gets. ``None``
    means "let PortAudio pick the default".
    """
    if device is not None:
        return device
    if not hint:
        return None
    try:
        import sounddevice as sd

        for index, info in enumerate(sd.query_devices()):
            if info.get("max_input_channels", 0) > 0 and hint.lower() in info["name"].lower():
                log.info("using input device %d: %s", index, info["name"])
                return index
    except Exception as exc:  # noqa: BLE001 - any PortAudio/backend error is fine here
        log.warning("could not query audio devices (%s); using the default", exc)
        return None
    log.warning("no input device matched %r; using PortAudio's default", hint)
    return None


class AudioIn:
    """A :class:`TranscriptSource` backed by the mic and a Moonshine model.

    ``MicTranscriber`` does the heavy lifting (VAD, streaming, its own capture
    worker, resampling to 16 kHz); we configure it, bridge its ``on_line``
    callback onto a queue, and hand finished lines out through :meth:`lines`.
    """

    def __init__(
        self,
        *,
        device: int | str | None = None,
        mic_hint: str | None = "respeaker",
        model_arch: str = "small",
        language: str = "en",
        models_dir: str | Path | None = None,
        channels: int | None = None,
        options: dict | None = None,
    ) -> None:
        self._device = resolve_device(mic_hint, device=device)
        self._model_arch = model_arch
        self._language = language
        self._models_dir = models_dir
        self._channels = channels
        self._options = options or {}
        self._queue: queue.Queue = queue.Queue()
        self._mic = None

    # -- construction ------------------------------------------------------

    def _build(self):
        """Build, load and start the Moonshine mic transcriber."""
        arch_name = _MOONSHINE_ARCHES.get(self._model_arch.lower().replace("_", "-"))
        if arch_name is None:
            known = ", ".join(sorted(set(_MOONSHINE_ARCHES)))
            raise AudioError(f"unknown model arch {self._model_arch!r} (expected one of: {known})")

        try:
            from moonshine_voice import MicTranscriber, ModelArch
        except Exception as exc:  # pragma: no cover - dependency missing
            raise AudioError(f"speech-to-text engine unavailable: {exc}") from exc

        mic = MicTranscriber().language(self._language).model_arch(getattr(ModelArch, arch_name))
        if self._device is not None:
            mic.device(self._device)
        if self._channels is not None:
            mic.channels(self._channels)
        if self._models_dir is not None:
            mic.models_from(str(self._models_dir))
        if self._options:
            mic.options(self._options)
        mic.on_line(self._on_line)
        try:
            log.info("loading the %s speech-to-text model…", self._model_arch)
            mic.load()
            mic.start()
        except Exception as exc:
            raise AudioError(f"could not start the microphone: {exc}") from exc
        return mic

    def _on_line(self, line) -> None:
        """Called from Moonshine's worker thread for each finished line."""
        text = (getattr(line, "text", "") or "").strip()
        if text:
            self._queue.put(Utterance(text, getattr(line, "duration", None)))

    # -- TranscriptSource --------------------------------------------------

    def lines(self) -> Iterator[Utterance]:
        self._mic = self._build()
        try:
            while True:
                item = self._queue.get()
                if item is _CLOSED:
                    return
                yield item
        finally:
            self._teardown()

    def close(self) -> None:
        # Wake lines() (if running) and stop the mic now, so a ctrl-c that
        # interrupts the loop still releases the device.
        self._queue.put(_CLOSED)
        self._teardown()

    def _teardown(self) -> None:
        mic, self._mic = self._mic, None
        if mic is None:
            return
        for step in ("stop", "close"):
            try:
                getattr(mic, step)()
            except Exception as exc:  # noqa: BLE001 - best-effort cleanup, never fatal
                log.debug("mic.%s() while closing: %s", step, exc)
