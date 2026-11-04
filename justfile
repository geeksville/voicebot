# voicebot — dev tasks (Poetry project). See docs/plans/initial.md.

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

# Ask the LLM for a witty reply to each overheard line.
# Examples: `just reply -- --line "the bread is done baking"`
#           `just reply -- -f sim-overheard.txt`
reply *args: install
    poetry run voicebot reply {{args}}

# List the models the remote server has pulled.
models *args: install
    poetry run voicebot models {{args}}
