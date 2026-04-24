# NOTICE

**Peach CLI** is a rewrite by Niclas Edge, inspired by and derived from
**toad** (https://github.com/batrachianai/toad) by Will McGugan, licensed
under the GNU Affero General Public License version 3 (AGPL-3.0). The
full upstream license text is preserved in [`LICENSE`](./LICENSE), and
the original toad README is preserved in
[`UPSTREAM_README.md`](./UPSTREAM_README.md).

## Attribution

- **Upstream source (AGPL-3.0):** `batrachianai/toad` — © Will McGugan.
  All rights reserved by the original author except as granted by AGPL-3.0.
- **Peach CLI (this project, AGPL-3.0):** `niclasedge/peach-cli` —
  rewrite and Windows port © 2026 Niclas Edge, also released under
  AGPL-3.0.

Because AGPL-3.0 is copyleft, Peach remains AGPL-3.0 regardless of how
much of the upstream code is retained or rewritten in Peach's own idiom.

## Scope of Peach vs. upstream toad

Peach is narrowly scoped to running Claude Code via the Agent Client
Protocol (ACP) natively on Windows, macOS, and Linux. The following
upstream features are intentionally out of scope and not ported:

- All non-Claude providers (Gemini, OpenAI Codex, Copilot, Cursor,
  Mistral, Kimi, Goose, OpenHands, …) and the agent-store / picker UI.
- The integrated persistent shell and PTY-based interactive terminal
  (upstream uses Unix-only `fcntl` / `pty` / `termios`).

Peach-specific modifications are concentrated in:

- `pyproject.toml` — Python version constraint, dependency adjustments,
  package rename.
- `src/peach/paths.py` — cross-platform path handling via `platformdirs`.
- `src/peach/_pty_compat.py` (new) — POSIX/Windows abstraction shim.
- `src/peach/shell.py` — no-op stub; integrated shell removed.
- `src/peach/widgets/command_pane.py` — pipe-based fallback for install
  modal.
- `src/peach/widgets/terminal_tool.py` — pipe-based
  `asyncio.create_subprocess_exec` implementation of ACP
  `terminal/create`.
- `src/peach/screens/startup_picker.py` (new) — startup picker listing
  recent sessions grouped by project.
- `src/peach/db.py` — `project_path` column + backfill migration, early
  session persistence.

Files meaningfully modified by Peach carry an inline marker:

```
# Modified YYYY-MM-DD by niclasedge (peach): <reason>
```

## Your rights and obligations

Because Peach is AGPL-3.0:

- You may use, study, modify, and redistribute this software.
- Any redistribution — including running it as a network-accessible
  service — requires that you also make the complete corresponding
  source code available to the recipient/user under AGPL-3.0.
- You may not sublicense under more permissive terms.

Commercial licensing questions about the upstream code must be directed
to the upstream project. Peach itself does not grant any additional
licenses beyond AGPL-3.0.
