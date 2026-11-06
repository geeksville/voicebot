"""The audio seam: fake source, line reading, device selection, the queue bridge."""

from __future__ import annotations

import io
import sys
import types

import pytest

from voicebot.audio import (
    _MOONSHINE_ARCHES,
    AudioError,
    AudioIn,
    FakeTranscriptSource,
    Utterance,
    read_lines,
    resolve_device,
)


def test_fake_source_yields_utterances_and_closes():
    source = FakeTranscriptSource(["a", Utterance("b", 1.5)])
    assert [u.text for u in source.lines()] == ["a", "b"]
    assert [u.duration_s for u in source.lines()] == [None, 1.5]
    assert source.closed is False
    source.close()
    assert source.closed is True


def test_read_lines_trims_and_drops_blanks():
    assert read_lines(io.StringIO("a\n\n  b  \n")) == ["a", "b"]


def test_friendly_arch_names_all_map_to_streaming():
    for name in ("tiny", "base", "small", "medium"):
        assert _MOONSHINE_ARCHES[name].endswith("STREAMING")


def test_resolve_device_prefers_an_explicit_device():
    assert resolve_device("respeaker", device=5) == 5
    assert resolve_device("respeaker", device="hw:2,0") == "hw:2,0"


def test_resolve_device_coerces_a_bare_numeric_index():
    # `--device 5` arrives as a string; an index must not degrade to the name "5".
    assert resolve_device("respeaker", device="5") == 5
    assert resolve_device("respeaker", device=" 12 ") == 12
    assert resolve_device("respeaker", device="hw:2,0") == "hw:2,0"


def _install_fake_sounddevice(monkeypatch, devices):
    module = types.SimpleNamespace(query_devices=lambda: devices)
    monkeypatch.setitem(sys.modules, "sounddevice", module)


def test_resolve_device_matches_by_name(monkeypatch):
    _install_fake_sounddevice(
        monkeypatch,
        [
            {"name": "HD-Audio Generic: ALC294 Analog (hw:1,0)", "max_input_channels": 2},
            {"name": "reSpeaker XVF3800 4-Mic Array: USB Audio (hw:2,0)", "max_input_channels": 2},
        ],
    )
    assert resolve_device("respeaker") == 1


def test_resolve_device_ignores_output_only_devices(monkeypatch):
    _install_fake_sounddevice(monkeypatch, [{"name": "reSpeaker Output", "max_input_channels": 0}])
    assert resolve_device("respeaker") is None


def test_resolve_device_without_a_hint_uses_the_default(monkeypatch):
    assert resolve_device(None) is None


def test_on_line_bridges_finished_lines_onto_the_queue():
    audio_in = AudioIn(model_arch="small")
    audio_in._on_line(types.SimpleNamespace(text="  the bread is done  ", duration=1.2))
    audio_in._on_line(types.SimpleNamespace(text="   ", duration=0.1))  # blank -> ignored
    assert audio_in._queue.get() == Utterance("the bread is done", 1.2)
    assert audio_in._queue.empty()


def test_unknown_model_arch_is_an_error():
    audio_in = AudioIn(model_arch="gigantic")
    with pytest.raises(AudioError) as excinfo:
        next(audio_in.lines())
    assert "gigantic" in str(excinfo.value)


def test_on_error_is_logged_as_a_warning(caplog):
    import logging

    audio_in = AudioIn(model_arch="small")
    with caplog.at_level(logging.WARNING, logger="voicebot.audio"):
        audio_in._on_error(RuntimeError("boom"))
    assert "speech-to-text error: boom" in caplog.text


def test_build_wires_on_error_and_releases_the_engine_when_start_fails(monkeypatch):
    """A `start()` failure after `load()` must not leak the microphone."""
    created: list = []

    class FakeMic:
        def __init__(self):
            created.append(self)
            self.calls: list = []
            self.closed = False

        def language(self, code):
            self.calls.append(("language", code))
            return self

        def model_arch(self, arch):
            self.calls.append(("model_arch", arch))
            return self

        def device(self, index):
            # Reached only when a real mic is visible (resolve_device finds one).
            self.calls.append(("device", index))
            return self

        def on_line(self, cb):
            self.calls.append(("on_line", cb))
            return self

        def on_error(self, cb):
            self.calls.append(("on_error", cb))
            return self

        def load(self):
            self.calls.append(("load",))
            return self

        def start(self):
            raise RuntimeError("no mic")

        def close(self):
            self.closed = True

    fake = types.SimpleNamespace(
        MicTranscriber=FakeMic,
        ModelArch=types.SimpleNamespace(SMALL_STREAMING=4),
    )
    monkeypatch.setitem(sys.modules, "moonshine_voice", fake)

    audio_in = AudioIn(model_arch="small")
    with pytest.raises(AudioError) as excinfo:
        next(audio_in.lines())

    assert "no mic" in str(excinfo.value)
    assert [m.closed for m in created] == [True]  # released on the way out
    calls = created[0].calls
    assert any(name == "on_error" for name, *_ in calls)  # error sink attached
    assert calls.index(("load",)) > calls.index(("on_error", audio_in._on_error))
