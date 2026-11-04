# voicebot

An **eavesdropping desk robot**: it listens to nearby conversation, asks a small
LLM for a witty one-liner, and scrolls that line across an addressable-LED
matrix.

`voicebot` is the AI half of the **creep3r** art project — the pendant LED
pillar that overhears, quips, and scrolls. It runs on a Raspberry-Pi-class box,
with a USB mic for ears and a [touchy-pad] display (an LED matrix, or any
touchy-pad LCD) for a mouth, and it reaches out to a remote [Ollama] server for
the wit — no local GPU required.

[touchy-pad]: https://github.com/geeksville/touchy-pad
[Ollama]: https://ollama.com

> **Status: early.** Today this is the **responder + listener**: text (or
> speech) in, quip out — served by a remote Ollama server (no local model),
> optionally scrolled on a **touchy-pad**. Speech-to-text runs locally with
> **Moonshine Voice**. The full creep3r loop (an always-on service that
> reconnects the pad and the server) is still ahead — see
> [docs/plans/](docs/plans/).

## How it works

```
   [ people talking nearby ]
             |
             v
   [ mic + VAD + STT ]         Moonshine Voice — on-device, CPU-only
             |  text, one utterance at a time
             v
   [ utterance gate ]          >= a few content words, de-duplicated
             |
             v
   [ voicebot responder ]      a witty line via a remote Ollama LLM
             |  a one-to-two-sentence quip, or /notfunny
             v
   [ touchy-pad display ]      a scrolling label on an LED matrix / LCD
```

Two halves, usable independently:

* **Audio in** (`voicebot listen`) — mic -> transcript -> gate -> LLM, logging
  `HEARD:` / `SKIP(...)` / `REPLY:` per utterance.
* **LED out** (`voicebot listen --display pad`) — each quip is a *single*
  property write that scrolls across a touchy-pad; no screen re-upload.

## Install

Requires **Python 3.11-3.14**.

```sh
pip install touchy-voicebot          # or:  pipx install touchy-voicebot
```

