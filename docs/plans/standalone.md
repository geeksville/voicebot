# voicebot — extracting to a standalone repo

## Goal

Make `voicebot` a self-contained project that no longer needs the touchy-pad
source tree: depend on the *published* `touchy-pad` package, ship a trimmed
devcontainer, add CI + PyPI release workflows, and be movable out of
`touchy-pad/tools/voicebot` with no code changes.

## Deliverables (this pass)

- **`.devcontainer/`** — a trimmed copy of the parent's (Python, Poetry, just,
  libusb, ALSA/PortAudio, host `/dev/snd` + host PipeWire wiring). Dropped:
  ESP-IDF, Rust/Tauri, Deno, GTK/StreamController, the Qt runtime for the
  touchy-pad simulator GUI, and protoc/nanopb.
- **`.github/workflows/`** — `ci.yml` (ruff + pytest + build, on
  ubuntu/macos/windows), `release.yml` (test → OIDC PyPI publish on a GitHub
  Release), `testpypi.yml` (manual dry run).
- **`pyproject.toml`** — distribution name **`touchy-voicebot`**;
  `touchy-pad = ">=0.3.8"` from PyPI; PyPI metadata (keywords/classifiers/urls).
- **`justfile`** — `build`, `bump-version`, and `use-touchy-local` /
  `use-touchy-pypi` recipes for switching the dependency.
- **`README.md`**, **`AGENTS.md`** (+ `CLAUDE.md` symlink), **`.clinerules/`**.

## Key decisions

| Decision | Choice | Why |
|---|---|---|
| PyPI name | `touchy-voicebot` | The bare name `voicebot` is already taken on PyPI (someone else's 0.0.1). |
| Import package / console script | `voicebot` (unchanged) | Only the *distribution* name changes; keeps the code diff tiny. |
| `touchy-pad` dependency | PyPI `>=0.3.8` (default) | The floor is the first release with the host API voicebot's `--display pad` uses (`SetPropertiesCmd` / `build_property_override` + `Label.recolor` from 0.3.5, `Label.scroll_speed_px_s` — the marquee speed — from 0.3.8). `just use-touchy-local` (path dep on `../../app`) stays the dev path for host-library work. |
| CI OS matrix | ubuntu + macos + windows | `moonshine-voice` ships wheels for linux x86_64/arm64, macos arm64, win_amd64; the tests import no native libs, so all three install + run. |
| Devcontainer | strip to Python + audio + USB | voicebot devs do not build firmware or run the sim GUI. |

## Notes / open questions

- **Touchy-pad floor**: `pyproject.toml` requires `touchy-pad >= 0.3.8` (settled
  — 0.3.5 shipped the `--display pad` host API, 0.3.8 added
  `Label.scroll_speed_px_s`) and `poetry.lock` is committed, so a fresh
  `poetry install` / CI resolve just works. `just use-touchy-local` re-locks
  against the sibling `../../app` tree for host-library work;
  `just use-touchy-pypi` puts the published package back.
- **Trusted publishing**: create the `touchy-voicebot` project on PyPI with a
  trusted publisher (workflow `release.yml`, environment `pypi`), plus a
  `testpypi` environment for the dry run. Until that exists the release workflow
  will fail at the publish step.
- **Version sync**: the version lives in `pyproject.toml` *and*
  `src/voicebot/__init__.py`; `just bump-version` keeps both in step.
- Once extracted, the `docs/plans/initial.md` "extraction" risk item is
  resolved and the repo can drop its `tools/voicebot` framing.
