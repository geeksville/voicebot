"""The persona (comedic mechanism) and the ``NOTFUNNY`` contract.

Wit from a small model does not come from "tell me a joke" — that dredges up
memorised dad jokes (see ``docs/responder.md``). It comes from a *comedic
mechanism baked into the system prompt* plus a loosened sampler. Both are lifted
from ``launch-funny.sh`` so the app inherits the prototype's behaviour.

The mechanism includes the escape hatch: the model may answer with the single
token ``NOTFUNNY`` when it has nothing worth saying, and the responder then
*suppresses* that reply rather than showing a weak joke.
"""

from __future__ import annotations

#: The sentinel a model returns when it has no good line.
NOTFUNNY = "NOTFUNNY"

#: Default system prompt — the toaster-robot persona from launch-funny.sh.
DEFAULT_PERSONA = """You are a witty, slightly dramatic toaster-sized robot living on a desk, eavesdropping on the humans nearby.
The input you receive is snippets from a conversation you are eavesdropping on.
very important: if you don't think you have something funny enough to say, just say NOTFUNNY (we will use that token to skip your reply). It is better to say NOTFUNNY than to force a weak joke.
If you do think of something funny to say, go ahead and reply with it.
Never tell standard knock-knock or pun jokes. Instead, reply to whatever the user says with dry observational humor, absurd over-confident theories, or playful sarcasm in 1 to 2 short sentences.
Your words will appear on a scrolling LED display. NEVER use emoji.
Never open with 'Sure' or 'Certainly'."""


def is_notfunny(reply: str) -> bool:
    """True if *reply* is the ``NOTFUNNY`` sentinel (however it was dressed up).

    Tolerant of the ways a chat model wraps a one-word answer: surrounding
    whitespace, quotes / markdown emphasis, and trailing punctuation. A real
    sentence that merely *contains* the token is not treated as a skip.
    """
    text = reply.strip().strip("\"'`*").strip().rstrip(".!,").strip()
    return text.upper() == NOTFUNNY
