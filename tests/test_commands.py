"""The ``/command`` parser: colour runs, ``/notfunny``, and the stripping rules."""

from __future__ import annotations

from voicebot.commands import COLOURS, WHITE, Run, parse, resolve_colour


def test_plain_text_is_one_white_run():
    out = parse("Time to toast!")
    assert out.runs == (Run("Time to toast!", WHITE),)
    assert out.text == "Time to toast!"
    assert out.skip is False
    assert out.found == ()


def test_notfunny_skips():
    out = parse("/notfunny")
    assert out.skip is True
    assert out.runs == ()
    assert out.text == ""
    assert out.found == ("/notfunny",)


def test_notfunny_wins_over_text():
    assert parse("/notfunny I'll stay quiet").skip is True


def test_dressed_up_notfunny_still_skips():
    assert parse('"**/notfunny**"').skip is True


def test_text_that_merely_contains_notfunny_is_not_a_skip():
    assert parse("Not funny, that joke.").skip is False


def test_colour_starts_a_run():
    out = parse("/color/red Danger!")
    assert out.runs == (Run("Danger!", COLOURS["red"]),)
    assert out.text == "Danger!"


def test_colour_mid_sentence_splits_runs():
    out = parse("Look out /color/red Danger!")
    assert out.runs == (Run("Look out ", WHITE), Run("Danger!", COLOURS["red"]))
    assert out.text == "Look out Danger!"


def test_several_colours_in_one_reply():
    out = parse("/color/red Stop /color/blue go")
    assert [r.colour for r in out.runs] == [COLOURS["red"], COLOURS["blue"]]
    assert out.text == "Stop go"


def test_hex_colours_are_accepted():
    for value in ("0xFF00AA", "#FF00AA", "ff00aa"):
        assert parse(f"/color/{value} hi").runs[0].colour == 0xFF00AA


def test_named_colours_are_case_insensitive():
    assert parse("/COLOR/Red hi").runs[0].colour == COLOURS["red"]


def test_a_bad_colour_value_keeps_the_current_colour(caplog):
    with caplog.at_level("WARNING"):
        out = parse("/color/chartreuse hi")
    assert out.runs == (Run("hi", WHITE),)
    assert "chartreuse" in caplog.text


def test_an_unknown_command_is_stripped_and_logged(caplog):
    with caplog.at_level("WARNING"):
        out = parse("/frobnicate hi")
    assert out.text == "hi"
    assert "/frobnicate" in out.found
    assert "frobnicate" in caplog.text


def test_a_command_only_reply_is_a_skip():
    assert parse("/color/red").skip is True
    assert parse("   ").skip is True


def test_the_colon_separator_is_not_a_colour_command(caplog):
    # The contract switched from ``/color:NAME`` to ``/color/NAME``; the old
    # form is no longer a valid command, so the colour stays white.
    with caplog.at_level("WARNING"):
        out = parse("/color:red hi")
    assert out.runs == (Run(":red hi", WHITE),)
    assert "/color" in out.found
    assert "color" in caplog.text


def test_urls_and_word_slashes_are_not_commands():
    assert parse("see http://example.com/x for more").text == "see http://example.com/x for more"
    assert parse("either/or").text == "either/or"


def test_resolve_colour():
    assert resolve_colour("green") == COLOURS["green"]
    assert resolve_colour("0X00FF00") == 0x00FF00
    assert resolve_colour("nope") is None
