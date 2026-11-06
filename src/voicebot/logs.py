"""Terminal logging: ``HEARD`` / ``SKIP`` / ``REPLY`` lines, colourised with rich.

Log records still go to **stderr**, and they are rendered with `rich`_ so the
terminal mirrors the LED matrix: a quip is printed in the very colours
:mod:`voicebot.display` scrolls for it, which makes colour debugging possible
without looking at the pad.

Only the *presentation* changes. Every record's message is still the plain
``REPLY: Danger ahead`` / ``SKIP(too_short): uh`` / ``HEARD: …`` text, so
``--json`` consumers, ``grep`` and ``caplog`` are unaffected — and rich drops
the colours by itself when the output is a pipe or ``NO_COLOR`` is set.

Two halves:

* :func:`configure` — install the rich handler on the root logger (once per
  process; called from ``voicebot.cli.main``), replacing ``logging.basicConfig``;
* :func:`heard_line` / :func:`skip_line` / :func:`reply_line` — build the
  :class:`rich.text.Text` that a log call emits (``listen.log_emitter``).

See ``docs/plans/ledout.md`` for the colours themselves.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from rich.console import Console
from rich.logging import RichHandler
from rich.text import Text

from .commands import Run

#: Tag styles for the three listen events. The pad can't say *which* of the three
#: it is, so the tag carries it: cyan = said, yellow = dropped, white = the quip.
HEARD_STYLE = "bold cyan"
SKIP_STYLE = "bold yellow"
REPLY_STYLE = "bold white"
#: Logger name, tag punctuation, and the utterance a ``SKIP`` threw away.
DIM_STYLE = "dim"

#: Root-logger level when nothing else sets one — what ``basicConfig`` used.
DEFAULT_LEVEL = logging.WARNING

_configured = False


def colour_style(colour: int) -> str:
    """``0xRRGGBB`` → rich's ``#rrggbb`` style: the very colour the LEDs show."""
    return f"#{colour & 0xFFFFFF:06x}"


def runs_text(runs: Sequence[Run]) -> Text:
    """A quip's colour runs as one styled :class:`~rich.text.Text`."""
    text = Text()
    for run in runs:
        text.append(run.text, style=colour_style(run.colour))
    return text


def heard_line(text: str) -> Text:
    """``HEARD: <text>`` — what the mic (or ``--fake``) picked up."""
    line = Text()
    line.append("HEARD: ", style=HEARD_STYLE)
    line.append(text)
    return line


def skip_line(reason: str, text: str) -> Text:
    """``SKIP(<reason>): <text>`` — an utterance that never got a reply."""
    line = Text()
    line.append("SKIP", style=SKIP_STYLE)
    line.append(f"({reason}): ", style=DIM_STYLE)
    line.append(text, style=DIM_STYLE)
    return line


def reply_line(runs: Sequence[Run], text: str = "") -> Text:
    """``REPLY: <quip>`` — the quip in the colours the display will scroll.

    *text* is the fallback when there are no runs (the plain, command-free text).
    """
    line = Text()
    line.append("REPLY: ", style=REPLY_STYLE)
    line.append_text(runs_text(runs) if runs else Text(text))
    return line


class _Handler(RichHandler):
    """A ``RichHandler`` that lets a :class:`~rich.text.Text` message keep its colour.

    ``RichHandler`` renders ``%(message)s``, which stringifies a ``Text`` back to
    uncoloured text; here a ``Text`` message is used as-is, so a quip's per-run
    colours survive. Such a line also skips the highlighter — model output is
    arbitrary text and must not be re-coloured as if it were a repr.
    """

    def render_message(self, record: logging.LogRecord, message: str) -> Text:
        if isinstance(record.msg, Text):
            # Our own pre-coloured line: no highlighter, no markup pass.
            body = record.msg
        else:
            # Anything else renders exactly as RichHandler would.
            body = super().render_message(record, message)  # type: ignore[assignment]
        line = Text()
        line.append(f"{record.name}: ", style=DIM_STYLE)
        line.append_text(body)
        return line


def make_handler(*, level: int = logging.NOTSET, console: Console | None = None) -> logging.Handler:
    """The rich handler — stderr by default, so stdout stays pipeable/``--json``.

    *level* defaults to ``NOTSET``: as with ``basicConfig``, it is the *root
    logger's* level (set by :func:`configure`) that decides what is emitted, so a
    ``voicebot`` logger raised to INFO (``voicebot listen``) still gets through.
    """
    return _Handler(
        level=level,
        console=console or Console(stderr=True),
        show_time=False,
        show_path=False,
        rich_tracebacks=True,
        # A quip may legitimately contain ``[...]``; never read it as markup.
        markup=False,
    )


def configure(level: int = DEFAULT_LEVEL) -> None:
    """Send all logging through the rich handler (once per process)."""
    global _configured
    if _configured:
        return
    _configured = True
    root = logging.getLogger()
    if root.level == logging.NOTSET or root.level > level:
        root.setLevel(level)
    root.addHandler(make_handler())
