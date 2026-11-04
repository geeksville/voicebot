"""The utterance gate: content words, thresholds and repeat debounce (pure logic)."""

from __future__ import annotations

from voicebot.gate import UtteranceGate, content_words


def test_content_words_strips_filler_and_punctuation():
    assert content_words("Uh, the bread is done baking!") == [
        "the",
        "bread",
        "is",
        "done",
        "baking",
    ]


def test_content_words_keeps_contractions():
    assert "don't" in content_words("I don't know")


def test_short_utterance_is_dropped():
    decision = UtteranceGate(min_words=3).decide("hello there")
    assert decision.keep is False
    assert decision.reason == "too_short"


def test_filler_only_is_dropped_even_if_long():
    decision = UtteranceGate(min_words=1).decide("uh um hmm yeah okay")
    assert decision.keep is False
    assert decision.reason == "too_short"


def test_keeps_a_few_content_words():
    decision = UtteranceGate(min_words=3).decide("the bread is done baking")
    assert decision.keep is True
    assert decision.reason == "keep"


def test_min_words_counts_content_only():
    # 4 tokens but only 2 of them carry content -> below a floor of 3.
    assert UtteranceGate(min_words=3).decide("uh the bread um").keep is False


def test_duration_gate_applied_when_known():
    gate = UtteranceGate(min_words=1, min_duration_s=1.0)
    assert gate.decide("the bread is done", duration_s=0.3).reason == "too_brief"
    assert gate.decide("the bread is done", duration_s=2.0).keep is True


def test_duration_gate_ignored_when_unknown():
    gate = UtteranceGate(min_words=1, min_duration_s=1.0)
    assert gate.decide("the bread is done", duration_s=None).keep is True


def test_debounce_suppresses_identical_repeat_within_window():
    now = [0.0]
    gate = UtteranceGate(min_words=1, debounce_s=5.0, clock=lambda: now[0])
    assert gate.decide("the bread is done").keep is True
    now[0] = 1.0
    assert gate.decide("the bread is done").reason == "repeat"
    now[0] = 6.0
    assert gate.decide("the bread is done").keep is True


def test_debounce_ignores_a_different_utterance():
    now = [0.0]
    gate = UtteranceGate(min_words=1, debounce_s=5.0, clock=lambda: now[0])
    assert gate.decide("the bread is done").keep is True
    assert gate.decide("the light is red").keep is True


def test_debounce_normalises_case_and_punctuation():
    now = [0.0]
    gate = UtteranceGate(min_words=1, debounce_s=5.0, clock=lambda: now[0])
    assert gate.decide("The bread is done!").keep is True
    assert gate.decide("the bread is done").reason == "repeat"
