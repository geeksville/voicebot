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

#: Model default. Hermes-3-8B is the reliable choice for honouring the NOTFUNNY
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
