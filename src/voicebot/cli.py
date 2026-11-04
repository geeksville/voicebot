"""The ``voicebot`` command line.

Two commands:

* ``voicebot reply`` — read overheard lines (``--line`` / ``-f FILE`` / stdin)
  and print a witty reply for each (commands stripped; ``/notfunny`` suppresses).
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
from .audio import AudioIn, FakeTranscriptSource, read_lines
from .config import (
    DEFAULT_CTX,
    DEFAULT_DEBOUNCE_S,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MIN_DURATION_S,
    DEFAULT_MIN_P,
    DEFAULT_MIN_WORDS,
    DEFAULT_MODEL,
    DEFAULT_MODEL_ARCH,
    DEFAULT_TEMPERATURE,
    DEFAULT_TIMEOUT,
    DEFAULT_URL,
    Settings,
)
from .display import DEFAULT_CLEAR_AFTER_S, SCREEN_NAME, PadDisplay
from .gate import UtteranceGate
from .listen import Listener, json_emitter
from .persona import DEFAULT_PERSONA
from .responder import Reply, Responder
from .server import ChatClient, VoicebotError

log = logging.getLogger(__name__)

#: The LLM/server options shared by ``reply`` and ``listen`` (flag → env →
#: default, via click). Applied by :func:`_llm_options` so the two commands
#: cannot drift apart.
_LLM_OPTIONS = [
    click.option("--url", default=DEFAULT_URL, envvar="VOICEBOT_URL", show_default=True),
    click.option("--model", default=DEFAULT_MODEL, envvar="VOICEBOT_MODEL", show_default=True),
    click.option(
        "--persona",
        default=DEFAULT_PERSONA,
        envvar="VOICEBOT_PERSONA",
        help="System prompt (persona / comedic mechanism).",
    ),
    click.option(
        "--persona-file",
        type=click.File("r", encoding="utf-8"),
        default=None,
        help="Read the persona from FILE (wins over --persona).",
    ),
    click.option(
        "--temperature",
        type=float,
        default=DEFAULT_TEMPERATURE,
        envvar="VOICEBOT_TEMP",
        show_default=True,
    ),
    click.option(
        "--min-p",
        "min_p",
        type=float,
        default=DEFAULT_MIN_P,
        envvar="VOICEBOT_MIN_P",
        show_default=True,
    ),
    click.option("--ctx", type=int, default=DEFAULT_CTX, envvar="VOICEBOT_CTX", show_default=True),
    click.option(
        "--max-tokens",
        type=int,
        default=DEFAULT_MAX_TOKENS,
        envvar="VOICEBOT_MAX_TOKENS",
        show_default=True,
    ),
    click.option(
        "--native",
        is_flag=True,
        default=False,
        envvar="VOICEBOT_NATIVE",
        help="Use Ollama's native /api/chat (exact sampler control).",
    ),
    click.option(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        envvar="VOICEBOT_TIMEOUT",
        show_default=True,
    ),
]


def _llm_options(fn):
    """Attach the shared :data:`_LLM_OPTIONS` decorators to *fn*."""
    for decorator in reversed(_LLM_OPTIONS):
        fn = decorator(fn)
    return fn


def _build_responder(
    *,
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
) -> Responder:
    """A :class:`Responder` wired to a live :class:`ChatClient`."""
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
    return Responder(client.chat, model=model, persona=persona)


def _make_display(kind: str, screen_name: str, clear_after_s: float) -> PadDisplay | None:
    """The display for ``--display`` (``None`` for ``off``), banner already shown.

    :class:`~voicebot.display.PadDisplay` only reaches for ``touchy_pad`` when it
    actually draws, so ``--display pad`` without the host library installed
    degrades to a logged warning rather than a crash.
    """
    if kind == "off":
        return None
    display = PadDisplay(screen_name=screen_name, clear_after=clear_after_s)
    display.start()  # the "I'm voicebot" banner (connects lazily)
    return display


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
@_llm_options
@click.option(
    "--json", "json_out", is_flag=True, default=False, help="Emit one JSON object per input line."
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
) -> None:
    """Ask the LLM for a witty reply to each overheard line."""
    responder = _build_responder(
        url=url,
        model=model,
        persona=persona,
        persona_file=persona_file,
        temperature=temperature,
        min_p=min_p,
        ctx=ctx,
        max_tokens=max_tokens,
        native=native,
        timeout=timeout,
    )
    try:
        for source in _input_lines(line, file):
            _emit(responder.respond(source), json_out)
    except VoicebotError as exc:
        click.echo(f"voicebot: {exc}", err=True)
        raise SystemExit(1) from exc


@main.command()
@click.option(
    "--fake",
    "fake",
    type=click.File("r", encoding="utf-8"),
    default=None,
    help="Replay utterances from FILE instead of the mic (no audio, no model).",
)
@click.option(
    "--device",
    default=None,
    envvar="VOICEBOT_MIC",
    help="Capture device (PortAudio index or name substring). Default: auto-detect the mic array.",
)
@click.option(
    "--model-arch",
    "model_arch",
    default=DEFAULT_MODEL_ARCH,
    envvar="VOICEBOT_MODEL_ARCH",
    show_default=True,
    help="STT model size: tiny|base|small|medium (all streaming).",
)
@click.option(
    "--min-words",
    "min_words",
    type=int,
    default=DEFAULT_MIN_WORDS,
    envvar="VOICEBOT_MIN_WORDS",
    show_default=True,
    help="Skip utterances with fewer than N content words (filler stripped).",
)
@click.option(
    "--min-duration",
    "min_duration_s",
    type=float,
    default=DEFAULT_MIN_DURATION_S,
    envvar="VOICEBOT_MIN_DURATION",
    show_default=True,
    help="Skip utterances shorter than N seconds (when the duration is known).",
)
@click.option(
    "--debounce",
    "debounce_s",
    type=float,
    default=DEFAULT_DEBOUNCE_S,
    envvar="VOICEBOT_DEBOUNCE",
    show_default=True,
    help="Suppress an identical repeat of the previous utterance within N seconds.",
)
@click.option(
    "--display",
    "display_kind",
    type=click.Choice(["off", "pad"]),
    default="off",
    show_default=True,
    help="Also scroll each quip on a touchy-pad (LED matrix or LCD).",
)
@click.option(
    "--screen-name",
    "screen_name",
    default=SCREEN_NAME,
    show_default=True,
    help="On-device screen name used for the display (F:host/s/<name>.pb).",
)
@click.option(
    "--clear-after",
    "clear_after_s",
    type=float,
    default=DEFAULT_CLEAR_AFTER_S,
    envvar="VOICEBOT_CLEAR_AFTER",
    show_default=True,
    help="Blank the display after N seconds with no new reply (0 = never).",
)
@_llm_options
@click.option(
    "--json", "json_out", is_flag=True, default=False, help="Emit one JSON event per line."
)
def listen(
    fake: TextIO | None,
    device: str | None,
    model_arch: str,
    min_words: int,
    min_duration_s: float,
    debounce_s: float,
    display_kind: str,
    screen_name: str,
    clear_after_s: float,
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
) -> None:
    """Listen to the mic, transcribe, and log a witty reply per utterance."""
    if not json_out:
        logging.getLogger("voicebot").setLevel(logging.INFO)
    responder = _build_responder(
        url=url,
        model=model,
        persona=persona,
        persona_file=persona_file,
        temperature=temperature,
        min_p=min_p,
        ctx=ctx,
        max_tokens=max_tokens,
        native=native,
        timeout=timeout,
    )
    gate = UtteranceGate(min_words=min_words, min_duration_s=min_duration_s, debounce_s=debounce_s)
    source = (
        FakeTranscriptSource(read_lines(fake))
        if fake is not None
        else AudioIn(device=device, model_arch=model_arch)
    )
    display = _make_display(display_kind, screen_name, clear_after_s)
    listener = Listener(
        responder,
        gate,
        emit=json_emitter if json_out else None,
        display=display.show if display is not None else None,
        inline=fake is not None,
    )
    try:
        listener.run(source)
    except VoicebotError as exc:
        click.echo(f"voicebot: {exc}", err=True)
        raise SystemExit(1) from exc
    except KeyboardInterrupt:  # pragma: no cover - interactive stop
        click.echo("voicebot: stopped.", err=True)
    finally:
        if display is not None:
            display.close()


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
