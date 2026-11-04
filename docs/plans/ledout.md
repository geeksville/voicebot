# voicebot — plan: LED out (scroll the quip on a touchy-pad)

**Where this sits.** This is `initial.md` **Stage 3** — the *output* half of the
pipeline. Stage 1+2 (the responder) and Stage 4a (audio in) are already built, so
the only gap left between "the model said something funny" and "the desk robot
says it out loud" is the display. The eventual target is the `creep3r` hanging LED
pillar (parent repo [`docs/led-art.md`](../../../../docs/led-art.md), lightbar
stages lb1–lb16); the first target is a single WS2812B matrix on a desk.

> **Status: PROPOSED — decisions recorded, not built yet.** The three questions
> that mattered are settled (see *Decisions*): **inline multi-colour is in scope**
> and needs a small touchy-pad feature (`Label.recolor` — see *Touchy-pad
> (parent-repo) changes*); the legacy `NOTFUNNY` token is **removed** in favour of
> `/notfunny`; and the display gets a startup banner, a 2-minute idle clear, and a
> **lazy** connect. Everything below the decisions is confirmed against the parent
> repo's code and the sibling `tools/googly-vr`, which drives the same panel with
> the same mechanism. The recolor feature is specified here but not written — the
> owner flashes + tests it on hardware once it lands.

## Goal / vision

```
  [ voicebot listen ]
     mic → gate → responder ──► Reply { runs }                (stage 4a / 1+2)
                                     │
                                     ▼
              ┌───────────────────────────────────────────────┐
              │  display.py   (the ONLY touchy_pad importer)  │
              │   · one full-panel scrolling label screen,    │
              │     saved once at connect (recolor on)        │
              │   · per quip: one SetPropertiesCmd batch      │
              │       text = "#FF0000 Danger!# watch out"     │
              └───────────────────────────────────────────────┘
                                     │ USB (or TOUCHY_SIM_URL / HTTP)
                                     ▼
                       [ touchy-pad LED matrix / LCD ]
                 ← the quip scrolls across it, in colour →
```

The deliverable is that right-hand half: a `display.py` that opens the attached
touchy-pad, builds **one** screen containing a single full-panel label in LVGL's
continuous-scroll long mode, saves it, and then only ever pushes property
overrides — never another screen upload.

## What this plan covers

* **A display sink in `listen`** — every `KIND_REPLY` is pushed to the pad;
  `HEARD` / `SKIP` stay log-only.
* **One screen, built from the board's real geometry** (never hard-coded to 8×8 —
  see *The screen*, below), with a font chosen from what the firmware actually
  compiled in and **inline recolour enabled**.
* **The `/command` contract** — replacing the bare `NOTFUNNY` sentinel with a
  small in-band command language: `/notfunny`, `/color:…`, extensible, and
  **multi-colour within a single reply**.
* **A touchy-pad feature: inline recolor** — a new `Label.recolor` proto field plus
  the firmware / host-DSL / sim / Rust / docs work to honour it (the parent-repo
  half of this plan).
* **A startup banner, a 2-minute idle clear, and lazy connect** — the panel shows
  `I'm voicebot` from startup, blanks after `--clear-after` seconds with nothing
  new, and only connects when there is something to show.
* **Packaging** — the `touchy_pad` dependency (path first, PyPI later) plus the
  `just use-touchy-local` / `just use-touchy-pypi` recipes.

## Non-goals (for now)

* **No multitouch / interaction.** The matrix is a pure output device here;
  nothing is read back from it.
* **No graphics beyond scrolling text** (no bouncing shapes, no images). The
  parent repo's `build_setup_screen_touchless` already covers pixels; voicebot
  only needs a marquee.
* **No always-on service wiring yet** — that is Stage 5. This stage is
  `listen`-shaped: it drives the pad only while replies arrive (and retries
  lazily, exactly like googly-vr).
* **No other `Label` long-mode/animation work** — the parent-repo change is the
  `recolor` flag and nothing more (see *Deferred*).

## Approach & technology choices

