"""LED out: scroll the quip on a touchy-pad (stage 3).

This is the **only** module that imports ``touchy_pad`` (see
``docs/plans/ledout.md``), so pulling voicebot out to its own repo stays a
one-file diff plus the PyPI switch — and the import is *lazy* (inside the
functions that need it) so the module can be imported and unit-tested without the
parent repo installed.

Shape:

* one full-panel scrolling-label screen is built once per connection and saved;
* every quip afterwards is a single ``SetPropertiesCmd`` batch — the label's
  ``text``, carrying LVGL inline-recolour markup — never a screen re-upload;
* a pad is opened **lazily**, only when there is something to show, so a pad
  plugged in later is picked up on the next message and a missing one is never
  fatal;
* an idle timer blanks the marquee after ``clear_after`` seconds of quiet.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from threading import Lock, Timer
from typing import Any

from .commands import Run

log = logging.getLogger(__name__)

#: On-device screen + widget names — the contract between the saved screen and
#: the runtime property overrides. Deliberately *not* ``default`` so a later
#: ``touchy init`` / ``touchy screen demo`` cannot clobber it (or vice-versa).
SCREEN_NAME = "voicebot"
LABEL_ID = "voicebot_msg"

#: What the panel shows on connect, and the colour LVGL draws unmarked text in.
STARTUP_TEXT = "I'm voicebot"
WHITE = 0xFFFFFF

#: The label font sizes the firmware actually compiles (see the plan's Q6);
#: any other size silently falls back to the theme default.
FONT_SIZES = (8, 16, 30)

#: Blank the display after this many seconds with no new reply (0 = never).
DEFAULT_CLEAR_AFTER_S = 120.0

#: The device stores a `text` override in a fixed buffer: nanopb rejects a
#: `SetPropertyCmd.string_value` longer than its `max_size`, and the firmware has
#: no way to report that cap. `max_size` is 512 *including* the NUL terminator
#: (stage LB17 raised it from 128), so 511 characters of rendered markup is the
#: most the device accepts — measured on hardware. Quips are truncated to fit.
MAX_OVERRIDE_CHARS = 511

#: Connect attempts before giving up until the next message. A bad *first*
#: response (a leftover frame in the device FIFO from a previously-killed host)
#: is a known transient that self-heals — see the parent repo's open-issues.md.
CONNECT_ATTEMPTS = 2


class DisplayError(RuntimeError):
    """The pad is reachable but can't be driven (e.g. a headless 0×0 panel)."""


def connect() -> Any:
    """Open a touchy-pad connection (USB, or the simulator via ``TOUCHY_SIM_URL``)."""
    from touchy_pad.api import touchy_open

    return touchy_open()


def font_for(height: int) -> int:
    """The largest *compiled* font size that fits *height* (the plan's Q6).

    A size with no compiled font renders at the theme default instead, so stay
    inside the set the firmware actually ships.
    """
    fits = [size for size in FONT_SIZES if size <= height]
    return max(fits) if fits else FONT_SIZES[0]


def to_markup(runs: Sequence[Run], max_chars: int = MAX_OVERRIDE_CHARS) -> str:
    """Colour runs → LVGL inline-recolour text, truncated to *max_chars*.

    A non-white run becomes ``#RRGGBB text#`` — the space after the colour
    terminates the command and is not drawn, and the closing ``#`` reverts to the
    label's ``text_color`` — while a white run is emitted plainly. A literal
    ``#`` is dropped: it delimits a command and this LVGL version's ``##`` escape
    is dead code.

    *max_chars* bounds the **rendered** length because the device keeps a
    ``text`` override in a fixed buffer and rejects anything longer (see
    :data:`MAX_OVERRIDE_CHARS`). Truncation happens on a run boundary, so the
    markup always stays well-formed.
    """
    parts: list[str] = []
    used = 0
    for run in runs:
        text = run.text.replace("#", "")
        if not text:
            continue
        opening, closing = ("", "") if run.colour == WHITE else (f"#{run.colour:06X} ", "#")
        room = max_chars - used - len(opening) - len(closing)
        if room <= 0:
            break
        body = text[:room]
        parts.append(f"{opening}{body}{closing}")
        used += len(opening) + len(body) + len(closing)
        if len(body) < len(text):
            break  # truncated — stop rather than opening another run
    return "".join(parts)


def _daemon_timer(delay_s: float, fn: Callable[[], None]) -> Timer:
    timer = Timer(delay_s, fn)
    timer.daemon = True
    return timer


def _safe_close(pad: Any) -> None:
    if pad is None:
        return
    try:
        pad.close()
    except Exception:
        log.debug("voicebot: closing the pad failed", exc_info=True)


