# voicebot — plan for the early days

An eavesdropping desk robot: it listens to nearby conversation, decides whether
something said is worth riffing on, asks a small LLM for a witty one-liner, and
scrolls that line across an addressable-LED matrix. `voicebot` is the *AI half*
of the parent repo's **creep3r** art project
([docs/led-art.md](../../../../docs/led-art.md)); this repo is a git submodule
of `touchy-pad` today, developed standalone, and intended to be extracted to its
own home later (exactly like the sibling `tools/googly-vr`).

> **Status (2026-11-04): planning.** Nothing but the pre-existing
> `launch-funny.sh` prototype and research notes live here yet. The *responder*
> half is being ported from that local-`llama.cpp` script to a Poetry-based
> Python app that talks to a **remote Ollama server**, which is the first
> concrete stage (Stage 1 below). Display and speech-to-text are **documented
> but explicitly deferred** to later stages.

## Goal / vision

```
   [ people talking nearby ]
             │
             ▼
   [ mic + VAD + STT ]         (deferred — Moonshine/Parakeet via sherpa-onnx)
             │  text, one utterance at a time
             ▼
   [ interestingness filter ]  (deferred — cheap "is this worth riffing on?")
             │  a phrase, or nothing
             ▼
   [ voicebot responder ]      (THIS PLAN — witty line via a remote LLM)
             │  a one-to-two-sentence quip, or NOTFUNNY
             ▼
   [ touchy-pad LED matrix ]   (deferred — scrolling label text over the
                                 touchy-pad Python API / protobuf)
```

The end state is the hanging LED pillar of `creep3r`: a runtime that eavesdrops,
quips, and scrolls. This plan builds the *quip* stage first because it is the
one pure-software piece we can already exercise end-to-end against a live model
server, and because the same code is reusable by the whole `creep3r` family.

### What this plan covers

* **Stage 1 — project skeleton + the responder CLI** (Poetry/`justfile`/tests
  mirroring `tools/googly-vr`): read overheard text (stdin / file / one-shot
  flag), send it to the remote Ollama server with the `launch-funny.sh`
  persona + sampler, print the reply. This is the direct replacement for the
  local-`llama.cpp` prototype.
* **Stage 2 — the responder's edges**: the `NOTFUNNY` suppress-token contract,
  batch/JSON output, `voicebot models`, config resolution, and a network-free
  test harness with an opt-in live test.

### Non-goals (for now)

* **No speech-to-text / VAD / mic capture.** The response pipeline is fed *text*
  (from `sim-overheard.txt`, stdin, or later the STT stage). No audio deps in
  Stage 1/2.
* **No display output yet.** Pushing a quip to an LED matrix is Stage 3,
  deferred; the design notes below pin the primitives so it's a small add.
* **No "interestingness" scoring** (Stage 4) — the responder answers *whatever
  it is given* and leans on the `NOTFUNNY` escape hatch instead of a separate
  classifier.
* **No homekit / MCP / smart-home surface** — cool, but unrelated to the art
  path this plan is on.
* **Not published to PyPI** while it depends on touchy-pad by path.
* **No local inference.** The vendored `llama.cpp/` tree (gitignored) and
  `launch-funny.sh` stay as the *local fallback / reference implementation*, not
  as a code path this plan exercises.

## Approach & technology choices

