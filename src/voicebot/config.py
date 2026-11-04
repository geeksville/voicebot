"""Defaults and the ``Settings`` value object.

Config resolution is *CLI flag → environment variable → default*; click implements
that precedence for us (``default=`` + ``envvar=`` on every option), so this
module only owns the default values and the frozen dataclass they feed.

Env names mirror ``launch-funny.sh``'s ``TOUCHY_BOT_*`` but are rebranded
``VOICEBOT_*`` (the repo is finally called voicebot). The script's
``TOUCHY_BOT_NGL`` — GPU layers to offload — has no remote analogue and is
dropped.
"""

from __future__ import annotations

from dataclasses import dataclass

#: The remote Ollama server (Tailscale; verified 2026-11-04, Ollama 0.40.14).
DEFAULT_URL = "https://kai.pygmy-map.ts.net"

#: Model default. Hermes-3-8B is the reliable choice for honouring the /notfunny
#: contract; the funnier-but-more-erratic Human-Like Mistral Nemo (12B, Q8_0) is
#: one flag away: ``--model hf.co/bartowski/Human-Like-Mistral-Nemo-Instruct-2407-GGUF:Q8_0``.
DEFAULT_MODEL = "hf.co/NousResearch/Hermes-3-Llama-3.1-8B-GGUF:latest"

#: Loosened sampler — the launch-funny.sh lesson: wit needs creative word choice.
DEFAULT_TEMPERATURE = 0.85
DEFAULT_MIN_P = 0.05
DEFAULT_CTX = 4096
DEFAULT_MAX_TOKENS = 120

#: HTTP timeout (seconds). Generous: a cold 12B+ model can take a while to load.
DEFAULT_TIMEOUT = 120.0


@dataclass(frozen=True)
class Settings:
    """Everything the :class:`~voicebot.server.ChatClient` needs to talk to the server."""

    url: str = DEFAULT_URL
    model: str = DEFAULT_MODEL
    temperature: float = DEFAULT_TEMPERATURE
    min_p: float = DEFAULT_MIN_P
    ctx: int = DEFAULT_CTX
    max_tokens: int = DEFAULT_MAX_TOKENS
    native: bool = False
    timeout: float = DEFAULT_TIMEOUT


# ---------------------------------------------------------------------------
# Audio in (the "listen" stage) — see docs/plans/audioin.md
# ---------------------------------------------------------------------------

#: Case-insensitive substring of the capture device name to auto-select. The
#: reSpeaker XVF3800 shows up as e.g. "reSpeaker XVF3800 4-Mic Array: USB Audio
#: (hw:2,0)", so a short hint finds it whatever PortAudio index it lands on.
DEFAULT_MIC_HINT = "respeaker"

#: Moonshine streaming model size: tiny (34M) | base | small (123M) | medium
#: (245M). Small is the Pi-friendly default; see the plan's Q2.
DEFAULT_MODEL_ARCH = "small"

#: Answer only utterances with at least this many *content* words (filler
#: stripped) — "a text snippet of at least a few words" (plan Q3).
DEFAULT_MIN_WORDS = 3

#: Also ignore utterances shorter than this many seconds (when the duration is
#: known; the --fake replay has none).
DEFAULT_MIN_DURATION_S = 0.6

#: Suppress an utterance identical to the previous one within this many seconds
#: (plan Q9).
DEFAULT_DEBOUNCE_S = 5.0


@dataclass(frozen=True)
class AudioSettings:
    """Everything the ``listen`` stage's capture + gate needs."""

    device: int | str | None = None
    mic_hint: str | None = DEFAULT_MIC_HINT
    model_arch: str = DEFAULT_MODEL_ARCH
    min_words: int = DEFAULT_MIN_WORDS
    min_duration_s: float = DEFAULT_MIN_DURATION_S
    debounce_s: float = DEFAULT_DEBOUNCE_S
