"""The persona text and the ``/command`` convention it advertises."""

from __future__ import annotations

from voicebot.persona import DEFAULT_PERSONA


def test_default_persona_carries_the_contract():
    # The mechanism must name the escape hatch, advertise colour, and forbid
    # emoji / stray command characters (the output is destined for a scrolling
    # LED matrix).
    assert "/notfunny" in DEFAULT_PERSONA
    assert "/color/" in DEFAULT_PERSONA
    assert "emoji" in DEFAULT_PERSONA
