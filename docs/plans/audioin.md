# voicebot — plan: audio in (mic → VAD → speech-to-text)

**Where this sits.** This is the **"audio in" half of
[`initial.md`](initial.md)'s Stage 4** (mic capture + VAD + speech-to-text),
pulled forward **ahead of Stage 3** (the LED display). The responder is already
built and proven; the next thing worth *hearing* is the *front* of the pipeline
— reliably turning nearby conversation into clean text, a few words at a time.
The display stays deferred, so this stage's only output is **log lines**: the
text we heard and the reply the model produced are logged exactly as they would
later be scrolled on the matrix.

> **Status: IMPLEMENTED (Stage 4a — "audio in").** A new `voicebot listen`
> command drives a `TranscriptSource` seam (the mic via Moonshine
> `MicTranscriber`, or a `--fake` replay) through the `UtteranceGate` into the
> existing `Responder`, emitting `HEARD:` / `SKIP(…)` / `REPLY:` log lines (or
> `--json` events). New modules: `audio.py`, `gate.py`, `listen.py`; new tests
> cover the gate, the loop (incl. the worker/drop-oldest path), the audio seam
> and the CLI. Verified: `just test` **49 passed / 2 live-skipped**, `just lint`
> clean; live runs against the real XVF3800 (device selected, model loaded,
> engine started) and the remote LLM (`listen --fake sim-overheard.txt` →
> `HEARD`/`REPLY`/`SKIP(notfunny)`). Display (Stage 3) is still deferred.
>
> The [questions below](#questions-to-settle-first) are now **settled** — all
> took the recommended option: **(1)** `MicTranscriber`; **(2)** `small`
> streaming default; **(3)** ≥3 content words; **(4)** *direct ALSA*, not
> PipeWire (the container's `pactl` was refused and PortAudio sees the array as
> `hw:2,0` — so **no `libasound2-plugins` was needed**); **(5)** worker thread +
> bounded queue (one in flight + one pending, drop-oldest as the safety valve;
> `--fake` runs inline for deterministic replay); **(6)** a new
> `voicebot listen`; **(7)** confirmed 16 kHz / 2-ch / S16_LE, mono capture;
> **(8)** `models_from`/cache for offline; **(9)** 5 s debounce + `NOTFUNNY`
> backstop.

## Goal / vision

```
  [ people talking nearby ]
            │
            ▼
  ┌───────────────────────────────────────────────┐
  │  mic capture  →  VAD / segment  →  STT         │   ← THIS PLAN
  │  (XVF3800 via sounddevice)  (Moonshine Voice)  │
  └───────────────────────────────────────────────┘
            │  one finished utterance at a time
            ▼
  [ min-words gate ]  ("at least a few words", else drop)   ← THIS PLAN
            │  a phrase worth answering
            ▼
  [ voicebot responder ]      (already built: src/voicebot/responder.py)
            │  a one-to-two-sentence quip, or NOTFUNNY
            ▼
  [ log it ]   (log.info("HEARD: …"), log.info("REPLY: …"))  ← THIS PLAN
            ⋮
  [ touchy-pad LED matrix ]   (Stage 3 — DEFERRED, not in this plan)
```

The deliverable is a new long-running command, `voicebot listen`, that opens the
mic, transcribes speech in (near-)real time, keeps only utterances with enough
words to be worth riffing on, asks the existing `Responder` for a quip, and
**logs** both sides of the exchange. Nothing is sent to the LED matrix yet — the
log lines are the audit trail we tune the STT and the gate against, and the exact
thing Stage 3 will later hand to the display.

### What this plan covers

* **Mic capture** — open the reSpeaker **XVF3800** USB mic array (dev: via the
  host's PipeWire from inside the devcontainer; prod: directly on the Pi) and
  stream 16-bit PCM frames.
* **VAD + segmentation** — decide when someone is speaking and cut the stream
  into discrete utterances (so one line of output = one thing a person said).
* **Speech-to-text** — run a **Moonshine Voice** streaming model on CPU.
* **The min-words gate** — "only invoke the LLM when you have a text snippet of
  at least a few words"; shorter/filler-only segments are logged and dropped.
* **Hand-off to the existing responder** — reuse `Responder` unchanged, call it
  off the audio thread, and log the quip (or the suppressed `NOTFUNNY`).

### Non-goals (for now)

* **No display output** — the touchy-pad LED matrix is Stage 3, deferred; this
  plan does not add a `touchy_pad` dependency and adds no `display.py`.
* **No text-to-speech / no talking back** — voicebot is ears-only for now.
* **No wake word, no diarization/speaker ID, no "interestingness" classifier** —
  we lean solely on the utterance gate + the existing `NOTFUNNY` backstop
  (`initial.md` Stage 4's optional classifier stays optional).
* **No XVF3800 control plane** — we do **not** drive or read the array's
  hardware VAD/DoA/LED ring / mute button; those live on a vendor control
  interface, not in the USB audio stream (see below). Host-side VAD only.
* **No meaningful latency tuning on PC** — the dev desktop is *not* the target;
  we measure on the Pi.

## Touchy-pad specifics

* **Which side(s):** `tools/voicebot/` **only**. No `firmware/`, `app/`, `rust/`
  or `proto/` changes.
* **Wire version:** **none moves.** This is a pure host-side consumer; it does
  not even import `touchy_pad` yet (Stage 3 will).
* **Recipes that validate it:** this project's own `just install` / `just test`
  / `just lint`, plus a new `just listen`. The parent repo's `just app-test` is
  **unaffected** (nothing in `app/` changes) — no need to run it, though it
  should stay green.
* **Runtime prerequisites** already in place: the dev-container audio wiring
  (`/dev/snd` bind mount, `PULSE_SERVER` → host PipeWire, `libasound2t64` /
  `libportaudio2` / `alsa-utils` / `pulseaudio-utils` in the image). One
  possible addition is called out as a question (`libasound2-plugins`).

## Approach

One new long-running command, `voicebot listen`, wraps a small pipeline whose
stages are each a separate, individually testable object:

```
  AudioIn (owns the mic + the STT session)
      │  yields finished utterances  ("lines")
      ▼
  gate(line) -> keep | drop        (pure function: word count / filler / rate)
      │  kept lines
      ▼
  Responder.respond(line)          (existing; called off the audio thread)
      │
      ▼
  log HEARD / REPLY / SKIP
```

The whole microphone + model layer sits behind a **`TranscriptSource`** seam — an
iterator/generator of finished utterances. `listen.py` depends only on that seam,
so every test runs against a `FakeTranscriptSource` (a scripted list of lines)
with a fake `chat_fn`, and **CI never touches a mic, the network, or Moonshine**.

`voicebot listen` reuses the `reply` command's config surface (`--url`, `--model`,
`--persona`, `--temperature`, `--min-p`, `--ctx`, `--max-tokens`, `--native`,
`--json`, `--no-notfunny`) and adds audio-shaped flags (`--device`, `--model-arch`,
`--min-words`, …). `reply` (text-in, quip-out) stays exactly as it is — it is the
regression harness for the responder half, and `listen` reuses `Responder`
verbatim.

## The hardware

### The mic: Seeed reSpeaker XVF3800 (USB 4-mic array)

* **What it is:** four PDM MEMS mics in a circle + an XMOS **XVF3800** DSP doing
  **AEC, multi-beamforming, de-reverberation, dynamic noise suppression, 60 dB
  AGC, VAD and DoA** on-board; 360° capture to ~5 m. It is a **USB Audio Class
  (UAC) device** — plug-and-play on Linux/macOS/Windows — with a separate
  vendor/I²C **control** interface (the "reSpeaker console" app, DoA readout,
  the LED ring, mute button).
* **What it gives the audio stream:** in the shipping **USB firmware** the host
  sees a **processed** capture device — verified in the devcontainer as card 2,
  `arecord -D hw:2,0 -f S16_LE -r 16000 -c 2 -d 2` writes a valid 2.00 s WAV.
  A **6-channel** (raw-mic + processed) firmware also exists.
* **What it does *not* give the audio stream:** the **hardware VAD/DoA** are
  control-plane readouts, not a flag in the PCM. So this plan does **not** rely on
  the array's VAD — we run **host-side VAD** (Moonshine's). That keeps the code
  identical on any UAC mic (a webcam mic, the Pi's own input, …) and keeps the
  XVF3800's DSP as a "free" quality win we don't have to drive.
* **Assumption to verify on hardware:** the default processed capture is
  **16 kHz, 2-channel, S16_LE** (the array's native rate is 16 kHz, which is
  exactly what the STT models want). If a unit defaults to 48 kHz we resample
  once in `AudioIn` (see [questions](#questions-to-settle-first)).

### Dev now vs. prod later — same design, different box

| | Dev (today) | Prod (target) |
|---|---|---|
| Host | beefy AMD desktop, exporting the mic into the devcontainer | low-end **Raspberry Pi** (Pi 4/5 class) |
| Mic path | USB → host PipeWire → container (`PULSE_SERVER`/`/dev/snd`) | USB → ALSA directly |
| Compute | CPU-only (deliberately, like the Pi) | CPU-only |
| What changes | nothing in the code but `--device` + maybe model size | — |

The rule from the sketch holds: **use the CPU, never a GPU**, and keep the code
path *identical* on both so the devcontainer result predicts the Pi. Concretely
that means **no `ort_providers`** (Moonshine's docs: *"Unset means CPU-only
(recommended)"*), and a model small enough for a Pi.


## Technology choices

| Choice | Rationale |
|---|---|
| **Moonshine Voice** (`pip install moonshine-voice`) as the STT engine | Purpose-built for edge/Pi CPU (it scales compute with utterance length instead of padding to 30 s like Whisper), ships **streaming** models, and — crucially — its streaming API already does **VAD + line segmentation** (`LineStarted` … `LineCompleted`), which is exactly the "one finished utterance at a time" shape this plan needs. |
| **Streaming** model, not a batch file transcriber | The library "does work while the user is still talking", so latency overlaps the conversation. Batch (`transcribe_without_streaming`) is kept only as a fallback / for tests over a fixed WAV. |
| English **streaming** family (`Tiny` 34M / `Small` 123M / `Medium` 245M) | All **MIT**, all CPU-runnable, WER 12.0 / 7.84 / 6.65%. Default is a [question](#questions-to-settle-first); `Small` is the suggested Pi-friendly middle. `--model-arch` + `models_from(dir)` make it a one-flag switch. |
| **`sounddevice`** (PortAudio) for capture | The Python-idiomatic UAC capture library; the container already installs the Linux PortAudio (`libportaudio2`) + `libasound2t64` it needs. |
| A **`TranscriptSource` seam** between `listen.py` and Moonshine | Makes the loop testable with zero audio/network/model, exactly like `Responder` takes an injected `chat_fn` today. This is the single most important structural decision for CI. |
| **`logging`** for output (no prints, no display) | Matches the repo convention (`logging.getLogger(__name__)`) and the sketch's "use python log messages instead". `--json` mirrors `reply` for machine-readable logs if wanted. |
| **CPU-only, small model, no GPU** | The production target is a Pi; choosing it *in the container* is what makes the container a useful predictor. |

### Model facts worth pinning (from the Moonshine docs)

* `MicTranscriber` owns the mic and emits `on_text` (in-progress) / `on_line`
  (finished segment) callbacks; `load()` downloads the recommended model on
  first use into a cache (`~/.cache/moonshine_voice`, override with
  `MOONSHINE_VOICE_CACHE`) and runs **offline** after that.
* `Transcriber` is the base class for **feeding audio yourself**
  (`start()` / `add_audio()` / `stop()` + a `TranscriptEventListener`) — the
  alternate path if we want to own capture (device choice, resampling, tests).
* `options={...}` carries `ort_providers` (leave unset ⇒ CPU), `skip_transcription`
  (VAD-only, no STT), `max_tokens_per_second`, key terms, etc.
* English **streaming** models take **16 kHz** input and are the default for
  English; `moonshine_voice-0.1.5-…-x86_64.whl` is available here and prebuilt
  **arm64** libs exist for the Pi.

## File & component layout

```
tools/voicebot/
  pyproject.toml            + moonshine-voice, sounddevice deps
  justfile                  + `listen` recipe
  src/voicebot/
    audio.py       NEW   AudioIn: owns the mic + a Moonshine streaming session;
                         yields finished utterances. The ONLY module that imports
                         moonshine_voice / sounddevice.
    gate.py        NEW   the min-words / filler / debounce gate — a pure function
                         (`should_answer(text, *, min_words) -> bool`) + a small
                         `UtteranceGate` class for rate-limiting repeats.
    listen.py      NEW   the loop: TranscriptSource -> gate -> Responder -> log.
                         Imports neither mic nor model (inject the source + a chat_fn).
    config.py      EDIT  add audio settings (device, model_arch, min_words, rate limit)
                         + their defaults/env names.
    cli.py         EDIT  new `voicebot listen` command (reuses the `reply` options).
    responder.py   —     unchanged (reused).
    persona.py     —     unchanged.
    server.py      —     unchanged.
  tests/
    test_audio.py    NEW   AudioIn against a fake/none: device selection, resample,
                           utterance assembly — no model, no mic.
    test_gate.py     NEW   word counting, filler, debounce — pure logic.
    test_listen.py   NEW   the loop with a FakeTranscriptSource + fake chat_fn.
    test_live_audio.py NEW  @pytest.mark.live: real mic + model, opt-in only.
```

Seam contract (kept deliberately tiny, in `audio.py`):

```python
class TranscriptSource(Protocol):
    def lines(self) -> Iterator[str]: ...   # blocks, yields one finished utterance
    def close(self) -> None: ...
```

`listen.py`'s only audio knowledge is this protocol; `AudioIn` is one
implementation and `FakeTranscriptSource` the other.


## Implementation sequence

Phased so that **every phase is independently testable and CI-green**, and the
first phase needs no mic and no model at all.

* **A0 — skeleton + the seam (no audio, no model).**
  Add `TranscriptSource` + `FakeTranscriptSource`, `gate.py`, `listen.py`, and
  `voicebot listen` wired only to the fake source. `just listen -- --fake
  file.txt` replays a text file through the gate + responder and logs — the
  end-to-end loop, with zero hardware. Tests: `test_gate.py`, `test_listen.py`.
* **A1 — real capture, no STT.** `AudioIn` opens `sounddevice` on the chosen
  device, downmixes to mono, and (if needed) resamples to 16 kHz; a debug mode
  logs frame level/RMS so we can *see* audio arriving before any model is
  involved. Device discovery (`--device`, default = name match on the XVF3800).
  Tests: `test_audio.py` with a fake `sd.InputStream`.
* **A2 — STT wired in (streaming).** Hand frames to Moonshine's streaming
  session and yield `on_line` results. `--model-arch` / `models_from` /
  `MOONSHINE_VOICE_CACHE`. Verify a recorded WAV transcribes correctly, then a
  live mic.
* **A3 — the gate + responder hand-off.** Apply the min-words/filler/debounce
  gate; call `Responder` on a **worker thread** with a bounded queue so the
  audio callback never blocks on HTTP. Log `HEARD` / `REPLY` / `SKIP`.
* **A4 — polish.** Config/env parity with `reply`, `--json`, README + `justfile`
  updates, and a short usage note in the README (this file stays the plan).
  Update `initial.md`'s Stage 4 to point here.
* **A5 — measure + Pi dry-run (optional, when hardware is available).** Time
  utterance-end → quip latency; run the same command on the Pi; note CPU/RAM.

## Testing strategy

* **CI is network-, mic- and model-free.** All of it drives the
  `TranscriptSource` seam with a fake and `Responder` with a fake `chat_fn`
  (exactly as `test_cli.py` / `test_responder.py` do today). Moonshine and
  `sounddevice` are imported *lazily* inside `AudioIn` so merely importing the
  package (and the test suite) never pulls them in.
* **Golden tape reused.** `tests/hermes.txt` already encodes the
  quip-vs-`NOTFUNNY` contract; the listen-loop test feeds the same lines through
  the fake source and asserts the same outcomes.
* **Gate unit tests** — word counting (punctuation, contractions), filler-only
  ("uh huh", "hmm"), the debounce window, and the "at least a few words" line.
* **Opt-in live tests** — extend the existing `VOICEBOT_LIVE=1` idea with a new
  `@pytest.mark.audio` (or `live`) test that opens the real mic + model and
  asserts one utterance comes back; skipped by default, run by hand in the
  container and on the Pi.
* **Lint** — `just lint` (unchanged).

## Risks / open questions

* **Container audio path.** `sounddevice` speaks to PortAudio, which on Linux
  uses ALSA; reaching the *host's* PipeWire from the container may need ALSA's
  `pulse` plugin (`libasound2-plugins`, **not currently installed**) — or we
  address the device directly via ALSA (`hw:2,0`). See question 4.
* **Model download needs network once.** The first `load()` fetches the model
  (~tens of MB; Medium is larger). Fine in the container; on an offline Pi it
  must be pre-staged (`models_from(dir)` / `MOONSHINE_VOICE_CACHE`). See
  question 8.
* **Latency is unproven on a Pi.** Moonshine streaming `Tiny`/`Small` should be
  ~sub-second per utterance on a Pi 5, but that is a claim to *measure*, not
  assume; the LLM round-trip is the other half of the budget.
* **Blocking the audio thread.** A 120 s HTTP timeout inside Moonshine's
  callback would stall capture — hence the worker-thread hand-off (question 5).
* **Over-triggering.** Continuous conversation could fire the LLM constantly.
  The gate's debounce/rate-limit and the `NOTFUNNY` backstop are the mitigations;
  a real "interestingness" classifier stays out of scope.
* **`MicTranscriber` vs `Transcriber` coupling.** Who owns the mic changes how
  testable and portable the capture is — question 1.


## Questions to settle first

These are the decisions I'd like to make *with you* before writing code. Each
has the options, the trade-off, and my recommendation.

1. **Who owns the microphone — Moonshine's `MicTranscriber`, or our own capture
   feeding `Transcriber`?**
   * (a) **`MicTranscriber`** — it opens the mic itself and gives us streaming +
     VAD + line segmentation for almost no code. *Cost:* device selection /
     resampling / threading are inside the library; feeding a pre-recorded WAV
     for tests uses a *different* API.
   * (b) **Our own `sounddevice` capture + `Transcriber.add_audio()`** — we pick
     the device, downmix/resample ourselves, and can replay a WAV through the
     exact production path. *Cost:* more code, and we own the streaming session
     (`start`/`add_audio`/`stop` + a `TranscriptEventListener`).
   * **My recommendation: (a)** for the shipping path, because it is the
     documented "happy path" and gets segmentation for free — *provided* it
     supports `.device()` selection (it does) — with the `AudioIn` seam making
     (b) a drop-in swap later. **Which do you want?**

2. **Default STT model size.** `Medium` streaming = 245M, WER 6.65% (best, heaviest);
   `Small` = 123M, 7.84%; `Tiny` = 34M, 12.0% (lightest). All CPU-runnable on a Pi.
   **My recommendation: `Small` by default** (the Pi-friendly middle), with
   `Medium` one `--model-arch` away for the dev desktop if the extra accuracy
   noticeably helps the quips. **Agree, or start at `Medium` in dev?**

3. **The "at least a few words" gate.** Proposed rule: answer only if the finished
   utterance has **≥ 3 words** *after* dropping pure filler ("uh", "um", "hmm",
   "yeah"), and lasts **≥ ~0.6 s**; log every utterance either way. Make the word
   count a `--min-words` flag. **Is 3 the right floor? Want filler-stripping, or
   just a raw word count?**

4. **Container audio backend.** How should `sounddevice` reach the mic here?
   * (a) **Host PipeWire** — ALSA's `pulse` plugin → `PULSE_SERVER`. Needs
     `libasound2-plugins` (provides `libasound_module_pcm_pulse.so`), which is
     **not currently in the image**. Nicest (hot-plug, routing, same as a desktop app).
   * (b) **Direct ALSA `hw:2,0`** — bypasses the sound server; already proven to
     work via `arecord`, but is card-number-fragile and ignores PipeWire.
   * (c) `default` — whatever ALSA defaults to; least predictable here.
   * **My recommendation: (a), adding `libasound2-plugins` to the `Containerfile`**
     (needs one image rebuild), with `--device` able to force (b). **OK to add the
     package, or do you prefer the direct-ALSA path?**

5. **Never block the audio callback.** The responder call is an HTTP request with
   a 120 s timeout; running it inside Moonshine's `on_line` callback would stall
   capture. Proposed: a **single worker thread + a small bounded queue**
   (drop-oldest) so a slow/absent server can't back up the audio. **Agree?**
   (Alternative: inline call and accept the stall — simpler, worse.)

6. **Command shape + stage framing.** A **new `voicebot listen`** command (leaving
   `reply` untouched as the responder's regression harness), framed as **Stage 4a
   ("audio in") landing ahead of Stage 3 (display)**. **Good — or would you rather
   fold this into `reply`?**

7. **Sample format / rate / channels.** I'm assuming the XVF3800 exposes
   **16 kHz, 2-channel, S16_LE** processed capture (Moonshine wants 16 kHz mono).
   Plan: take **channel 0**, downmix only if trivially better; resample once if a
   unit turns out to be 48 kHz. **Shall I verify the exact format with
   `arecord -l` / `--list-devices` as the first implementation step?**

8. **Pi model provisioning (offline).** First `load()` downloads the model. For the
   Pi I'd **pre-download once and point at a fixed dir** (`models_from(dir)` +
   `MOONSHINE_VOICE_CACHE`), so the appliance runs fully offline — matching
   `creep3r`'s "100% local" goal. **Agree, or is a first-run download acceptable?**

9. **Repeat / debounce defaults.** Continuous chatter could re-fire the LLM on the
   same thing. Proposed: ignore an utterance that is **~identical to the last one
   within N seconds** (default ~5 s), and keep relying on `NOTFUNNY` for "nothing
   worth saying" (no separate interestingness classifier yet). **Reasonable
   defaults, or would you rather see every utterance answered while we tune?**

> Once 1–4 are answered I can build A0→A2 in a sitting; 5–9 are tunables that can
> even be adjusted after the first live run.

## Relationship to `initial.md` and the docs

* This plan **is** `initial.md` Stage 4's "mic capture + VAD + STT" bullet, done
  ahead of Stage 3. When it lands, Stage 4's bullet should link here, and Stage 5
  (the full `creep3r` loop) becomes STT → responder → **display** → Pad.
* It reuses the responder unchanged, so `initial.md`'s Stage-1/2 description of
  the `NOTFUNNY` contract still holds verbatim.
* The `docs/TODO.md` "ai tips" (Moonshine/Parakeet via `sherpa-onnx`, the Pi
  hardware notes) and `docs/transcribe.md` (the Moonshine quickstart link) are the
  background; this plan picks **Moonshine Voice (streaming)** from that list and
  defers the alternatives.
* `docs/hardware.md` currently just says `xvf3800`; this plan is the place to
  expand that one-liner with the "processed UAC, host-side VAD" decision above.

## Acceptance criteria (definition of done)

1. `voicebot listen` runs end-to-end on the container + XVF3800: spoken
   sentences produce `HEARD: …` / `REPLY: …` log lines; short/filler utterances
   log as skipped and do **not** hit the LLM.
2. `just test` green **with no mic, no network and no model** (the fake-source
   path), `just lint` clean.
3. `reply` and `models` behave exactly as before (unchanged).
4. No `touchy_pad` import, no wire-version change, no parent-repo code touched.
5. README + `justfile` document `just listen`; `initial.md` Stage 4 links here.