class PadDisplay:
    """Owns the on-device scrolling-label screen and the per-quip updates.

    ``pad`` may be injected (tests use a stub); otherwise a real pad is opened
    lazily on the first :meth:`show`. All pad calls are serialized by a lock,
    because :meth:`show` runs on the listener's reply worker while the idle-clear
    timer fires on its own thread.
    """

    def __init__(
        self,
        pad: Any | None = None,
        *,
        screen_name: str = SCREEN_NAME,
        clear_after: float = DEFAULT_CLEAR_AFTER_S,
        font_size: int | None = None,
        timer_factory: Callable[[float, Callable[[], None]], Timer] = _daemon_timer,
    ) -> None:
        self._pad = pad
        self._prepared = False
        self._screen_name = screen_name
        self._clear_after = float(clear_after)
        self._font_size = font_size
        self._timer_factory = timer_factory
        self._lock = Lock()
        self._timer: Timer | None = None
        self._size: tuple[int, int] = (0, 0)

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        """Show the startup banner (connecting lazily, if a pad is attached)."""
        self.show([Run(STARTUP_TEXT)])

    def close(self) -> None:
        """Stop the idle timer and release the pad (idempotent)."""
        with self._lock:
            self._cancel_timer()
            self._forget_pad()

    # -- the public verb ---------------------------------------------------

    def show(self, runs: Sequence[Run]) -> None:
        """Render *runs* on the pad (empty ⇒ clear) and (re)arm the idle timer."""
        with self._lock:
            pad = self._open()
            if pad is None:
                return
            if not self._write_quip(pad, runs):
                self._forget_pad()
                return
            self._arm_timer()

    def _write_quip(self, pad: Any, runs: Sequence[Run]) -> bool:
        """Send the quip; ``False`` means the pad looks gone (drop the handle).

        :func:`to_markup` keeps the string inside the device's buffer, so a
        refusal here means the link itself is broken rather than a bad payload.
        """
        try:
            self._write(pad, to_markup(runs))
            return True
        except Exception as exc:  # noqa: BLE001 — a lost pad is not fatal
            log.warning("voicebot: lost the touchy-pad (%s) — will reconnect", exc)
            return False

    # -- the pad -----------------------------------------------------------

    def _open(self) -> Any | None:
        """The pad, connecting + provisioning lazily; ``None`` (logged) on failure."""
        if self._pad is None:
            self._pad = self._connect()
            if self._pad is None:
                return None
        if not self._prepared:
            try:
                self._prepare(self._pad)
            except Exception as exc:  # noqa: BLE001 — a bad pad is not fatal
                log.warning("voicebot: found a touchy-pad but can't drive it (%s)", exc)
                self._forget_pad()
                return None
            self._prepared = True
            width, height = self._size
            log.info(
                "voicebot: display ready on %dx%d (screen %r)", width, height, self._screen_name
            )
        return self._pad

    def _connect(self) -> Any | None:
        """Open the pad, retrying once; ``None`` (logged) when there is none.

        A bad *first* response — a leftover frame in the device's bulk-IN FIFO
        from a host process that was killed mid-RPC — is a documented transient
        that self-heals on the next attempt (see the parent repo's
        ``docs/open-issues.md``), so one retry turns a confusing failure into a
        working connection.
        """
        for attempt in range(CONNECT_ATTEMPTS):
            try:
                return connect()
            except Exception as exc:  # noqa: BLE001 — a failed connect is a retry reason
                if attempt + 1 < CONNECT_ATTEMPTS:
                    log.debug(
                        "voicebot: connect attempt %d failed (%s); retrying", attempt + 1, exc
                    )
                    continue
                log.warning("voicebot: no touchy-pad to show this on (%s)", exc)
        return None

    def _prepare(self, pad: Any) -> None:
        """Build + save + load the one scrolling-label screen for this panel."""
        from touchy_pad.api import LongMode, Screen, absolute, label, rect, style
        from touchy_pad.paths import screen_path

        info = getattr(pad, "board_info", None)
        width = int(getattr(info, "display_width", 0) or 0)
        height = int(getattr(info, "display_height", 0) or 0)
        if width <= 0 or height <= 0:
            raise DisplayError(
                "the panel reports 0x0 — provision a display first, e.g. "
                "`touchy pref from-template led-32x8` for an LED matrix"
            )
        self._size = (width, height)

        screen = Screen(self._screen_name, layout=absolute())
        screen += label(
            LABEL_ID,
            text=STARTUP_TEXT,
            font_size=self._font_size or font_for(height),
            long_mode=LongMode.LONG_MODE_SCROLL_CIRCULAR,
            recolor=True,  # stage LB17: parse `#RRGGBB text#` runs
            rect=rect(0, 0, width, height),  # SCROLL_CIRCULAR needs a fixed box
            style=style(text_color=WHITE),
        )
        pad.screen_save(screen)
        pad.screen_load(screen_path(self._screen_name))

    def _write(self, pad: Any, text: str) -> None:
        """One ``text`` property override — the whole per-quip cost."""
        from touchy_pad.api import build_property_override

        pad.set_properties([build_property_override(LABEL_ID, "text", text)])

    def _forget_pad(self) -> None:
        pad, self._pad = self._pad, None
        self._prepared = False
        _safe_close(pad)

    # -- the idle clear ----------------------------------------------------

    def _arm_timer(self) -> None:
        self._cancel_timer()
        if self._clear_after > 0:
            self._timer = self._timer_factory(self._clear_after, self._clear)
            self._timer.start()

    def _cancel_timer(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def _clear(self) -> None:
        """Blank the marquee after a quiet spell — runs on the timer thread."""
        with self._lock:
            self._timer = None
            if self._pad is None:
                return
            try:
                self._write(self._pad, "")
            except Exception:
                log.debug("voicebot: idle clear failed", exc_info=True)
                self._forget_pad()
