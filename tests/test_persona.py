"""The persona text and the NOTFUNNY normaliser."""

from __future__ import annotations

from voicebot.persona import DEFAULT_PERSONA, NOTFUNNY, is_notfunny


def test_token():
    assert NOTFUNNY == "NOTFUNNY"


def test_default_persona_carries_the_contract():
    # The mechanism must both name the escape hatch and forbid emoji (the
    # output is destined for a scrolling LED matrix).
    assert NOTFUNNY in DEFAULT_PERSONA
    assert "emoji" in DEFAULT_PERSONA


def test_is_notfunny_accepts_dressed_up_sentinels():
    for raw in (
        "NOTFUNNY",
        "notfunny",
        " NOTFUNNY \n",
        '"NOTFUNNY"',
        "*Notfunny*",
        "**NOTFUNNY**",
        "NOTFUNNY.",
        "NOTFUNNY!",
    ):
        assert is_notfunny(raw), raw


def test_is_notfunny_rejects_real_replies():
    for raw in (
        "Time to toast!",
        "Not funny.",
        "NOTFUNNY-ish",
        "I think this is NOTFUNNY material",
        "",
    ):
        assert not is_notfunny(raw), raw
