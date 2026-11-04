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
    _use_fake(monkeypatch, {"meer loves the new toy": "NOTFUNNY"})
    result = CliRunner().invoke(cli.main, ["reply", "--line", "meer loves the new toy"])
    assert result.exit_code == 0
    assert result.output.strip() == ""


def test_reply_no_notfunny_prints_raw(monkeypatch):
    _use_fake(monkeypatch, {"x": "NOTFUNNY"})
    result = CliRunner().invoke(cli.main, ["reply", "--line", "x", "--no-notfunny"])
    assert result.output.strip() == "NOTFUNNY"


def test_reply_json_is_structural(monkeypatch):
    _use_fake(monkeypatch, {"x": "NOTFUNNY"})
    result = CliRunner().invoke(cli.main, ["reply", "--line", "x", "--json"])
    assert json.loads(result.output) == {
        "input": "x",
        "reply": "",
        "skip": True,
        "model": cli.DEFAULT_MODEL,
    }


def test_reply_reads_lines_from_file(monkeypatch, tmp_path):
    _use_fake(monkeypatch, {"a": "quip a", "b": "NOTFUNNY", "c": "quip c"})
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