That pulls the [`touchy-pad`](https://pypi.org/project/touchy-pad/) host library
(**>= 0.3.5**) from PyPI for the `--display pad` output. The LLM / STT half needs
no touchy-pad at all. `--display pad` relies on a recent touchy-pad host API
(`SetPropertiesCmd` / `build_property_override` + inline-recolour labels); if the
published version is older than 0.3.5, install the git `main` or build the host
library and use [Dev](#dev)'s `just use-touchy-local`.

You also need a reachable **Ollama** server — a local `ollama serve`, or a
remote box over Tailscale / LAN. Point `--url` / `VOICEBOT_URL` at it. On first
use, Moonshine downloads its STT model into `~/.cache/moonshine_voice` and runs
offline afterwards.

For the mic you want a real USB array (the Seeed reSpeaker XVF3800 is what this
was built against — see [docs/hardware.md](docs/hardware.md)); it is auto-selected
by name, so `--device` is only needed for a different input.

## Quickstart

```sh
# One line:
voicebot reply --line "the bread is done baking"

# A file of overheard lines (one per line):
voicebot reply -f sim-overheard.txt

# What's pulled on the server?
voicebot models

# Listen to the mic (transcribe + witty reply, logged):
voicebot listen

# Replay a file instead — no mic, no model:
voicebot listen --fake sim-overheard.txt

# ... and scroll each quip on a touchy-pad:
voicebot listen --display pad --fake sim-overheard.txt
```

## Commands

| Command | What it does |
|---|---|
| `voicebot reply` | Read overheard lines (`--line` / `-f FILE` / stdin) and print a witty reply for each (`--json` for `{input, reply, skip, model, raw}` per line). Commands are stripped from the printed text, so a `/notfunny` reply prints nothing. |
| `voicebot models` | List the models the server has pulled. |
| `voicebot listen` | Listen to the mic, transcribe with **Moonshine**, and log `HEARD:` / `SKIP(...)` / `REPLY:` per utterance; `--fake FILE` replays a text file instead (no mic, no model); `--display pad` also scrolls each quip on a touchy-pad. |

Configuration is **flag -> env -> default** — click implements the precedence:

| Setting | Flag | Env | Default |
|---|---|---|---|
| Server URL | `--url` | `VOICEBOT_URL` | `https://kai.pygmy-map.ts.net` |
| Model | `--model` | `VOICEBOT_MODEL` | Hermes-3-Llama-3.1-8B |
| Persona | `--persona` / `--persona-file` | `VOICEBOT_PERSONA` | the toaster robot |
| Temperature | `--temperature` | `VOICEBOT_TEMP` | `0.85` |
| min-p | `--min-p` | `VOICEBOT_MIN_P` | `0.05` |
| Context | `--ctx` | `VOICEBOT_CTX` | `4096` |
| Max output tokens | `--max-tokens` | `VOICEBOT_MAX_TOKENS` | `120` |
| Native `/api/chat` | `--native` | `VOICEBOT_NATIVE` | off (use `/v1`) |

Try the funnier-but-more-erratic 12B model:
`--model hf.co/bartowski/Human-Like-Mistral-Nemo-Instruct-2407-GGUF:Q8_0`.

## The name of the game

A small model asked to "tell me a joke" regurgitates memorised dad jokes. Wit
comes from a **persona baked into the system prompt** plus a **loosened
sampler** (`temperature=0.85`, `min_p=0.05`). The persona also defines a tiny
**command channel**: any word starting with `/` in the model's output is a
directive voicebot consumes — and never displays.

* `/notfunny` — "nothing worth saying": the reply is *suppressed* rather than
  showing a weak joke.
* `/color:NAME` — colour the text — `red` / `green` / `blue` / `yellow` /
  `white`, or a `0xRRGGBB` hex, e.g. `/color:red Danger ahead`.

All of that lives in [`src/voicebot/persona.py`](src/voicebot/persona.py) and
[`src/voicebot/commands.py`](src/voicebot/commands.py).

## Listening (`voicebot listen`)

The audio-in half: open the mic, transcribe speech with **Moonshine Voice**
(streaming, CPU-only — the Raspberry Pi target), keep only utterances with at
least a few content words, and ask the LLM for a quip, logging `HEARD:` /
`SKIP(...)` / `REPLY:` lines. Add `--display pad` to also scroll the quip on a
touchy-pad.

| Setting | Flag | Env | Default |
|---|---|---|---|
| Capture device | `--device` | `VOICEBOT_MIC` | auto (name ~ `respeaker`) |
| STT model size | `--model-arch` | `VOICEBOT_MODEL_ARCH` | `small` (tiny/base/small/medium) |
| Min content words | `--min-words` | `VOICEBOT_MIN_WORDS` | `3` |
| Min duration (s) | `--min-duration` | `VOICEBOT_MIN_DURATION` | `0.6` |
| Repeat debounce (s) | `--debounce` | `VOICEBOT_DEBOUNCE` | `5.0` |
| Replay instead of the mic | `--fake FILE` | — | off |
| JSON events | `--json` | — | off |
| Scroll on a touchy-pad | `--display` | — | `off` (`pad` to enable) |
| On-device screen name | `--screen-name` | — | `voicebot` |
| Blank after quiet (s) | `--clear-after` | `VOICEBOT_CLEAR_AFTER` | `120` (`0` = never) |

All the LLM flags (`--url` / `--model` / `--persona` / ...) are shared with
`reply`.

## The display (`voicebot listen --display pad`)

The LED-out half: voicebot builds **one** full-panel scrolling label on a
touchy-pad, then each quip is a single property write (no screen re-upload).
`/color:NAME` runs are rendered in colour via LVGL inline recolour — e.g.
`/color:red Danger ahead` scrolls "Danger ahead" in red. See the plan in
[docs/plans/ledout.md](docs/plans/ledout.md).

* The panel shows **"I'm voicebot"** on connect, then the quips; after
  `--clear-after` seconds with nothing new it goes blank.
* The pad is opened **lazily** — plug it in at any time and the next quip lands
  on it. Nothing is fatal: no pad / an unplugged pad / an incompatible firmware
  all just log a warning and retry.
* Geometry (and the font size) come from the board's reported display size, so
  the same code drives an 8x8 / 32x8 LED matrix and a full-size LCD.
* A **fresh LED board is headless** (`0x0`) until its panel chain is
  provisioned: `touchy pref from-template led-32x8`. voicebot says so if it sees
  `0x0`.
* The screen is saved as `F:host/s/voicebot.pb` (`--screen-name` to change it) —
  deliberately *not* `default`, so `touchy init` can't clobber it.
* A quip is capped by the firmware's `SetPropertyCmd` string buffer — a 512-byte
  nanopb field, i.e. **511 characters** (the terminator is counted); voicebot
  truncates a longer reply to fit, so a chatty model can't overflow it. Use
  `--max-tokens` to keep replies short if you prefer.

## Dev

```sh
just install              # venv + deps
just test                 # pytest (network-free)
VOICEBOT_LIVE=1 just test # + one real request to the server / the mic
just lint                 # ruff format + check
just build                # wheel + sdist into dist/
just bump-version         # bump version, commit, tag, push (then release on GitHub)
```

The devcontainer (`.devcontainer/`) ships Python, Poetry, just, libusb (for the
touchy-pad USB transport) and ALSA / PortAudio (for the mic) — open it in VS Code
and `just test` works. By default the `touchy-pad` dependency is the **published
PyPI package**; `just use-touchy-local` swaps in a sibling `../../app` checkout
while hacking on the host library itself (`just use-touchy-pypi` puts it back).

Only [`src/voicebot/display.py`](src/voicebot/display.py) imports `touchy_pad`,
and it does so lazily, so the rest of voicebot (and the whole test suite) runs
with no touchy-pad and no hardware.

## Contributing

you probably don't want this yet.

I'm okay with using AI tools to help make code — I used them a fair amount on
this project (one of my first experiments with not writing all my code "by
hand"). But some of my other open-source projects have shown me the current hell
that PR management is becoming, so I'd **love** any contributions (and I promise
to be kind), with two asks:

* Send only PRs **you** are willing to sign off as "nicely written" (with your
own experience as a software engineer). If your little AI buddy made something a
bit ugly, iterate with it until it isn't.
* Keep PRs fairly **atomic** — touch just the code a single, nicely defined
  feature or bug-fix needs.
* Only send **tested** code you've run against real hardware (not just the
  simulator).

## `launch-funny.sh`

Kept in-tree as the **local `llama.cpp` fallback / reference** this project was
ported from (its persona and sampler are the source of truth for
`src/voicebot/persona.py`). It needs a local `llama.cpp` build; `voicebot` itself
needs only network access to the Ollama server.

## License

GPL-3.0-or-later — see [LICENSE](LICENSE).