| Choice | Rationale |
|---|---|
| Python 3.11+ / Poetry | Match the touchy-pad host stack and the sibling `googly-vr` tool, so the devcontainer, the eventual PyPI pull-in, and the `touchy_pad` path dep all "just work". |
| `openai` SDK against the server's **`/v1`** endpoint | The remote Ollama exposes an OpenAI-compatible API (verified — see below), so the client is portable: point `--url` at any OpenAI-compatible server, or at a future vLLM/llama.cpp `llama serve`. |
| Ollama-specific sampler knobs via `extra_body={"options": {...}}` | `launch-funny.sh`'s whole point is a *loosened sampler* (`temperature=0.85`, `min_p=0.05`, `num_ctx`). Ollama's `/v1` forwards an `options` object; non-Ollama servers ignore unknown fields. A `--native` escape hatch (below) covers any knob `/v1` drops. |
| `--native` fallback → Ollama **`/api/chat`** | Verified to honour `options.{temperature,min_p,num_ctx}` precisely, which is the *exact* fidelity the persona/sampler tuning needs. Kept as an alternate code path, not the default, so the client stays server-agnostic. |
| `click` for the CLI | Matches `googly-vr` and the `touchy` CLI conventions. |
| touchy-pad as a **path dependency on `../../app`** — *added in Stage 3 only* | googly-vr adds it up front; here the responder has **no** device dependency, so Stage 1/2 stay installable and testable without the parent repo. Stage 3 adds the path dep and confines **every** `touchy_pad` import to one module (`display.py`) so extraction stays a one-file diff. |
| `requests` / `httpx` only if needed | The `openai` SDK covers `/v1`; the native `/api/chat` path can reuse the SDK's HTTP layer or a single `requests.post`. Prefer the SDK; add nothing new unless the native path needs it. |
| Persona + sampler live in **one** place (`persona.py`) | The prototype's hard-won lesson (docs/responder.md): wit comes from the persona/mechanism *and* the loosened sampler, and both are easy to forget by hand. Centralising them is why `launch-funny.sh` exists; the app must not regress that. |

## The remote model server (verified 2026-11-04)

* **URL:** `https://kai.pygmy-map.ts.net` (Tailscale; reached over plain HTTPS,
  no auth on the endpoint).
* **Software:** `GET /api/version` → `{"version":"0.40.14"}` (Ollama).
* **Endpoints that work:**
  * `GET /v1/models` and `POST /v1/chat/completions` — OpenAI-compatible.
  * `GET /api/tags`, `POST /api/chat` — native Ollama (full `options`).
* **Models already pulled** (`GET /api/tags`):

  | Ollama tag | Params / quant | Size | Notes |
  |---|---|---|---|
  | `hf.co/bartowski/Human-Like-Mistral-Nemo-Instruct-2407-GGUF:Q8_0` | 12.2B / Q8_0 | 13.0 GB | **default** — funniest in the recorded logs; the rough-plan example |
  | `hf.co/NousResearch/Hermes-3-Llama-3.1-8B-GGUF:latest` | 8.0B / Q4_K_M | 4.9 GB | fast + steerable fallback; `launch-funny.sh`'s default |
  | `hf.co/bartowski/Qwen2.5-Coder-14B-Instruct-GGUF:Q8_0` | 14.8B / Q8_0 | 15.7 GB | larger / slower |
  | `hf.co/bartowski/Qwen2.5-Coder-32B-Instruct-GGUF:Q3_K_M` | 32.8B / Q3_K_M | 15.9 GB | largest |

  A real reply from Hermes-3 (`/v1`, temp 0.85) for `the bread is done baking`:
  *"Time to toast! The bread is golden and ready for its close-up."*

### Config resolution (precedence: CLI flag → env → default)

| Setting | CLI | Env | Default |
|---|---|---|---|
| Server URL | `--url` | `VOICEBOT_URL` | `https://kai.pygmy-map.ts.net` |
| Model | `--model` | `VOICEBOT_MODEL` | `…/Human-Like-Mistral-Nemo-Instruct-2407-GGUF:Q8_0` |
| Persona text | `--persona` | `VOICEBOT_PERSONA` | the toaster-robot persona (below) |
| Persona file | `--persona-file` | — | (none) |
| Temperature | `--temperature` | `VOICEBOT_TEMP` | `0.85` |
| min-p | `--min-p` | `VOICEBOT_MIN_P` | `0.05` |
| Context (`num_ctx`) | `--ctx` | `VOICEBOT_CTX` | `4096` |
| Max output tokens | `--max-tokens` | `VOICEBOT_MAX_TOKENS` | `120` |
| API surface | `--native` | `VOICEBOT_NATIVE` | off (use `/v1`) |

