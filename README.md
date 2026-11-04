# voicebot

An eavesdropping desk robot: it listens to nearby conversation, asks a small
LLM for a witty one-liner, and scrolls that line across an addressable-LED
matrix. `voicebot` is the AI half of the parent repo's **creep3r** art project —
see [docs/led-art.md](../../docs/led-art.md) and the plan in
[docs/plans/initial.md](docs/plans/initial.md).

> Not ready for others yet. Today it's the **responder + listener**: text in,
> quip out (served by a remote [Ollama](https://ollama.com) server, no local
> model), optionally scrolled on a **touchy-pad** LED matrix / LCD.

## The name of the game

A small model asked to "tell me a joke" regurgitates memorised dad jokes. Wit
comes from a **persona baked into the system prompt** plus a **loosened
sampler** (`temperature=0.85`, `min_p=0.05`). The persona also defines a tiny
**command channel**: any word starting with `/` in the model's output is a
directive voicebot consumes (never displayed). `/notfunny` means "nothing worth
saying" (the reply is *suppressed* rather than showing a weak joke), and
`/color:NAME` colours the text — `red` / `green` / `blue` / `yellow` / `white`
or a `0xRRGGBB` hex, e.g. `/color:red Danger ahead`. All of that lives in
`src/voicebot/persona.py` + `src/voicebot/commands.py`.

## Quickstart

```sh
just install                                  # venv + deps

# One line:
just reply -- --line "the bread is done baking"

# A file of overheard lines (one per line):
just reply -- -f sim-overheard.txt

# What's on the server?
just models

# Listen to the mic (transcribe + witty reply, logged):
just listen

# Replay a file instead — no mic, no model:
just listen -- --fake sim-overheard.txt
```

Or use the console script directly: `poetry run voicebot reply -f sim-overheard.txt`.

## Commands

| Command | What it does |
|---|---|
| `voicebot reply` | Read overheard lines (`--line` / `-f FILE` / stdin) and print a witty reply for each (`--json` for `{input, reply, skip, model, raw}` per line). Commands are stripped from the printed text, so a `/notfunny` reply prints nothing. |
| `voicebot models` | List the models the server has pulled. |
| `voicebot listen` | Listen to the mic, transcribe with **Moonshine**, and log `HEARD:` / `SKIP(…)` / `REPLY:` per utterance; `--fake FILE` replays a text file instead (no mic, no model); `--display pad` also scrolls each quip on a touchy-pad. |

Configuration is **flag → env → default**:

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

## Listening (`voicebot listen`)

The audio-in half: open the mic, transcribe speech with **Moonshine Voice**
(streaming, CPU-only — the Raspberry Pi target), keep only utterances with at
least a few words, and ask the LLM for a quip — logging `HEARD:` / `SKIP(…)` /
`REPLY:` lines. Add `--display pad` to also **scroll the quip on a touchy-pad**
(see below).

The mic (a **reSpeaker XVF3800** USB array) is auto-selected by name, so
`--device` is only needed for a different input. The first run downloads a
Moonshine model into `~/.cache/moonshine_voice` and runs offline afterwards.

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

All the LLM flags (`--url` / `--model` / `--persona` / …) are shared with `reply`.

## The display (`voicebot listen --display pad`)

The LED-out half: voicebot builds **one** full-panel scrolling label on a
touchy-pad, then each quip is a single property write (no screen re-upload).
`/color:NAME` runs are rendered in colour via LVGL inline recolour — e.g.
`/color:red Danger ahead` scrolls "Danger ahead" in red. See the plan in
[docs/plans/ledout.md](docs/plans/ledout.md).

```sh
just listen-pad --fake sim-overheard.txt   # no mic, no model — just the display
```

(Args go straight after the recipe name — a `--` here would land *after* the
recipe's own `--display pad` and confuse click.)

* The panel shows **"I'm voicebot"** on connect, then the quips; after
  `--clear-after` seconds with nothing new it goes blank.
* The pad is opened **lazily** — plug it in at any time and the next quip lands
  on it. Nothing is fatal: no pad / an unplugged pad / an incompatible firmware
  all just log a warning and retry.
* Geometry (and the font size) come from the board's reported display size, so
  the same code drives an 8×8/32×8 LED matrix and a full-size LCD.
* A **fresh LED board is headless** (`0×0`) until its panel chain is provisioned:
  `touchy pref from-template led-32x8`. voicebot says so if it sees `0×0`.
* The screen is saved as `F:host/s/voicebot.pb` (`--screen-name` to change it) —
  deliberately *not* `default`, so `touchy init` can't clobber it.
* A quip is capped by the firmware's `SetPropertyCmd` string buffer: the current
  build allows **512** bytes; voicebot truncates to fit and, if the pad rejects a
  long quip (older firmware allowed only 127), retries shorter and logs a
  "re-flash" hint rather than dropping the message. Use `--max-tokens` to keep
  replies short if you prefer.

### The `touchy-pad` dependency

`voicebot` depends on the touchy-pad host library (a **path** dependency on the
sibling `../../app` checkout, like `tools/googly-vr`):

```sh
just use-touchy-local   # point at ../../app (the default)
just use-touchy-pypi    # point at the published package (once it exists)
```

Both rewrite `pyproject.toml` + `poetry.lock`; `git checkout pyproject.toml
poetry.lock` is the way back. Only `src/voicebot/display.py` imports
`touchy_pad`, so the eventual PyPI swap is a one-file diff.

## Dev

```sh
just test                 # pytest (network-free)
VOICEBOT_LIVE=1 just test # + one real request to the server
just lint                 # ruff format + check
```

## `launch-funny.sh`

Kept in-tree as the **local `llama.cpp` fallback / reference** this project was
ported from (its persona and sampler are the source of truth for
`src/voicebot/persona.py`). It needs a local `llama.cpp` build; `voicebot` needs
only network access to the Ollama server.

