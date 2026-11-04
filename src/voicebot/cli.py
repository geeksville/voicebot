"""The ``voicebot`` command line.

Two commands:

* ``voicebot reply`` — read overheard lines (``--line`` / ``-f FILE`` / stdin)
  and print a witty reply for each, suppressing ``NOTFUNNY`` answers.
* ``voicebot models`` — list the models the server has pulled.

Config resolution is *flag → env → default*, implemented via click's
``default=`` + ``envvar=`` (see :mod:`voicebot.config`). The chat client is
looked up as the module global ``ChatClient`` so tests can monkeypatch it.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import TextIO

import click

from . import __version__
from .config import (
    DEFAULT_CTX,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MIN_P,
    DEFAULT_MODEL,
    DEFAULT_TEMPERATURE,
    DEFAULT_TIMEOUT,
    DEFAULT_URL,
    Settings,
)
from .persona import DEFAULT_PERSONA
from .responder import Reply, Responder
from .server import ChatClient, VoicebotError

log = logging.getLogger(__name__)


@click.group()
@click.version_option(__version__, prog_name="voicebot")
def main() -> None:
    """Witty one-liners about overheard conversation, via a remote LLM."""
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")


@main.command()
@click.option("--line", default=None, help="A single overheard line to respond to (one-shot).")
@click.option(
    "-f",
    "--file",
    "file",
    type=click.File("r", encoding="utf-8"),
    default=None,
    help="Read overheard lines from FILE (one per line). Defaults to stdin.",
)
@click.option("--url", default=DEFAULT_URL, envvar="VOICEBOT_URL", show_default=True)
@click.option("--model", default=DEFAULT_MODEL, envvar="VOICEBOT_MODEL", show_default=True)
@click.option(
    "--persona",
    default=DEFAULT_PERSONA,
    envvar="VOICEBOT_PERSONA",
    help="System prompt (persona / comedic mechanism).",
)
@click.option(
    "--persona-file",
    type=click.File("r", encoding="utf-8"),
    default=None,
    help="Read the persona from FILE (wins over --persona).",
)
@click.option(
    "--temperature",
    type=float,
    default=DEFAULT_TEMPERATURE,
    envvar="VOICEBOT_TEMP",
    show_default=True,
)
@click.option(
    "--min-p",
    "min_p",
    type=float,
    default=DEFAULT_MIN_P,
    envvar="VOICEBOT_MIN_P",
    show_default=True,
)
@click.option("--ctx", type=int, default=DEFAULT_CTX, envvar="VOICEBOT_CTX", show_default=True)
@click.option(
    "--max-tokens",
    type=int,
    default=DEFAULT_MAX_TOKENS,
    envvar="VOICEBOT_MAX_TOKENS",
    show_default=True,
)
@click.option(
    "--native",
    is_flag=True,
    default=False,
    envvar="VOICEBOT_NATIVE",
    help="Use Ollama's native /api/chat (exact sampler control).",
)
@click.option(
    "--timeout", type=float, default=DEFAULT_TIMEOUT, envvar="VOICEBOT_TIMEOUT", show_default=True
)
@click.option(
    "--json", "json_out", is_flag=True, default=False, help="Emit one JSON object per input line."
)
@click.option(
    "--no-notfunny",
    is_flag=True,
    default=False,
    help="Print the raw NOTFUNNY token instead of suppressing it.",
)
def reply(
    line: str | None,
    file: TextIO | None,
    url: str,
    model: str,
    persona: str,
    persona_file: TextIO | None,
    temperature: float,
    min_p: float,
    ctx: int,
    max_tokens: int,
    native: bool,
    timeout: float,
    json_out: bool,
    no_notfunny: bool,
) -> None:
    """Ask the LLM for a witty reply to each overheard line."""
    if persona_file is not None:
        persona = persona_file.read()
    settings = Settings(
        url=url,
        model=model,
        temperature=temperature,
        min_p=min_p,
        ctx=ctx,
        max_tokens=max_tokens,
        native=native,
        timeout=timeout,
    )
    client = ChatClient(settings)
    responder = Responder(client.chat, model=model, persona=persona, notfunny=not no_notfunny)
    try:
        for source in _input_lines(line, file):
            _emit(responder.respond(source), json_out)
    except VoicebotError as exc:
        click.echo(f"voicebot: {exc}", err=True)
        raise SystemExit(1) from exc


@main.command()
@click.option("--url", default=DEFAULT_URL, envvar="VOICEBOT_URL", show_default=True)
@click.option("--native", is_flag=True, default=False, envvar="VOICEBOT_NATIVE")
@click.option(
    "--timeout", type=float, default=DEFAULT_TIMEOUT, envvar="VOICEBOT_TIMEOUT", show_default=True
)
def models(url: str, native: bool, timeout: float) -> None:
    """List the models the server has pulled."""
    settings = Settings(url=url, model="", native=native, timeout=timeout)
    try:
        for name in ChatClient(settings).list_models():
            click.echo(name)
    except VoicebotError as exc:
        click.echo(f"voicebot: {exc}", err=True)
        raise SystemExit(1) from exc


def _input_lines(line: str | None, file: TextIO | None) -> list[str]:
    """The overheard lines to answer: ``--line``, else *file*, else stdin.

    Blank lines are dropped; surrounding whitespace is trimmed.
    """
    if line is not None:
        return [line]
    stream = file if file is not None else sys.stdin
    return [stripped for raw in stream if (stripped := raw.strip())]


def _emit(reply: Reply, json_out: bool) -> None:
    """Print a reply — suppressed ones stay silent unless ``--json``."""
    if json_out:
        click.echo(json.dumps(reply.as_dict()))
    elif not reply.skip:
        click.echo(reply.text)


if __name__ == "__main__":  # pragma: no cover
    main()