Env names mirror `launch-funny.sh`'s `TOUCHY_BOT_*` but rebranded `VOICEBOT_*`
(the repo is `voicebot`); the script's `TOUCHY_BOT_NGL` (GPU layers) has no
remote analogue and is dropped.


## Persona, sampling, and the `NOTFUNNY` contract

Wit does not come from asking a small model to "tell a joke" (it dredges up
memorised dad jokes — docs/responder.md). It comes from (a) a **comedic
mechanism in the system prompt** and (b) a **loosened sampler**. Both are
lifted verbatim from `launch-funny.sh` so the app inherits the prototype's
behaviour, including the `tests/hermes.txt` recordings:

* **Persona (default, editable):**

  > You are a witty, slightly dramatic toaster-sized robot living on a desk,
  > eavesdropping on the humans nearby.
  > The input you receive is snippets from a conversation you are eavesdropping
  > on.
  > very important: if you don't think you have something funny enough to say,
  > just say NOTFUNNY (we will use that token to skip your reply). It is better
  > to say NOTFUNNY than to force a weak joke.
  > If you do think of something funny to say, go ahead and reply with it.
  > Never tell standard knock-knock or pun jokes. Instead, reply to whatever the
  > user says with dry observational humor, absurd over-confident theories, or
  > playful sarcasm in 1 to 2 short sentences.
  > Your words will appear on a scrolling LED display. NEVER use emoji.
  > Never open with 'Sure' or 'Certainly'.

* **Sampler (defaults):** `temperature=0.85`, `min_p=0.05`, `num_ctx=4096`.

* **`NOTFUNNY` contract.** The reply is a single string. If, after stripping
  whitespace/quotes/`*`, it equals `NOTFUNNY` (case-insensitive, optionally
  with trailing punctuation), the responder **suppresses** it: print nothing,
  emit no display update. `tests/hermes.txt` is the canonical tape — the first
  line (`meer loves the new toy`) correctly yields `NOTFUNNY`; the rest yield
  quips. The CLI exposes `--no-notfunny` to force printing the raw token, and
  `--json` to emit `{"input":…, "reply":…, "skip":true|false, "model":…}` per
  line (so a downstream stage or a test can consume it structurally).

## File & component layout

```
tools/voicebot/
├── pyproject.toml          # Poetry; console script `voicebot`; legacy [tool.poetry] layout
├── justfile                # install / test / lint / reply / models   (mirror googly-vr)
├── README.md               # quickstart once Stage 1 lands
├── launch-funny.sh         # kept: local-llama.cpp reference/fallback
├── sim-overheard.txt       # sample "overheard" lines (test + demo input)
├── docs/
│   ├── plans/initial.md    # ← this plan
│   ├── responder.md        # research: models/persona/sampler
│   └── transcribe.md       # research: STT (Stage 4)
├── src/voicebot/
│   ├── __init__.py
│   ├── cli.py          # click: `reply`, `models`  (the only click module)
│   ├── config.py       # resolve flag→env→default; build a Settings dataclass
│   ├── persona.py      # DEFAULT_PERSONA, NOTFUNNY token + is_notfunny()
│   ├── responder.py    # Responder: messages→chat()→parse; NOTFUNNY suppression
│   └── server.py       # ChatClient: openai /v1 (+ extra_body options), native /api/chat
└── tests/
    ├── test_persona.py
    ├── test_responder.py   # fake chat_fn; NOTFUNNY + batch + json
    ├── test_cli.py         # CliRunner, injected fake client, no network
    └── hermes.txt          # recorded tape (golden expectations)
```

`server.py` is deliberately the **only** module that opens a socket; `cli.py`
takes an injectable client so tests never touch the network. When Stage 3 adds
device output, `display.py` becomes the **only** module that imports
`touchy_pad` — the same one-importer extraction rule `googly-vr` uses.


