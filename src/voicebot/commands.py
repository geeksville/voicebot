"""The ``/command`` contract: directives embedded in the model's output.

Any word in the LLM's reply that starts with ``/`` is a directive to voicebot and
is *never displayed*. Two commands exist today:

* ``/notfunny`` — the model has nothing worth saying; suppress the whole reply.
* ``/color/NAME`` — start a coloured run. ``NAME`` is ``red`` / ``green`` /
  ``blue`` / ``yellow`` / ``white``, or ``0xRRGGBB`` (also ``#RRGGBB`` /
  ``RRGGBB``) so the model can pick any colour. Everything after the command is
  that colour until the next ``/color`` (or the end of the reply).

A reply parses into ordered :class:`Run` objects (text + colour). Colours are
purely decorative here: LVGL renders the *unmarked* text in the label's
``text_color`` (white) and only the ``#RRGGBB …#`` runs in their colour, so a
reply with no ``/color`` is simply white — there is no reset and no carried-over
state between replies.

See ``docs/plans/ledout.md`` → "The ``/command`` contract".
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

log = logging.getLogger(__name__)

#: The "unmarked" colour — what LVGL renders plain (non-``#RRGGBB``) text in.
WHITE = 0xFFFFFF

#: Named colours accepted by ``/color/NAME``.
COLOURS = {
    "red": 0xFF0000,
    "green": 0x00FF00,
    "blue": 0x0000FF,
    "yellow": 0xFFFF00,
    "white": 0xFFFFFF,
}

#: A command token: ``/name`` optionally ``/value``, starting a word (so ``a/b``
#: and the ``//`` in a URL are not commands). ``\w``/``/`` before the slash is
#: excluded so ``http://x`` does not read as ``/x``. The value is a single
#: whitespace-free token, so ``/color/red`` and ``/color/0xFF00AA`` both parse.
_CMD_RE = re.compile(r"(?<![/\w])/([a-z]+)(?:/(\S+))?", re.IGNORECASE)
#: ``0xRRGGBB`` / ``#RRGGBB`` / a bare ``RRGGBB``.
_HEX_RE = re.compile(r"^(?:0x|#)?([0-9a-f]{6})$", re.IGNORECASE)
_SPACE_RE = re.compile(r"[ \t]+")


@dataclass(frozen=True)
class Run:
    """A stretch of displayable text in a single colour (``0xRRGGBB``)."""

    text: str
    colour: int = WHITE


@dataclass(frozen=True)
class ParsedReply:
    """One model reply, split into command-free colour runs."""

    runs: tuple[Run, ...] = ()
    skip: bool = False
    found: tuple[str, ...] = ()

    @property
    def text(self) -> str:
        """The plain text, every command stripped."""
        return "".join(run.text for run in self.runs)


def resolve_colour(value: str) -> int | None:
    """``/color/`` value → ``0xRRGGBB``, or ``None`` if it isn't recognised."""
    named = COLOURS.get(value.lower())
    if named is not None:
        return named
    match = _HEX_RE.match(value)
    return int(match.group(1), 16) if match else None


def _finish(segments: list[tuple[str, int]], found: list[str], skip: bool) -> ParsedReply:
    """Tidy raw ``(text, colour)`` segments into a :class:`ParsedReply`."""
    runs: list[Run] = []
    for raw_text, colour in segments:
        text = _SPACE_RE.sub(" ", raw_text)
        if not runs:
            text = text.lstrip(" ")  # leading space of the whole message
        elif runs[-1].text.endswith(" "):
            text = text.lstrip(" ")  # no double space across a run boundary
        if text.strip():
            runs.append(Run(text, colour))
    if runs:
        runs[-1] = Run(runs[-1].text.rstrip(" "), runs[-1].colour)
    return ParsedReply(runs=tuple(runs), skip=skip or not runs, found=tuple(found))


def parse(raw: str) -> ParsedReply:
    """Split *raw* into colour runs and apply its directives."""
    colour = WHITE
    skip = False
    found: list[str] = []
    segments: list[tuple[str, int]] = []
    pos = 0

    for match in _CMD_RE.finditer(raw):
        segments.append((raw[pos : match.start()], colour))
        pos = match.end()
        token = match.group(0)
        name = match.group(1).lower()
        value = match.group(2) or ""
        found.append(token)
        if name == "notfunny":
            skip = True
        elif name == "color":
            resolved = resolve_colour(value)
            if resolved is None:
                log.warning("ignoring unknown colour %r in %r", value, token)
            else:
                colour = resolved
        else:
            log.warning("ignoring unknown command %r", token)
    segments.append((raw[pos:], colour))

    return _finish(segments, found, skip)
