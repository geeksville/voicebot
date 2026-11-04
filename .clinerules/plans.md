# Plans

Design and implementation plans live in `docs/plans/*.md` (kebab-case) and are
tracked in git.

## Rules

- When I create or edit a plan, I MUST save it as `docs/plans/<topic>.md`. Create
  the directory if it does not exist yet.
- Always persist plans to that directory so they can be committed — never leave a
  plan only in chat or in a temporary location.
- One plan per file. Update the existing file for a topic instead of creating a
  near-duplicate; use dated filenames only for an explicit supersession.
- A plan should include: goal/summary, approach, library/technology choices with
  rationale, file & component layout, a phased sequence, testing strategy, and
  risks/open questions.
- Do not delete a plan; mark it superseded and link the replacement.

## Existing plans

- `docs/plans/initial.md` — the original voicebot plan (the responder CLI).
- `docs/plans/audioin.md` — the audio-in stage (mic → Moonshine → gate → reply).
- `docs/plans/ledout.md` — the LED-out stage (scroll quips on a touchy-pad).
- `docs/plans/standalone.md` — extracting voicebot to its own repo (packaging,
  PyPI name, CI, devcontainer).

Docs that are *not* plans: `docs/TODO.md` (loose backlog), `docs/hardware.md`
(hardware notes), `docs/responder.md` / `docs/transcribe.md` (research notes).