## Phased implementation

### Stage 1 — responder CLI (the direct port of `launch-funny.sh`)

1. `pyproject.toml`: `name = "voicebot"`, `packages = [{include="voicebot",
   from="src"}]`, deps `openai >= 1.x` + `click >= 8.1`, dev group
   `pytest`/`ruff`, console script `voicebot = "voicebot.cli:main"`. Use the
   legacy `[tool.poetry]` layout (Poetry 2.x path-dep quirk, per googly-vr's
   comment) so Stage 3 can add the `touchy-pad` path dep cleanly.
2. `persona.py` — the default persona text, the `NOTFUNNY` token, and a
   `is_notfunny(reply: str) -> bool` normaliser (strip whitespace, surrounding
   quotes/asterisks, trailing `.`/`!`).
3. `server.py` — `ChatClient(settings)` with `reply(messages) -> str`:
   * default: `openai.OpenAI(base_url=f"{url}/v1", api_key="ollama")` +
     `chat.completions.create(model=…, temperature=…, max_tokens=…,
     messages=…, extra_body={"options": {"min_p":…, "num_ctx":…}})`;
   * `--native`: `POST {url}/api/chat` with `{stream:false, options:{…}}`,
     returning `message.content`;
   * `list_models()` → `GET {url}/api/tags` (native) or `/v1/models`.
   * Timeout + a clear error when the server is unreachable (bounded retry
     once; then a friendly message — this is a LAN/Tailscale appliance).
4. `responder.py` — build the `[system, user]` message list from the persona +
   one overheard line; call the client; apply `is_notfunny`.
5. `cli.py` — `voicebot reply`:
   * `--line "…"` (one-shot), or `-f FILE` / stdin (one overheard line per
     line) as the batch driver;
   * `--url/--model/--persona/--persona-file/--temperature/--min-p/--ctx/
     --max-tokens/--native/--json/--no-notfunny`;
   * `voicebot models` lists the server's pulled models.
6. `justfile` + README quickstart. `just reply -f sim-overheard.txt` is the
   end-to-end demo against the live server.

### Stage 2 — edges & hardening

* `--json` structured output; `--stream` optional (prints tokens as they
  arrive) — nice for the interactive/perf feel, not required.
* Interactive REPL mode (`voicebot reply` with no `-f`/`--line`, reading stdin
  until EOF) for manual tuning of persona/sampler.
* Graceful degradation: retry-once on timeout; `--max-tokens` guard so a
  runaway model can't flood the later LED display.
* Golden test against `tests/hermes.txt` with a **recorded** fake client; the
  live server test is `@pytest.mark.live`, skipped unless `VOICEBOT_LIVE=1`.

### Stage 3 — display: scroll a quip on the LED matrix *(deferred)*

* Add the `touchy-pad = { path = "../../app", develop = true }` path dep;
  `src/voicebot/display.py` is the sole `touchy_pad` importer.
* Build **one** screen at connect: a `label` with a fixed-size box and
  `long_mode = LongMode.LONG_MODE_SCROLL_CIRCULAR`
  (`touchy_pad.api.screens.label`), saved onto the device.
* Per quip: `pad.set_properties([build_property_override(label_id, "text",
  quip)])` — the Stage-lb14 batched override, no screen re-upload. Mirror
  `googly-vr`'s `connect()` / lazy-search / retry-the-next-update loop so a pad
  plugged in later is picked up, and `--sim` via `TOUCHY_SIM_URL`.
* Sizing: run against the board's `SysBoardInfoResponse` (`display_width` /
  `display_height`); the `creep3r` hanging pillar is a tall multi-panel chain
  (Stage lb10 chains), so keep geometry derived, never hard-coded.

### Stage 4 — speech-to-text + interestingness *(deferred)*

