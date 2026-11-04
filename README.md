# voicebot

An eavesdropping desk robot: it listens to nearby conversation, asks a small
LLM for a witty one-liner, and (soon) scrolls that line across an addressable-LED
matrix. `voicebot` is the AI half of the parent repo's **creep3r** art project —
see [docs/led-art.md](../../docs/led-art.md) and the plan in
[docs/plans/initial.md](docs/plans/initial.md).

> Not ready for others yet. Today it's the **responder**: text in, quip out,
> served by a remote [Ollama](https://ollama.com) server (no local model).

## The name of the game

A small model asked to "tell me a joke" regurgitates memorised dad jokes. Wit
comes from a **persona baked into the system prompt** plus a **loosened
sampler** (`temperature=0.85`, `min_p=0.05`). And when the model has nothing
worth saying it answers `NOTFUNNY`, which the responder *suppresses* rather than
showing a weak joke. All of that lives in one place (`src/voicebot/persona.py`).

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
| `voicebot reply` | Read overheard lines (`--line` / `-f FILE` / stdin) and print a witty reply for each; `--json` for `{input, reply, skip, model}` per line; `--no-notfunny` to print the raw sentinel. |
| `voicebot models` | List the models the server has pulled. |
| `voicebot listen` | Listen to the mic, transcribe with **Moonshine**, and log `HEARD:` / `SKIP(…)` / `REPLY:` per utterance; `--fake FILE` replays a text file instead (no mic, no model). |

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
`REPLY:` lines. Display is still future work; the log lines *are* the output.

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

All the LLM flags (`--url` / `--model` / `--persona` / …) are shared with `reply`.

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