| Choice | Rationale |
|---|---|
| `touchy_pad.api` (path dep → PyPI) | The supported host entry point (`touchy_open`, the `screens` DSL, `build_property_override`). Same stack as `tools/googly-vr`, so the devcontainer and the later PyPI swap "just work". |
| **One saved screen + `set_properties`** | Stage lb14's batched `SetPropertiesCmd` lands a whole message (the marked-up text) in one atomic RPC — no screen re-upload, no lost widget state. Stages lb15/lb16 additionally guarantee the batch **wakes the panel** and **repaints immediately**, so a quip shows within a refresh period. This is the exact mechanism googly-vr proved for the eyes. |
| `LongMode.LONG_MODE_SCROLL_CIRCULAR` label | The parent repo added this in lightbar stage LB3 precisely for a full-panel marquee (`build_setup_screen_touchless` already uses it). Continuous one-way scroll, loops forever, no animation code. |
| **Inline recolour** (`#RRGGBB text#`), promoted to a `Label.recolor` proto field | The only way to get **multi-colour inside one scrolling string**: LVGL parses `#RRGGBB text#` runs when the label's `recolor` flag is on, and the flag is not reachable through the runtime-property system — hence the small touchy-pad feature this plan adds. One `text` override then carries the whole coloured quip. |
| `text_color` — **not** needed after all | Superseded by inline recolour (below): with every coloured run marked up, the label's built-in white `text_color` covers the unmarked text, so the runtime path carries no colour state at all. |
| Geometry from `pad.board_info` | The board reports `display_width` / `display_height` / `is_touchable`. Hard-coding 32×8 would break the LCD boards *and* the multi-panel `creep3r` pillar (stage lb10 chains) this same code must eventually serve. |
| `click` flags + the existing `_LLM_OPTIONS` | Matches the rest of the CLI; the display is one more `listen` option, not a new program. |
| Reuse googly-vr's **lazy connect / retry-on-next-reply** shape | A pad plugged in later gets picked up without a restart and an unplugged pad is never fatal — the pattern is already written and tested in `tools/googly-vr/src/googly_vr/cli.py`. |
| `touchy_pad` import confined to `display.py` | `initial.md`'s extraction rule: pulling voicebot out to its own repo stays a one-file diff plus the PyPI switch. |

## The `/command` contract — model output → voicebot directives

Today the model's only control channel is the bare sentinel `NOTFUNNY`
(`responder.py` + `persona.is_notfunny`). This stage generalises it into a tiny
in-band command language: **any word in the model's output that starts with `/`
is a directive to voicebot, never something to display**.

The two commands to define now:

| Command | Meaning |
|---|---|
| `/notfunny` | The model has nothing worth saying → suppress the whole reply (replaces the `NOTFUNNY` sentinel). |
| `/color:xxx` | Print the text in colour `xxx`, where `xxx` is `red` / `green` / `blue` / `yellow` / `white` (case-insensitive) or an exact `0xRRGGBB` (also accept `#RRGGBB` / bare `RRGGBB`) so the model can pick *any* colour. |

…and the grammar is deliberately open, so more commands (`/speed:…`,
`/repeat:…`) become a table entry rather than a redesign.

### Parsing rules

* **Token shape:** `/` + `[a-z]+` + optional `:` + a value, where the value runs
  to the next whitespace. Names are case-insensitive.
* **Anywhere, stripped:** a command token is a directive wherever it appears and
  is **removed** from the displayed text (so `/color:red Danger!` displays
  `Danger!`). Whitespace left behind is collapsed.
* **Colour runs:** `/color:X` starts a new run — the text *after* it (up to the
  next `/color`, or the end of the reply) is colour `X`. `Look out /color:red
  Danger!` therefore becomes two runs: `("Look out ", white)` and `("Danger!",
  red)`. That maps 1:1 onto LVGL's inline recolour, so **multi-colour within one
  reply works**.
* **Tolerance:** the token may be dressed up however a model likes (quotes,
  trailing punctuation) — accept it and strip it.
* **Empty result:** if stripping the commands leaves nothing, there is nothing to
  show; treat it as a skip (log `SKIP(empty)`), like `/notfunny`.
* **Unknown command** (`/foo`, or `/color:` with a bad value): stripped from the
  text, logged at WARNING, otherwise ignored (never displayed, never fatal). A
  bad `/color` value leaves the run colour unchanged.
