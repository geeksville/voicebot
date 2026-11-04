# Terminal safety

Never leave a shell waiting at a secondary prompt (`dquote>` / `quote>` /
`heredoc>`) — a command line that does gets stuck forever. Keep each command a
single, simple statement; use a properly-terminated heredoc or a temp script for
anything long. If a command seems to hang, check whether the process actually
started before re-running the same line.

## What blocks in this repo

- **`git`** — always `--no-pager` (`git --no-pager log|diff|show|branch -v`).
- **`just install` / `poetry install`** — pass `--no-interaction`; the first run
  downloads wheel deps, including the `moonshine-voice` native wheel. Give it a
  bounded `timeout` and/or let it finish rather than polling.
- **`just test`** — fast and network-free. `VOICEBOT_LIVE=1 just test` hits the
  real remote server, and the live audio test opens the mic and may download a
  Moonshine model.
- **`voicebot listen`** — runs until Ctrl-C (it streams the mic). Never run it in
  the foreground and wait: use `--fake FILE` for a finite, hardware-free run.
- **`voicebot reply` / `voicebot models`** — one-shot, but need network to the
  Ollama server.
- **Device I/O is not guaranteed.** No mic / no touchy-pad is the normal state in
  CI and on a dev box: use `--fake` and the fakes in `tests/` rather than
  retrying against hardware.
