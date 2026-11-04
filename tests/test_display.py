"""The LED-out display: colour markup, the scrolling screen, lazy connect, idle clear.

Driven through a duck-typed fake pad, so no hardware is needed; the screen-shape
assertions additionally need the host library (``touchy_pad``), which the path
dependency installs. See ``docs/plans/ledout.md``.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from voicebot.commands import COLOURS, WHITE, Run
from voicebot.display import (
    LABEL_ID,
    LEGACY_OVERRIDE_CHARS,
    MAX_OVERRIDE_CHARS,
    STARTUP_TEXT,
    PadDisplay,
    font_for,
    to_markup,
)


class FakePad:
    """A duck-typed stand-in for a ``touchy_pad.api.Touchy``."""

    def __init__(self, width: int = 32, height: int = 8, *, failures: int = 0) -> None:
        self.board_info = SimpleNamespace(display_width=width, display_height=height)
        self.saved: list[object] = []
        self.loaded: list[str] = []
        self.batches: list[list[object]] = []
        self.closed = False
        self._failures = failures

    def screen_save(self, screen):
        self.saved.append(screen)

    def screen_load(self, path):
        self.loaded.append(path)

    def set_properties(self, entries):
        if self._failures > 0:
            self._failures -= 1
            raise RuntimeError("usb gone")
        self.batches.append(list(entries))

    def close(self):
        self.closed = True

    def texts(self) -> list[str]:
        return [entry.string_value for batch in self.batches for entry in batch]


# --- to_markup -------------------------------------------------------------


def test_white_text_is_plain():
    assert to_markup([Run("Time to toast!")]) == "Time to toast!"


def test_a_coloured_run_is_wrapped():
    assert to_markup([Run("Danger!", COLOURS["red"])]) == "#FF0000 Danger!#"


def test_mixed_runs():
    assert to_markup([Run("Look out ", WHITE), Run("Danger!", COLOURS["red"])]) == (
        "Look out #FF0000 Danger!#"
    )


def test_hashes_are_dropped():
    assert to_markup([Run("a #tag b", COLOURS["blue"])]) == "#0000FF a tag b#"


def test_no_runs_is_empty():
    assert to_markup([]) == ""


def test_markup_is_truncated_to_the_device_cap():
    assert len(to_markup([Run("x" * 2000)])) == MAX_OVERRIDE_CHARS


def test_a_coloured_run_is_truncated_within_budget():
    out = to_markup([Run("x" * 2000, COLOURS["red"])])
    assert len(out) == MAX_OVERRIDE_CHARS
    assert out.startswith("#FF0000 ")
    assert out.endswith("#")


def test_markup_takes_a_smaller_budget():
    assert len(to_markup([Run("x" * 2000)], max_chars=LEGACY_OVERRIDE_CHARS)) == (
        LEGACY_OVERRIDE_CHARS
    )


# --- font_for --------------------------------------------------------------


def test_font_for_picks_the_largest_that_fits():
    assert (font_for(8), font_for(16), font_for(30), font_for(272), font_for(12)) == (
        8,
        16,
        30,
        30,
        8,
    )


# --- showing ---------------------------------------------------------------


def test_show_sends_one_text_override_and_builds_the_screen_once():
    pad = FakePad()
    PadDisplay(pad, clear_after=0).show([Run("Danger!", COLOURS["red"])])
    assert pad.texts() == ["#FF0000 Danger!#"]
    assert len(pad.saved) == 1
    assert pad.loaded == ["F:host/s/voicebot.pb"]


def test_start_shows_the_banner():
    pad = FakePad()
    PadDisplay(pad, clear_after=0).start()
    assert pad.texts() == [STARTUP_TEXT]


def test_the_saved_screen_is_a_scrolling_recolor_label():
    proto = pytest.importorskip("touchy_pad._proto")
    pad = FakePad(width=32, height=8)
    PadDisplay(pad, clear_after=0).show([Run("hi")])

    layer = pad.saved[0].to_proto().active
    label = getattr(layer, layer.WhichOneof("kind")).layout.children[0]
    assert label.id == LABEL_ID
    assert label.WhichOneof("kind") == "label"
    assert label.label.recolor is True
    assert label.label.text == STARTUP_TEXT
    assert label.label.long_mode == proto.LongMode.LONG_MODE_SCROLL_CIRCULAR
    assert (label.rect.w, label.rect.h) == (32, 8)
    assert any(style.font_size == 8 for style in label.styles)


def test_the_screen_is_not_rebuilt_per_quip():
    pad = FakePad()
    display = PadDisplay(pad, clear_after=0)
    display.show([Run("a")])
    display.show([Run("b")])
    assert len(pad.saved) == 1
    assert pad.texts() == ["a", "b"]


def test_connect_retries_once_on_a_transient_failure(monkeypatch):
    """A bad first response (stale device frame) self-heals on the retry."""
    from voicebot import display as display_mod

    calls: list[int] = []

    def flaky_connect():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("device returned NOT_FOUND (3)")
        return FakePad()

    monkeypatch.setattr(display_mod, "connect", flaky_connect)
    display = display_mod.PadDisplay(clear_after=0)
    display.show([Run("hi")])
    assert len(calls) == 2
    assert display._pad is not None


def test_connect_gives_up_after_the_allowed_attempts(monkeypatch, caplog):
    from voicebot import display as display_mod

    calls: list[int] = []

    def always_fail():
        calls.append(1)
        raise RuntimeError("no pad")

    monkeypatch.setattr(display_mod, "connect", always_fail)
    with caplog.at_level("WARNING"):
        display_mod.PadDisplay(clear_after=0).show([Run("hi")])
    assert len(calls) == display_mod.CONNECT_ATTEMPTS
    assert "no touchy-pad" in caplog.text


def test_a_headless_panel_is_reported_and_skipped(caplog):
    pad = FakePad(width=0, height=0)
    with caplog.at_level("WARNING"):
        PadDisplay(pad, clear_after=0).show([Run("hi")])
    assert pad.saved == [] and pad.batches == []
    assert "0x0" in caplog.text


def test_a_long_quip_is_retried_at_the_legacy_cap():
    """Old firmware caps the override at 127 bytes — retry shorter, keep the pad."""

    class CappedPad(FakePad):
        def set_properties(self, entries):
            if len(entries[0].string_value) > LEGACY_OVERRIDE_CHARS:
                raise RuntimeError("device returned INVALID_ARG (2)")
            super().set_properties(entries)

    pad = CappedPad()
    display = PadDisplay(pad, clear_after=0)
    display.show([Run("x" * 500)])
    assert pad.texts() == ["x" * LEGACY_OVERRIDE_CHARS]
    assert display._pad is pad  # a short quip is not a lost pad


def test_a_lost_pad_is_dropped_and_reconnects_next_time():
    pad = FakePad(failures=2)  # both the write and the legacy retry fail
    display = PadDisplay(pad, clear_after=0)
    display.show([Run("first")])
    assert display._pad is None
    assert pad.closed is True
    display._pad = pad  # the user plugs it back in
    display.show([Run("second")])
    assert pad.texts() == ["second"]


# --- the idle clear --------------------------------------------------------


def test_clear_after_zero_disarms_the_timer():
    display = PadDisplay(FakePad(), clear_after=0)
    display.show([Run("hi")])
    assert display._timer is None


def test_showing_arms_the_timer_and_clearing_blanks_the_marquee():
    pad = FakePad()
    display = PadDisplay(pad, clear_after=120)
    display.show([Run("hi")])
    assert display._timer is not None
    display._clear()
    assert pad.texts() == ["hi", ""]
    assert display._timer is None


def test_close_stops_the_timer_and_releases_the_pad():
    pad = FakePad()
    display = PadDisplay(pad, clear_after=120)
    display.show([Run("hi")])
    display.close()
    assert pad.closed is True
    assert display._timer is None
