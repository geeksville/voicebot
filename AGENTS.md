# voicebot — AI agent guide

`CLAUDE.md` is a symlink to this file — keep them in sync via the symlink.

`voicebot` is an eavesdropping desk robot: it listens to nearby conversation,
asks a small LLM (a remote [Ollama] server) for a witty one-liner, and scrolls
that line across an addressable-LED matrix (a [touchy-pad]). It is the AI half
of the **creep3r** art project. This repo is standalone: it depends on the
*published* `touchy-pad` package, not the touchy-pad source tree.

[Ollama]: https://ollama.com
[touchy-pad]: https://github.com/geeksville/touchy-pad

## Repo layout

| Path | Purpose |
|------|---------|
| `src/voicebot/cli.py` | `click` CLI: `reply` / `models` / `listen`. |
| `src/voicebot/server.py` | `ChatClient` (OpenAI `/v1` + native `/api/chat`) + `VoicebotError`. |
| `src/voicebot/responder.py` | Persona → prompt → reply, and the reply value object. |
| `src/voicebot/persona.py` | The default persona (the toaster robot). |
| `src/voicebot/commands.py` | The `/command` channel (`/notfunny`, `/color:NAME`). |
| `src/voicebot/audio.py` | Mic capture + Moonshine STT (the audio-in stage). |
| `src/voicebot/gate.py` | The utterance gate (min words, de-dup). |
| `src/voicebot/listen.py` | The listen loop wiring the above together. |
| `src/voicebot/display.py` | The **only** module that imports `touchy_pad` (the LED-out stage). |
| `src/voicebot/config.py` | Defaults + the `Settings` value objects. |
| `tests/` | pytest (network-free; audio + touchy-pad are faked). |
| `docs/` | `plans/` (design), `hardware.md`, `TODO.md`. |
| `justfile` | All dev tasks — prefer `just <recipe>`. |
| `.agents/skills/moonshine-voice/` | The Moonshine Voice SDK cheat-sheet. |

## Build / test / run

This project uses **Poetry** (never uv/uvx). Everything goes through `just`:

```bash
just install               # venv + deps
just test                  # pytest (network-free)
VOICEBOT_LIVE=1 just test  # + a real request to the server / the mic
just lint                  # ruff format + check
just build                 # wheel + sdist into dist/
just reply -- --line "..."  # run the CLI in the venv
just listen -- --fake sim-overheard.txt
just bump-version          # bump version, commit, tag, push
```

`uvx <tool>` → `poetry run <tool>`; `uv add <pkg>` → `poetry add <pkg>`.

## Conventions & gotchas

- **Keep `touchy_pad` imports inside `display.py`, and lazy** (inside the
  functions). That is what lets the whole package + test suite run with no
  touchy-pad and no hardware.
- **`touchy-pad` floor is `>= 0.3.8`** — the first release with the host API
  `--display pad` needs (`SetPropertiesCmd` / `build_property_override` +
  `Label.recolor` arrived in 0.3.5; 0.3.8 added `Label.scroll_speed_px_s`, the
  marquee-speed knob `display.py` uses to slow the scroll to
  `DEFAULT_SCROLL_SPEED_PX_S`). Older releases break the display path and its
  tests. Until a suitable version is on PyPI, resolve it with
  `just use-touchy-local` (a path dep on the sibling `../../app` tree).
- **Keep `moonshine_voice` / `sounddevice` imports lazy** too (inside
  `AudioIn._build()` / `resolve_device()`), so importing `voicebot` never needs
  the native libs — and CI needs no mic.
- **Logging:** `logging.getLogger(__name__)`; the CLI configures the `voicebot`
  logger. High-frequency RPC-ish lines go on a child logger.
- **The `/command` contract** lives in `commands.py`; commands are stripped from
  every displayed/printed reply. Keep `/notfunny` as the final backstop.
- **Config is flag → env → default** via click (`default=` + `envvar=`); a new
  setting gets a `DEFAULT_*` in `config.py` and a `VOICEBOT_*` env name.
- **No network in tests.** The `ChatClient` is injected/monkeypatched
  everywhere; live checks are opt-in behind `VOICEBOT_LIVE=1`.
- Version is single-sourced in `pyproject.toml` + `src/voicebot/__init__.py`;
  bump both with `just bump-version` (never hand-edit one of them).

## Hardware

- Mic: Seeed **reSpeaker XVF3800** USB 4-mic array (`docs/hardware.md`). It does
  its own AEC/beamforming/noise-suppression, but *VAD runs host-side* in
  Moonshine, so the code is mic-agnostic.
- Display: a [touchy-pad] board (LED matrix or LCD) over USB — boards/firmware
  live in the touchy-pad project.
- Audio in the devcontainer: `/dev/snd` is bind-mounted from the host and
  `PULSE_SERVER` points at the host's PipeWire (see `.devcontainer/`).

## Release

`just bump-version [X.Y.Z]` bumps the patch version, commits, tags `vX.Y.Z` and
pushes. Publishing a GitHub Release then triggers
`.github/workflows/release.yml`, which tests, builds, and publishes
`touchy-voicebot` to PyPI via OIDC trusted publishing. `testpypi.yml` is a manual
dry-run to TestPyPI.

## Working with this repo (agent rules)

- **Never auto-commit or push.** Make the edits; the human commits. (This
  includes `just bump-version`, which commits/tags/pushes — treat it as a human
  action.)
- Plans live in `docs/plans/*.md`; keep them there, not in chat. See
  `.clinerules/` for the full rules (collaboration, terminal, plans, searching).
