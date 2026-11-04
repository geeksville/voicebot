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
```

Or use the console script directly: `poetry run voicebot reply -f sim-overheard.txt`.

## Commands

| Command | What it does |
|---|---|
| `voicebot reply` | Read overheard lines (`--line` / `-f FILE` / stdin) and print a witty reply for each; `--json` for `{input, reply, skip, model}` per line; `--no-notfunny` to print the raw sentinel. |
| `voicebot models` | List the models the server has pulled. |

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

