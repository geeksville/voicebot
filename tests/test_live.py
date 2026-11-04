"""Opt-in smoke test against the real remote server.

Skipped unless ``VOICEBOT_LIVE=1`` is set, so CI stays network-free. Run with:

    VOICEBOT_LIVE=1 just test
"""

from __future__ import annotations

import os

import pytest

from voicebot.config import Settings
from voicebot.responder import Responder
from voicebot.server import ChatClient

pytestmark = pytest.mark.live

_LIVE = os.environ.get("VOICEBOT_LIVE") == "1"


@pytest.mark.skipif(not _LIVE, reason="set VOICEBOT_LIVE=1 to hit the remote server")
def test_remote_server_answers():
    client = ChatClient(Settings())
    responder = Responder(client.chat, model=client.model)
    reply = responder.respond("the bread is done baking")
    assert not reply.skip
    assert reply.text
