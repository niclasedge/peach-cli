# Changelog

All notable changes to Peach CLI are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Peach is a rewrite by Niclas Edge, inspired by Will McGugan's
[toad](https://github.com/batrachianai/toad). Entries before Peach's first
release are not reproduced here — the upstream toad history is available
in the original repository. Only Peach-specific changes are tracked below.

## [Unreleased]

### Added

- Native Windows support via `platformdirs` (state/config/cache resolve to
  `%LOCALAPPDATA%\peach\peach.db` etc.).
- Startup picker listing recent sessions grouped by project path; Enter
  resumes, `n` starts a new session, `d` deletes a session row.
- Active-session cards above the picker tree showing the latest user
  prompt (left) and agent reply (right) per session; busy / active /
  idle state derived from `last_used` and `turn_ended_at`.
- `last_user_prompt`, `last_reply`, `turn_ended_at` columns on the
  sessions table for cross-process / cross-device card previews.
- Resuming a session that is already loaded as a mode in the current
  process now switches to that mode instead of spawning a duplicate.
- Optional sidebar "Project overview" panel that surfaces TaskMD state
  via the `task` CLI (cc-task) — Termine / In Arbeit / Waiting / Next
  task lists are pulled from `task info --format json`.
- LAN-friendly `peach serve`: when bound to `0.0.0.0` / `::`, the public
  URL is auto-derived from the primary LAN IP so browser-side WebSocket
  + static URLs resolve from remote devices. `--public-url` still
  overrides.
- `project_path` column on the sessions table with backfill migration.
- Early session persistence: DB row is inserted at session creation, then
  updated with the ACP `agent_session_id` once the handshake completes —
  crash-mid-handshake sessions are no longer lost.

### Changed

- Scope narrowed to Claude Code ACP only. Other providers and the agent
  store / agent picker UI have been removed.
- Package, binary, env vars, and file names renamed from `toad` to
  `peach`:
  - Python package `src/toad` → `src/peach`
  - Binary `toad` → `peach`
  - Env vars `TOAD_LOG`, `TOAD_CWD`, `TOAD_ACP_INITIALIZE` → `PEACH_*`
  - Config/state files `toad.json` / `toad.db` → `peach.json` / `peach.db`
  - Agent identity domain `batrachian.ai` → `peach.local`
- Path sanitisation in `src/peach/paths.py` is now Windows-safe
  (no Unix-only `lstrip("/")` on absolute paths).

### Removed

- Integrated persistent shell (`src/peach/shell.py` is a no-op stub).
- PTY-based interactive tool execution (uses Unix-only `fcntl`, `pty`,
  `termios`). ACP `terminal/create` over pipes is the only execution
  channel.
- `xdg-base-dirs` dependency (crashes on Windows).
- All non-Claude providers (Gemini, Codex, Copilot, Cursor, Mistral,
  Kimi, Goose, OpenHands, …) and the agent-store screen.

### Upstream attribution

Peach starts from toad's AGPL-3.0 codebase; all redistribution continues
under AGPL-3.0. See [`NOTICE.md`](./NOTICE.md) for per-file attribution
and the preserved upstream README in
[`UPSTREAM_README.md`](./UPSTREAM_README.md).
