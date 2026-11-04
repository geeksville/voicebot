# Searching

This is a small, single-language (Python) repo — a plain `grep -rn` (or your
editor's search) is enough. There is no vector index to keep in sync.

- Search `src/` and `tests/` for code; `docs/plans/` for design rationale.
- The modules are small (tens of lines) — prefer reading the whole file over
  guessing from a snippet.
- Keep searches out of `.venv/`, `dist/`, `build/`, `__pycache__/`,
  `.pytest_cache/` and `.ruff_cache/`.
- Use the repo's own vocabulary: a **"quip" / "reply"** is a model response,
  **"the gate"** is `gate.py`, **"the display"** is `display.py`, **"the command
  channel"** is `commands.py`, **"the responder"** is `responder.py`.