* Mic capture + VAD, then STT (Moonshine / Parakeet via `sherpa-onnx`, per
  docs/TODO.md and docs/transcribe.md) producing one utterance per line that
  feeds the *existing* responder — no responder changes required.
* Optional cheap "interestingness" gate to replace leaning solely on
  `NOTFUNNY`. Keep it swappable; `NOTFUNNY` stays the final backstop.

### Stage 5 — the full `creep3r` loop *(deferred)*

* Wire STT → filter → responder → display into one long-running service;
  auto-reconnect the pad and the server; run on the hanging hardware.


## Testing strategy

* **No network in CI.** `server.py` is injected everywhere; unit tests pass a
  fake `chat_fn`. `CliRunner` drives `cli.py` with that fake.
* **Golden tape.** `tests/hermes.txt` encodes the `NOTFUNNY`-vs-quip contract;
  a recorded fake reproduces it deterministically.
* **Live smoke (opt-in).** `VOICEBOT_LIVE=1 just test` runs one real
  `voicebot reply --line "the bread is done baking"` against the server and
  asserts a non-empty, non-`NOTFUNNY` reply — the "does the box still answer"
  check.
* **Lint.** `just lint` = `ruff format` + `ruff check --fix`, mirroring
  googly-vr and the parent repo.

## Risks / open questions

* **Does `/v1` honour `extra_body={"options":...}`?** Verified that it does not
  *error*; whether it applies `min_p`/`num_ctx` (vs silently ignoring them) is
  unconfirmed. **Mitigation:** Stage 1 smoke-compares a `/v1` reply with the
  `--native` `/api/chat` reply (which definitively honours `options`) and, if
  `/v1` drops them, flips the default to native or documents `--native` as
  required for faithful sampling. *Need: a decision, then a one-line flip.*
* **Model default.** Notes say Human-Like Mistral Nemo is "funniest yet but
  seems to ignore the NOTFUNNY rule" (`launch-funny.sh` comment). Proposal:
  default to **Hermes-3-8B** for reliable `NOTFUNNY` behaviour, offer Nemo via
  `--model`. *Need: the user's pick; both are already pulled.*
* **Server availability / auth.** The endpoint is open over Tailscale today; if
  it grows auth or a different hostname, `--url`/`VOICEBOT_URL` absorb it, but
  there is no key handling yet. *Need: whether an API key is ever expected.*
* **Latency budget.** creep3r assumed ~30 s end-to-end; a 12–32B model on this
  box may be slower. Time Stage 1 replies and record them here.
* **Extraction.** Like googly-vr, this repo is a submodule meant to be
  extracted; keep `touchy_pad` imports confined to `display.py` and prefer
  stdlib/`openai`/`click` so the eventual PyPI swap is trivial.

## Relationship to the parent repo

* Parent doc [docs/led-art.md](../../../../docs/led-art.md) names `voicebot`
  as the voice→text / text→voice AI half of `creep3r`; the LED pillar firmware
  (parent-repo Stages lb1–lb16) is already in place and is what Stage 3 drives.
* Text scrolling on the LED matrix uses the **`Label` `long_mode`** support
  (lightbar Stage LB3) and the **batched `SetPropertiesCmd`** (Stage lb14) —
  no firmware change is expected for Stage 3.
* Nothing in this plan moves a touchy-pad wire version; it is a pure host-side
  consumer of the existing API.

## Kept from the original sketch

The rough note this plan grew from said, in full: *use `tools/voicebot/
launch-funny.sh` as inspiration; create a new Poetry-based Python app based on
that script but instead of using a local `llama.cpp` use a remote Ollama server
at `https://kai.pygmy-map.ts.net`* — plus a code snippet showing the `openai`
client pointed at `…/v1`, `temperature=0.85`, and a system-message persona.
All of that is preserved above: Stage 1 is the Poetry port, the `openai`-client
recipe is the default `--url/--model/--temperature` path, and the persona/sampler
are the ones the prototype tuned. `launch-funny.sh` stays in-tree as the local
fallback it was written to be.

