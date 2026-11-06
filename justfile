# voicebot — dev tasks (Poetry project). See docs/plans/standalone.md.

# List available recipes.
default:
    @just --list

# Create/update the venv and install deps.
install:
    poetry install --no-interaction

# Run the pytest suite (network-free; VOICEBOT_LIVE=1 enables the live smoke).
test: install
    poetry run pytest -q

# Format + lint.
lint:
    poetry run ruff format src tests
    poetry run ruff check --fix src tests

# Build the wheel + sdist into dist/.
build:
    poetry build

# Ask the LLM for a witty reply to each overheard line.
# Examples: `just reply -- --line "the bread is done baking"`
#           `just reply -- -f sim-overheard.txt`
reply *args: install
    poetry run voicebot reply {{args}}

# Listen to the mic, transcribe, and scroll a witty reply per utterance on the pad.
# `--fake FILE` replays a text file instead (no mic, no model).
listen *args: install
    poetry run voicebot listen {{args}}

# --- touchy-pad dependency ---------------------------------------------------
# The default dependency is the *published* touchy-pad package (see
# pyproject.toml). `use-touchy-local` swaps in the sibling ../../app checkout
# while hacking on the host library itself; `use-touchy-pypi` restores the
# published one. Both rewrite pyproject.toml + poetry.lock (committed files), so
# the way back is `git checkout pyproject.toml poetry.lock`.

# Point the touchy-pad dependency at the sibling checkout (../../app).
use-touchy-local:
    #!/usr/bin/env bash
    set -euo pipefail
    poetry add --no-interaction --path ../../app --develop touchy-pad
    poetry install --no-interaction

# Point the touchy-pad dependency back at the published PyPI package (the default).
use-touchy-pypi:
    #!/usr/bin/env bash
    set -euo pipefail
    poetry add --no-interaction "touchy-pad@>=0.3.8"
    poetry install --no-interaction

# List the models the remote server has pulled.
models *args: install
    poetry run voicebot models {{args}}

# --- release -----------------------------------------------------------------

# Bump the version, commit, tag it "vX.Y.Z", and push both the commit and the
# tag to origin. Bumps the patch component of the semver in pyproject.toml and
# in src/voicebot/__init__.py, or use the given version (e.g. `just bump-version
# 0.2.0`). Requires a clean git index on the branch being pushed.
bump-version VERSION="":
    #!/usr/bin/env bash
    set -euo pipefail
    ver=$(sed -n 's/^version = "\([0-9][0-9.]*\)"/\1/p' pyproject.toml | head -n1)
    if [ -z "$ver" ]; then
        echo "bump-version: could not read version from pyproject.toml" >&2
        exit 1
    fi
    if [ -n "{{VERSION}}" ]; then
        new_ver="{{VERSION}}"
    else
        IFS='.' read -r major minor patch <<< "$ver"
        new_ver="$major.$minor.$((patch + 1))"
    fi
    # pyproject.toml (the [tool.poetry] version line only — not dependency specs)
    sed -i "s/^version = \"[0-9][0-9.]*\"/version = \"${new_ver}\"/" pyproject.toml
    # ... and the runtime __version__ (the CLI's --version reads this).
    sed -i "s/^__version__ = \"[0-9][0-9.]*\"/__version__ = \"${new_ver}\"/" src/voicebot/__init__.py
    echo "Bumped: $ver → $new_ver"
    git add pyproject.toml src/voicebot/__init__.py
    git commit -m "chore: bump version to v${new_ver}"
    git tag "v${new_ver}"
    git push
    git push origin "v${new_ver}"
    echo "✓ Tagged and pushed v${new_ver}"