* **`#` is reserved:** a literal `#` in a quip would be swallowed by the recolour
  parser (LVGL's `##` escape is dead code in this version), so the markup builder
  neutralises it — see R2.

### The persona change

`persona.DEFAULT_PERSONA` swaps the `NOTFUNNY` sentence for the new contract —
roughly:

> * If you have nothing funny to say, reply with exactly `/notfunny` (any word
>   starting with `/` is a command we consume; it is never shown).
> * To colour your words, write `/color:NAME` — everything after it is that
>   colour until you change it again or the reply ends. NAME is `red`, `green`,
>   `blue`, `yellow`, `white`, or a hex value like `0xRRGGBB`. Text before any
>   `/color` is white, and you can switch colours several times in one reply.
>   Use colour for emphasis or a punchline.
> * Never use `/` or `#` in ordinary text.

### Where the parsing lives

A new, dependency-free `commands.py`:

```python
@dataclass(frozen=True)
class Run:
    text: str            # a stretch of displayable text
    colour: int          # 0xRRGGBB (white until a /color changes it)

@dataclass(frozen=True)
class ParsedReply:
    runs: tuple[Run, ...]     # the displayable text, as ordered colour runs
    skip: bool                # /notfunny (or nothing left after stripping)
    found: tuple[str, ...]    # the raw command tokens (for --json / debugging)

    @property
    def text(self) -> str:    # the plain text, commands stripped
        return "".join(r.text for r in self.runs)

COLOURS = {"red": 0xFF0000, "green": 0x00FF00, "blue": 0x0000FF,
           "yellow": 0xFFFF00, "white": 0xFFFFFF}

def parse(raw: str) -> ParsedReply: ...
```

`Responder.respond()` calls `parse()` and `Reply` carries `runs` (plus `skip`).
`display.py` is the **only** place that turns runs into LVGL markup
(`#RRGGBB text#…`); logs, `--json` and `voicebot reply` all use the plain
`text`.

## Removing the legacy `NOTFUNNY` token

The old sentinel goes away entirely (owner decision — no back-compat shim):

* `persona.is_notfunny` and `persona.NOTFUNNY` are **deleted**; `/notfunny` is
  the only skip mechanism. `responder.py` uses `commands.parse` alone.
* `--no-notfunny` is **dropped** (`/notfunny` is now part of the command
  contract, not a special case); `voicebot reply` prints the **stripped** text
  (what the LED will show), with `--json` also carrying the raw reply for
  debugging.
* `tests/hermes.txt` — a recorded transcript with **no consumers** (no test reads
  it); refresh it, or leave it as a historical artifact.
* `test_persona.py` / `test_responder.py` drop the `is_notfunny` cases.
* `initial.md` Stage 2's `NOTFUNNY` wording is rewritten to point at *The
  `/command` contract*.

## The scrolling display

`display.py` — the sole `touchy_pad` importer — owns everything device-shaped.

### Connect

```python
def connect():                      # mirrors googly-vr's renderer.connect()
    return touchy_open()            # honours TOUCHY_SIM_URL, USB, HTTP
```

`PadDisplay(pad)` reads `pad.board_info` (`display_width`, `display_height`,
`is_touchable`) and builds the screen from it.

### The screen — one label, saved once

```python
s = Screen(SCREEN_NAME, layout=absolute())
s += label(LABEL_ID, text=STARTUP_TEXT, font_size=font_for(height),
           long_mode=LongMode.LONG_MODE_SCROLL_CIRCULAR,
           recolor=True,                        # NEW field (see parent-repo changes)
           rect=rect(0, 0, width, height),
           style=style(text_color=0xFFFFFF))    # the "unmarked text" colour
pad.screen_save(s)
pad.screen_load(screen_path(SCREEN_NAME))
```

* **Sizing.** `SCROLL_CIRCULAR` needs a *fixed box narrower than the text*, so
  the label takes the whole panel via an explicit `rect(0, 0, w, h)`. Under
  `absolute()`, `grow_x`/`grow_y` are ignored — the exact trap
  `build_setup_screen_touchless` documents in its comments. Geometry comes from
  `board_info`, never from the board name.
* **Font.** Only fonts compiled into the firmware render; others silently fall
  back to the theme default. Today the shared `sdkconfig.defaults` has
  **UNSCII-8 (size 8), Montserrat 16 and 30** — so the chosen size must be one of
  those (8 for a ≤8-px-tall matrix, 30 for a big LCD), picked by panel height
  (see *Decisions* #6).
* **`recolor=True`** is the parent-repo feature this plan adds: it switches on
  LVGL's inline-recolour parsing for this label, so a `#RRGGBB text#` run renders
  in colour while plain text uses the style's white.
* **Name.** The screen is `voicebot` (`--screen-name`), **not** `default`, so a
  later `touchy init` / `touchy screen demo` can't clobber it and vice-versa.
* **Reconnect** rebuilds the screen and forgets the last-sent state.

### Per quip — one batch, one marked-up string

```python
WHITE = 0xFFFFFF

def to_markup(runs: Sequence[Run]) -> str:
    """Runs → LVGL inline-recolour text, e.g. '#FF0000 Danger!# watch out'."""
    out = []
    for r in runs:
        t = r.text.replace("#", "")     # '#' can't be escaped in this LVGL — drop it
        out.append(t if r.colour == WHITE else f"#{r.colour:06X} {t}#")
    return "".join(out)

def show(runs: Sequence[Run]) -> None:
    pad.set_properties([build_property_override(LABEL_ID, "text", to_markup(runs))])
    self._last_shown = monotonic()      # re-arm the idle clear
```

`SCROLL_CIRCULAR` re-lays-out when the text changes, so a new quip simply takes
over the marquee. **One** property override per quip — no colour state on the
device, no screen re-upload.

### Startup banner, idle clear, lazy connect

* **At startup** the label is built with text `"I'm voicebot"` (`STARTUP_TEXT`),
  so the first thing the panel shows is the banner.
* **Idle clear:** every shown message (re)arms a timer of `--clear-after` seconds
  (default **120**, `0` = never); when it expires, `show([])` — an empty string —
  blanks the marquee until the next reply.
* **Lazy connect:** a pad is only opened when there is a message to show. A pad
  absent at startup — or unplugged mid-run — is picked up on the **next message**,
  never a fatal error. A missing pad, an incompatible firmware or a drop all
  become a one-line log, and the handle is dropped so the next message reconnects
  (googly-vr's shape).
* **Headless LED board:** a fresh matrix reports **0×0 until a `BoardConfig` panel
  chain is provisioned** (stage lb6/lb10), so on `0×0` print the exact remedy
  (`touchy pref from-template led-32x8`) once and keep looking (see *Decisions*
  #7).

## voicebot code changes

| File | Change |
|---|---|
| `src/voicebot/commands.py` | **new** — the `/command` parser (`parse`, `ParsedReply`, `Run`, `COLOURS`). Stdlib only. |
| `src/voicebot/display.py` | **new** — `connect()`, `PadDisplay` (recolor screen build, `to_markup`, `show`, startup banner, idle clear, lazy connect). The only `touchy_pad` importer. |
| `src/voicebot/responder.py` | `Reply` gains `runs`; `respond()` uses `commands.parse` (the notfunny special-case is gone). |
| `src/voicebot/persona.py` | The `DEFAULT_PERSONA` text → the `/notfunny` + `/color` contract; `is_notfunny` / `NOTFUNNY` deleted. |
| `src/voicebot/listen.py` | `ListenEvent` gains `runs`; a **display sink** is invoked on `KIND_REPLY` (default: no display). |
| `src/voicebot/cli.py` | `listen` gains `--display {off,pad}` (default `off`), `--screen-name`, `--clear-after`; `--no-notfunny` dropped. |
| `pyproject.toml` | add `touchy-pad = { path = "../../app", develop = true }`. |
| `justfile` | `use-touchy-local` / `use-touchy-pypi`; a `listen-pad` convenience recipe. |
| `README.md`, `docs/plans/initial.md` | document the display + the new command contract; Stage 3 links here. |

The event flow gains exactly one hop:

```
Responder.respond(line) ─► Reply{runs, skip}
                             │
        Listener._answer ────┼──► ListenEvent(KIND_REPLY, runs=…)
                             │        │
                             │        ├──► emit()           (log / --json, unchanged)
                             │        └──► display.show()   (the pad, new)
```

* The display call happens on the **listener's worker thread** (where
  `KIND_REPLY` is produced), so it never blocks audio capture — the property the
  Stage-4a worker was introduced for.
* `HEARD` / `SKIP` never reach the display; they remain log lines.
* A display exception is caught and logged (the loop must not die for a USB
  hiccup); the display object drops its handle so the next message reconnects.
* **The idle clear is the one timer** in an otherwise event-driven design:
  `show()` (re)arms a `threading.Timer(clear_after, clear)`; a small lock
  serialises `set_properties` between the reply worker and the timer callback.

## Packaging: the `touchy-pad` dependency + `just` recipes

This is the first voicebot stage that needs the host library, so it is also where
the dependency strategy is pinned (`initial.md` always intended it here).

* **Default = path dep**, exactly like googly-vr:
  `touchy-pad = { path = "../../app", develop = true }` in the legacy
  `[tool.poetry]` layout (the file already explains *why* the legacy layout — the
  Poetry 2.x path-dep quirk).
* **Two switch recipes** in voicebot's `justfile`:

  | Recipe | Does |
  |---|---|
  | `just use-touchy-local` | Point the dep at `../../app` and reinstall (the default; the "develop against the parent repo" mode). |
  | `just use-touchy-pypi` | Point the dep at the published `touchy-pad` from PyPI and reinstall (the "someone else's checkout" mode). |

  Mechanism (see *Decisions* #8): the simplest is `poetry add --path ../../app --develop touchy-pad`
  vs. `poetry add "touchy-pad@^0.3"` inside the recipes — but that **rewrites the
  committed `pyproject.toml` + `poetry.lock`**, so switching back and forth
  creates churn. The alternative is a `touchy-local` / `touchy-pypi` **optional
  dependency group** (`poetry install --with touchy-pypi`) which leaves the
  manifest alone. Either is a few lines; the plan just needs to pick one.
* Touchy-pad is currently **`0.3.4`** and *not yet published* (`docs/pypi-checklist.md`
  in the parent repo is still unchecked), so `use-touchy-pypi` is a
  forward-looking switch: it is written now, exercised once the parent ships to
  PyPI. Until then `use-touchy-local` is the only working path — stated in the
  README so nobody is surprised.

## Touchy-pad (parent-repo) changes — the `Label.recolor` feature

This is the one thing this plan adds to the parent repo (owner decision, see
*Decisions* #1): **inline recolour**, so a label renders `#RRGGBB text#` runs in
different colours from a single string. It is a small, additive feature —
`Widget.Version` 28→29, **no** `ProtocolVersion` / `PreferencesFile` change.

### 1. Proto (`proto/widgets.proto` + the Rust mirror)

```proto
message Label {
    string text = 1;
    TextAlign text_align = 3;
    LongMode long_mode = 4;
    // When true, the label parses LVGL inline-recolour markup:
    //   "#RRGGBB text#"  → renders `text` in that colour
    // ("#" delimits a command, a space follows the colour). Plain text keeps
    // the style's text_color (white by default). Default false = today's
    // behaviour, so this is additive.
    bool recolor = 5;
}
```

Bump `Widget.Version.CURRENT` 28→29 (the root widget carries the wire version;
a new nested field moves it). `just build-proto` regenerates C / Python / Rust.

### 2. Firmware (`firmware/main/widgets/widget_builders.cpp`, `build_label`)

```c
if (w.kind.label.recolor) lv_label_set_recolor(lbl, true);
```

The label is built **once** with the flag on, and `lv_label_set_text` (the
runtime `text` property override) re-parses the markup on every change — so
there is no extra plumbing for the runtime path. Extend the existing `ESP_LOGI`
to include `recolor=%d`.

### 3. Host DSL (`app/src/touchy_pad/api/screens.py`)

`label(...)` gains `recolor: bool = False`, writing `w.label.recolor`; plus a
`build_setup_screen_touchless`/`test_screens.py` round-trip test.

### 4. Simulator (`app/src/touchy_pad/sim/widgets.py`)

Mirror the flag: split the text on `#RRGGBB …#` runs and render with Qt rich
text (`QTextDocument`), or — at minimum — don't choke and log a debug note. Add a
pytest that a `recolor=True` label round-trips and that a coloured run parses.

### 5. Docs

`docs/python-api.md` (the `label()` DSL + a short "inline colour" note), a new
entry in the lightbar stage history (the **LB3 precedent** for a Label-widget
stage; e.g. **LB17 — inline label recolour**) and an `AGENTS.md`/`CLAUDE.md`
highlight bullet — the repo's "a stage isn't done until the docs say so" rule.

> **Not voicebot-specific.** Any host app can use `label(recolor=True)` +
> `#RRGGBB …#`; voicebot is simply its first consumer, which is why the plan
> documents the feature in the parent repo rather than hiding it in voicebot.

**The owner flashes + tests this on hardware** once the whole plan is
implemented (per the `toai` note); voicebot's D2 hardware milestone depends on
it.

*(The optional sim-extends-`text_color` item from the earlier draft is dropped —
inline recolour replaces the `text_color` override entirely.)*

## Phased implementation

Each phase is independently verifiable and leaves the suite green. **D0** and
**D1** are independent; **P1** (the parent-repo feature) gates **D2**'s
on-hardware check.

> **Status (2026-11-04): DONE — all phases implemented, green, and verified on
> the real 8×8 pad.** **D0** (`/command` contract) ✅, **P1** (parent-repo
> `Label.recolor`, stage LB17) ✅, **D1** (path dep + `use-touchy-*` recipes) ✅,
> **D2** (`display.py` + `listen --display pad`) ✅, **D3** (CLI polish + docs) ✅.
> voicebot `just test` **86 passed / 2 skipped** and `just lint` clean; parent
> `just build-proto` / `just app-test` (**268 passed**) / `just app-lint` /
> `just firmware-build` all green.
>
> **Two device bugs surfaced on the first hardware run — both fixed:**
>
> 1. **`touchy_open()` died with `NOT_FOUND (3)`.** A reply left in the device's
>    bulk-IN FIFO by a previously-killed host process puts *every* later reply
>    one command behind, so the first `sys_board_info_get` of each new session
>    read a stale frame (and each failure orphaned another one). Fixed in the
>    parent repo: `TouchyClient._flush_stale_frames()` drains the FIFO at open,
>    and `close()` now takes the RPC lock so a clean close can't orphan a reply.
>    Full write-up in `docs/open-issues.md`.
> 2. **Long quips were rejected** (`INVALID_ARG` + a device-side
>    `pb_decode failed`): `SetPropertyCmd.string_value` was capped at 128 bytes,
>    i.e. 127 characters of text. Raised to **512** in `proto/touchy.options`
>    (511 characters of text — `max_size` counts the NUL terminator) and
>    re-flashed on every device; voicebot truncates a longer reply to fit.
>
> Remaining work is Stage 4/5 (STT filter, the full `creep3r` loop), not this plan.

| Phase | Deliverable | Verified by |
|---|---|---|
| **D0** | `commands.py` + `parse()` (colour runs, skip); `persona`/`responder`/`Reply` switched over; `NOTFUNNY`/`is_notfunny` removed. No display yet. | `just test` (new `test_commands.py`; updated `test_persona.py` / `test_responder.py` / `test_listen.py` / `test_cli.py`) — all network-free. |
| **P1** | *(parent repo)* the **`Label.recolor`** feature: proto + `Widget.Version` 28→29, firmware `lv_label_set_recolor`, host DSL, sim mirror, docs. | parent `just build-proto` / `just app-test` / `just app-lint` + a firmware build; **owner flashes + tests on hardware**. |
| **D1** | `pyproject` path dep + `just use-touchy-local` / `use-touchy-pypi`; `just install` green. | `just install`; `poetry run python -c "import touchy_pad"`. |
| **D2** | `display.py` (`connect`, `PadDisplay`, recolour screen build + `to_markup` + `show`, startup banner, idle clear, lazy connect), driven by `listen --display pad`. | `just test` with a **fake pad** (a stub with `board_info`/`screen_save`/`set_properties`); a manual `TOUCHY_SIM_URL` run; then hardware (needs **P1**). |
| **D3** | CLI polish: `--display`, `--screen-name`, `--clear-after`, the `0×0` remedy message; README + `initial.md` updates. | `just lint`, `just test`, README quickstart. |

**First hardware milestone** (after **P1** + **D2**): run `voicebot listen --fake
sim-overheard.txt --display pad` on a desk LED matrix and watch a multi-colour
quip scroll; then `listen --display pad` on the real mic. That is the whole point
of the stage.

## Decisions

The open questions from the first draft are settled. Three were answered by the
owner (the `toai` notes, kept verbatim in *Original notes*); the rest take the
recommended option.

| # | Decision | Consequence |
|---|---|---|
| 1 | **Multi-colour is in scope.** Inline recolour becomes a real touchy-pad feature: an optional `Label.recolor` bool; when set, the string's `#RRGGBB text#` runs render in colour. | New parent-repo work — proto + `Widget.Version` 28→29, firmware, host DSL, sim, docs (see *Touchy-pad (parent-repo) changes*). |
| 2 | **No per-reply colour state — rely on LVGL's default recolour behaviour.** Unmarked text renders in the label's `text_color` (white); only `#RRGGBB …#` runs are coloured. | Each reply is parsed in isolation, so nothing carries over and nothing needs resetting — the markup fully determines colour. |
| 3 | **A `/cmd` is a directive anywhere**, stripped from the text; unknown → stripped + WARNING; nothing left → skip. | `commands.parse` returns ordered `Run`s. |
| 4 | **`NOTFUNNY` is removed** (no legacy shim). | `persona.is_notfunny` / `NOTFUNNY` deleted; `hermes.txt` re-recorded. |
| 5 | **Startup banner `"I'm voicebot"`, cleared after 2 minutes** with nothing new; **lazy connect** — the pad is opened only when a message needs showing. | `--clear-after` (default 120 s); an idle-clear `threading.Timer`; connect-on-demand. |
| 6 | **Font by panel height** from the compiled set (8 / 16 / 30), with a `--font-size` override; geometry always from `board_info`. | Never key off the board name; works on 32×8 and the LCDs unchanged. |
| 7 | **On `0×0` (unprovisioned LED board), print the remedy once and keep looking** — never fail, never auto-provision. | One-line hint: `touchy pref from-template led-32x8`. |
| 8 | **`poetry add`-based switch recipes** for `use-touchy-local` / `use-touchy-pypi`. | README notes the `pyproject.toml` + `poetry.lock` churn and the `git checkout` way back. |

Decision 2 drops the "reset" concept entirely: a reply is parsed in isolation, so
its colour is simply whatever its own markup says. `/color:red … /color:blue …`
gives two colours in one quip; a reply with no `/color` is plain white (the
label's `text_color`) — i.e. exactly LVGL's default recolour behaviour.

### Deferred (explicitly not in this plan)

* More `/commands` (`/speed:`, `/repeat:`, `/font:`…) — a table entry away, but
  the sketch named only two.
* Non-text rendering on the matrix (shapes / images) — the touch-less default
  screen already covers pixels.
* Intra-reply *style* changes beyond colour (bold, blinking) — not requested.

## Testing strategy

* **All of it is network-free and hardware-free by default**, like the rest of
  voicebot.
* `tests/test_commands.py` (new) — the parser's contract: named + hex colours,
  case-insensitivity, colour **runs**, `/notfunny` (+ dressed-up variants),
  stripping, empty → skip, unknown → stripped + logged, a bad colour value leaves
  the run colour unchanged.
* `tests/test_responder.py` — `Reply.runs` round-trips; `/notfunny` (only) skips.
* `tests/test_listen.py` — the event carries `runs`; the **display sink** is
  called on `KIND_REPLY` only (a fake sink records the runs), and a sink that
  raises does **not** kill the loop.
* `tests/test_display.py` (new) — `PadDisplay` against a **fake pad** (a stub
  exposing `board_info` / `screen_save` / `screen_load` / `set_properties`):
  geometry→font mapping, `to_markup` (white vs `#RRGGBB …#`, `#` scrubbing), one
  `text` override per quip, the startup banner, the idle clear (driven by an
  injected clock/timer), and the `0×0` message. No real `touchy_pad` needed (the
  fake duck-types it) — and **`display.py`'s `touchy_pad` import must be
  lazy/guarded** so the module imports without the parent repo installed.
* **Parent repo (P1):** `app/tests/test_screens.py` gains a `recolor=True`
  round-trip, the sim gets a recolour test, and `just build-proto` /
  `just app-test` / `just app-lint` + a firmware build must pass.
* Existing suites (`test_persona`, `test_cli`, `test_gate`, `test_audio`) keep
  their shape, minus the removed `is_notfunny` cases.
* **Lint:** `just lint` (`ruff format` + `ruff check --fix`), as always.
* **Manual, on hardware:** `listen --fake sim-overheard.txt --display pad` (no
  mic, no model) then a real `listen --display pad`; and the same against
  `TOUCHY_SIM_URL` for the plumbing. **The owner flashes + tests** the recolour
  firmware.

## Risks / open questions

| # | Risk | Mitigation |
|---|---|---|
| R1 | **`Label.recolor` is new firmware** — until it is flashed, the LED shows the raw `#RRGGBB …#` markup. | It is a small, additive change (`lv_label_set_recolor`); the owner flashes + tests it (P1). Voicebot can be built entirely against the sim and fakes first. |
| R2 | **A literal `#` in a quip** is parsed as a recolour command and swallows the rest of the marquee (LVGL's `##` escape is dead code in this version). | The persona forbids `#`; `to_markup` strips any that slip through. |
| R3 | The model doesn't emit `/color` (or emits it badly). | The persona instructs it; a bad value leaves the run colour unchanged; a colour-less reply is exactly white text — purely additive. |
| R4 | A `0×0` / incompatible pad retries forever. | Intentional (the googly-vr rule: never exit), ≤1-line reason + the exact remedy (Decisions #7). |
| R5 | Two pads attached — `touchy_open()` picks the first. | Same as googly-vr; out of scope, revisited if it bites. |
| R6 | The sim renders recolour only approximately (rich text) or not at all. | The sim is advisory; hardware is the truth. A pytest pins the round-trip regardless. |
| R7 | **The idle-clear timer races the reply worker** (two threads calling `set_properties`). | One lock around every `set_properties`; `show()` cancels + re-arms the timer. |
| R8 | Long quips are hard to read at 32 px wide. | `--max-tokens` (already 120) bounds length; the marquee scrolls; a future `/speed` command is a table entry. |

## Acceptance criteria (definition of done)

1. `voicebot listen --display pad` on the desk matrix scrolls each quip; a
   `/color:…` reply shows colour, **including several colours within one quip**;
   `/notfunny` shows nothing.
2. The startup banner (`I'm voicebot`) appears on connect, and the marquee clears
   after `--clear-after` seconds with nothing new (default 120).
3. Works on at least the 32×8 LED matrix **and** a large LCD board with **no code
   change** (geometry + font derived from `board_info`).
4. `voicebot listen --fake sim-overheard.txt --display pad` demonstrates the
   whole path with no mic and no model.
5. `just test` green with no device, network or model; `just lint` clean; the
   existing `reply` / `listen` / `models` behaviour preserved.
6. `just install` and `poetry run python -c "import touchy_pad"` work; both
   `use-touchy-local` and `use-touchy-pypi` recipes exist and are documented.
7. `display.py` is the **only** module importing `touchy_pad`.
8. The parent-repo **`Label.recolor`** feature landed (`Widget.Version` 28→29,
   plus firmware / host DSL / sim / docs) with `just build-proto`, `just app-test`,
   `just app-lint` and a firmware build green — and the owner has flashed +
   tested it.
9. README + `initial.md` updated; `initial.md` Stage 3 links here and Stage 2's
   `NOTFUNNY` wording points at *The `/command` contract*.
10. Wire format: only `Widget.Version` moved (28→29); **no** `ProtocolVersion` /
    `PreferencesFile.Version` change.

## Relationship to `initial.md` and the docs

* This **is** `initial.md` Stage 3 ("display: scroll a quip on the LED matrix"),
  expanded from a bullet list into a build-ready plan. When it lands,
  `initial.md`'s Stage 3 section should shrink to a one-line link here (as
  `audioin.md` did for Stage 4), and Stage 2's `NOTFUNNY` description should
  point at *The `/command` contract*.
* It reuses the responder and the audio-in loop unchanged in shape — the only
  additions are the command parser and one event field.
* The parent repo's side is the **lightbar stage history**
  (`docs/hardware/lightbar/design.md`, stages LB1–LB16, plus `docs/design.md` →
  lb5–lb16) — LB3 (`long_mode`), lb6/lb10 (the `BoardConfig` chain), lb14
  (batched `SetPropertiesCmd`), lb15 (a batch wakes the panel) and lb16 (a batch
  repaints immediately) are all **prerequisites this plan consumes**, not things
  it builds.
* `docs/python-api.md` (parent) §"Overriding widget properties at runtime" is the
  API reference this plan codes against; `docs/simulator.md` + `TOUCHY_SIM_URL`
  document the no-hardware path.
* The **only** thing this plan *adds* to the parent repo is the `Label.recolor`
  feature — documented there as a new lightbar stage (**LB17**, following LB3's
  precedent for a Label-widget stage) with a `Widget.Version` 28→29 bump.
  Everything else listed above is a prerequisite it consumes.

## Original notes (the sketch this grew from)

Kept verbatim, so every decision above can be traced back to it:

> * we are now doing stage 3 - outputing funny scrolling led messages to the attached touchypad
> * use the touchypad api library to let voicebot write to the leds
> * for now you can use the app/src/touchy_pad py library but eventually i want to use the version from pypi. add just rules for 'use-touchy-pypi' and 'use-touchy-local' to switch the poetry config
> * initially we are targeting the 8x8 led version of touchypad but try not to assume that. ie. id like it to easily work on the large lcd versions also
> * instead of the NOTFUNNY token in our LLM output change the system cmd and our usage to assume that LLM output words that start with '/' are system commands to our software. heres the commands to define now:
>   * /notfunny - replaces the old NOTFUNNY usage
>   * /color:xxx - where xxx can be red/green/blue/yellow/white/0xrrggbb. the last variant lets the llm select any color. if this command is received any future text is printed in that color (until changed to a new color). the llm can assume at each new reply the default color will be white (no need to set that). encourage the llm to use colors to make things funnier or for emphasis
>   * (we might add other commands in the future)

### The owner's `toai` notes (answers to the first draft's questions)

Also verbatim — these are the decisions recorded in *Decisions*:

> toai: actually improve the touchypad parent firmware and host code to support
> inline recolor (so the llm can use multiple colors in a single reply).
> document this new feature. i recommend adding an optional 'recolor' bool to the
> Label protobuf. if recolor is set that means lvgl inline recolor parsing is
> suppored for that string. after you make the code changes for this entire plan
> ill manually flash the new code to the device and test.

> toai: no need to keep legacy NOTFUNNY - remove it

> toai: at startup default to "I'm voicebot". after 2 minutes of no new replies
> to show just clear it. btw: if not connected to a touchypad (because it was
> initially not plugged in or it got removed) - reconnect when we have a new
> message to show on it (ie connect to touchypad lazily)
