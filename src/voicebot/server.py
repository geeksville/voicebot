"""The only module that talks to the network.

Two surfaces are supported against the remote Ollama server:

* the **OpenAI-compatible** ``/v1`` API (default) — portable to any OpenAI-ish
  server (vLLM, a llama.cpp ``llama serve``, …). Ollama-specific sampler knobs
  ride along in an ``options`` object via ``extra_body``;
* Ollama's **native** ``/api/chat`` (``--native``) — needed when a knob such as
  ``min_p`` must be honoured *exactly* (``/v1`` may silently drop it).

Every failure — bad URL, timeout, HTTP error — is normalised to
:class:`VoicebotError` so the CLI has one thing to catch.
"""

from __future__ import annotations

import logging

import requests
from openai import OpenAI

from .config import Settings

log = logging.getLogger(__name__)


class VoicebotError(RuntimeError):
    """Anything that stops us getting a reply from the model server."""


class ChatClient:
    """A thin wrapper around the server, configured by a :class:`Settings`."""

    def __init__(self, settings: Settings) -> None:
        self._s = settings
        #: Exposed so callers can stamp it onto each :class:`~voicebot.responder.Reply`.
        self.model = settings.model

    # -- chat --------------------------------------------------------------

    def chat(self, messages: list[dict[str, str]]) -> str:
        """Return the assistant text for *messages* (OpenAI chat shape)."""
        if self._s.native:
            return self._chat_native(messages)
        return self._chat_openai(messages)

    def _chat_openai(self, messages: list[dict[str, str]]) -> str:
        client = OpenAI(
            base_url=f"{self._s.url}/v1",
            api_key="ollama",  # required by the SDK; ignored by Ollama
            timeout=self._s.timeout,
        )
        try:
            resp = client.chat.completions.create(
                model=self._s.model,
                messages=messages,
                temperature=self._s.temperature,
                max_tokens=self._s.max_tokens,
                # Ollama forwards these; non-Ollama servers ignore them.
                extra_body={"options": {"min_p": self._s.min_p, "num_ctx": self._s.ctx}},
            )
        except Exception as exc:
            raise VoicebotError(f"{type(exc).__name__}: {exc}") from exc
        return resp.choices[0].message.content or ""

    def _chat_native(self, messages: list[dict[str, str]]) -> str:
        payload = {
            "model": self._s.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": self._s.temperature,
                "min_p": self._s.min_p,
                "num_ctx": self._s.ctx,
                "num_predict": self._s.max_tokens,
            },
        }
        try:
            resp = requests.post(f"{self._s.url}/api/chat", json=payload, timeout=self._s.timeout)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            raise VoicebotError(f"{type(exc).__name__}: {exc}") from exc
        return data.get("message", {}).get("content", "") or ""

    # -- models ------------------------------------------------------------

    def list_models(self) -> list[str]:
        """The model names the server currently has pulled."""
        if self._s.native:
            return self._models_native()
        return self._models_openai()

    def _models_openai(self) -> list[str]:
        client = OpenAI(base_url=f"{self._s.url}/v1", api_key="ollama", timeout=self._s.timeout)
        try:
            return [m.id for m in client.models.list().data]
        except Exception as exc:
            raise VoicebotError(f"{type(exc).__name__}: {exc}") from exc

    def _models_native(self) -> list[str]:
        try:
            resp = requests.get(f"{self._s.url}/api/tags", timeout=self._s.timeout)
            resp.raise_for_status()
            return [m["name"] for m in resp.json().get("models", [])]
        except Exception as exc:
            raise VoicebotError(f"{type(exc).__name__}: {exc}") from exc
