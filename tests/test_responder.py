"""The responder's message shaping and NOTFUNNY suppression (no network)."""

from __future__ import annotations

from voicebot.responder import Reply, Responder


def _chat_returning(text: str):
    def chat(messages: list[dict[str, str]]) -> str:
        return text

    return chat


def test_respond_returns_a_quip():
    responder = Responder(_chat_returning("Time to toast!"), model="m")
    assert responder.respond("the bread is done baking") == Reply(
        source="the bread is done baking", text="Time to toast!", skip=False, model="m"
    )


def test_respond_suppresses_notfunny():
    responder = Responder(_chat_returning("NOTFUNNY"), model="m")
    out = responder.respond("meer loves the new toy")
    assert out.skip is True
    assert out.text == ""  # callers may print .text unconditionally


def test_notfunny_can_be_disabled():
    responder = Responder(_chat_returning("NOTFUNNY"), model="m", notfunny=False)
    out = responder.respond("x")
    assert out.skip is False
    assert out.text == "NOTFUNNY"


def test_messages_are_system_then_user():
    seen: list[list[dict[str, str]]] = []

    def chat(messages: list[dict[str, str]]) -> str:
        seen.append(messages)
        return "ok"

    responder = Responder(chat, model="m", persona="PERSONA")
    responder.respond("hello there")
    assert seen == [
        [
            {"role": "system", "content": "PERSONA"},
            {"role": "user", "content": "hello there"},
        ]
    ]


def test_as_dict_json_shape():
    out = Reply(source="a", text="b", skip=False, model="m")
    assert out.as_dict() == {"input": "a", "reply": "b", "skip": False, "model": "m"}
