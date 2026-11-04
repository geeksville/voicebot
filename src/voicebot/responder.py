"""The responder: one overheard line in, one witty :class:`Reply` out.

Deliberately transport-free — it is handed a ``chat`` callable
(``messages -> text``) so tests use a fake and never touch the network. The
:class:`~voicebot.server.ChatClient` supplies the real one.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .persona import DEFAULT_PERSONA, is_notfunny

#: ``messages -> assistant text``. ``messages`` is the OpenAI chat shape.
ChatFn = Callable[[list[dict[str, str]]], str]


@dataclass(frozen=True)
class Reply:
    """The responder's verdict for one overheard line.

    ``text`` is the line to *show* — empty when :attr:`skip` is set, so callers
    can uniformly print ``text`` without re-checking the sentinel.
    """

    source: str
    text: str
    skip: bool
    model: str

    def as_dict(self) -> dict[str, object]:
        """The ``--json`` shape: ``{input, reply, skip, model}``."""
        return {"input": self.source, "reply": self.text, "skip": self.skip, "model": self.model}


class Responder:
    """Builds the chat request for each line and applies the NOTFUNNY rule."""

    def __init__(
        self,
        chat: ChatFn,
        *,
        model: str,
        persona: str = DEFAULT_PERSONA,
        notfunny: bool = True,
    ) -> None:
        self._chat = chat
        self._model = model
        self._persona = persona
        self._notfunny = notfunny

    def messages_for(self, line: str) -> list[dict[str, str]]:
        """The ``[system, user]`` message list for one overheard line."""
        return [
            {"role": "system", "content": self._persona},
            {"role": "user", "content": line},
        ]

    def respond(self, line: str) -> Reply:
        """Ask for a reply to *line* and apply the NOTFUNNY suppression rule."""
        raw = self._chat(self.messages_for(line)).strip()
        skip = self._notfunny and is_notfunny(raw)
        return Reply(source=line, text="" if skip else raw, skip=skip, model=self._model)
