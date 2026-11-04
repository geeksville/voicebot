"""CLI behaviour with a monkeypatched ChatClient — never touches the network."""

from __future__ import annotations

import json
from typing import ClassVar

from click.testing import CliRunner

from voicebot import cli


class FakeClient:
    """Stand-in for ``voicebot.server.ChatClient`` keyed by user line."""

    replies: ClassVar[dict[str, str]] = {}

    def __init__(self, settings):
        self.model = settings.model

    def chat(self, messages):
        return self.replies.get(messages[-1]["content"], "Time to toast!")

    def list_models(self):
        return ["hermes", "nemo"]


def _use_fake(monkeypatch, replies=None):
    FakeClient.replies = replies or {}
    monkeypatch.setattr(cli, "ChatClient", FakeClient)


def test_reply_line(monkeypatch):
    _use_fake(monkeypatch, {"the bread is done baking": "Time to toast!"})
    result = CliRunner().invoke(cli.main, ["reply", "--line", "the bread is done baking"])
    assert result.exit_code == 0
    assert result.output.strip() == "Time to toast!"


def test_reply_suppresses_notfunny(monkeypatch):
    _use_fake(monkeypatch, {"meer loves the new toy": "/notfunny"})
    result = CliRunner().invoke(cli.main, ["reply", "--line", "meer loves the new toy"])
    assert result.exit_code == 0
    assert result.output.strip() == ""


def test_reply_strips_commands_from_the_printed_text(monkeypatch):
    _use_fake(monkeypatch, {"the light is red": "/color:red Danger ahead"})
    result = CliRunner().invoke(cli.main, ["reply", "--line", "the light is red"])
    assert result.exit_code == 0
    assert result.output.strip() == "Danger ahead"


def test_reply_json_is_structural(monkeypatch):
    _use_fake(monkeypatch, {"x": "/notfunny"})
    result = CliRunner().invoke(cli.main, ["reply", "--line", "x", "--json"])
    assert json.loads(result.output) == {
        "input": "x",
        "reply": "",
        "skip": True,
        "model": cli.DEFAULT_MODEL,
        "raw": "/notfunny",
    }


def test_reply_reads_lines_from_file(monkeypatch, tmp_path):
    _use_fake(monkeypatch, {"a": "quip a", "b": "/notfunny", "c": "quip c"})
    lines = tmp_path / "overheard.txt"
    lines.write_text("a\n\nb\nc\n")  # blank line is dropped
    result = CliRunner().invoke(cli.main, ["reply", "-f", str(lines)])
    assert result.exit_code == 0
    assert result.output.splitlines() == ["quip a", "quip c"]


def test_reply_reads_stdin(monkeypatch):
    _use_fake(monkeypatch, {"a": "quip a"})
    result = CliRunner().invoke(cli.main, ["reply"], input="a\n")
    assert result.output.splitlines() == ["quip a"]


def test_models_lists_server_models(monkeypatch):
    _use_fake(monkeypatch)
    result = CliRunner().invoke(cli.main, ["models"])
    assert result.exit_code == 0
    assert result.output.splitlines() == ["hermes", "nemo"]


def test_version_option():
    result = CliRunner().invoke(cli.main, ["--version"])
    assert "voicebot" in result.output


def test_listen_fake_replays_utterances(monkeypatch, tmp_path):
    _use_fake(monkeypatch, {"the bread is done baking": "Time to toast!"})
    lines = tmp_path / "overheard.txt"
    lines.write_text("the bread is done baking\nuh\n")
    result = CliRunner().invoke(cli.main, ["listen", "--fake", str(lines), "--json"])
    assert result.exit_code == 0
    events = [json.loads(line) for line in result.output.splitlines() if line.strip()]
    assert [e["event"] for e in events].count("heard") == 2
    reply = next(e for e in events if e["event"] == "reply")
    assert reply["heard"] == "the bread is done baking"
    assert reply["reply"] == "Time to toast!"
    skip = next(e for e in events if e["event"] == "skip")
    assert skip["reason"] == "too_short"


def test_listen_fake_never_asks_about_short_utterances(monkeypatch, tmp_path):
    asked: list[str] = []

    class RecordingClient(FakeClient):
        def chat(self, messages):
            asked.append(messages[-1]["content"])
            return "quip"

    FakeClient.replies = {}
    monkeypatch.setattr(cli, "ChatClient", RecordingClient)
    lines = tmp_path / "overheard.txt"
    lines.write_text("uh\nhmm yeah\n")
    result = CliRunner().invoke(cli.main, ["listen", "--fake", str(lines), "--json"])
    assert result.exit_code == 0
    events = [json.loads(line) for line in result.output.splitlines() if line.strip()]
    assert events and all(e["event"] in ("heard", "skip") for e in events)
    assert not any(e["event"] == "reply" for e in events)
    assert asked == []


def test_listen_logs_heard_and_reply(monkeypatch, tmp_path, caplog):
    import logging

    _use_fake(monkeypatch, {"the bread is done baking": "Time to toast!"})
    lines = tmp_path / "overheard.txt"
    lines.write_text("the bread is done baking\n")
    with caplog.at_level(logging.INFO, logger="voicebot"):
        result = CliRunner().invoke(cli.main, ["listen", "--fake", str(lines)])
    assert result.exit_code == 0
    assert "HEARD: the bread is done baking" in caplog.text
    assert "REPLY: Time to toast!" in caplog.text
