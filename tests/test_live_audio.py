"""Opt-in live check that the real mic + model can start and stop.

Skipped unless ``VOICEBOT_LIVE=1`` (it opens the microphone and, on first run,
downloads a Moonshine model — so it needs hardware and network). Run with:

    VOICEBOT_LIVE=1 just test

Set ``VOICEBOT_TEST_ARCH`` to pick the model size (default ``tiny``, the
smallest/fastest to fetch).
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.live

_LIVE = os.environ.get("VOICEBOT_LIVE") == "1"


@pytest.mark.skipif(not _LIVE, reason="set VOICEBOT_LIVE=1 (needs the mic + a model download)")
def test_mic_opens_and_the_engine_starts():
    from voicebot.audio import AudioIn

    audio_in = AudioIn(model_arch=os.environ.get("VOICEBOT_TEST_ARCH", "tiny"))
    audio_in._mic = audio_in._build()  # opens the device, loads + starts the model
    assert audio_in._mic is not None
    audio_in.close()  # releases the device cleanly
