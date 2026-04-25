# 🍑 Peach CLI

**toad cli for win** — a Claude Code ACP client for the terminal, written for
native Windows, macOS, and Linux.

Peach is a rewrite by [@niclasedge](https://github.com/niclasedge), inspired by
Will McGugan's [toad](https://github.com/batrachianai/toad). The upstream
codebase is the starting point under AGPL-3.0 (see
[`NOTICE.md`](./NOTICE.md) and [`LICENSE`](./LICENSE) for attribution), but
scope, platform support, and architecture are Peach's own.

## What Peach does

- **Claude Code ACP only.** One agent, one code path. Other providers
  (Gemini, OpenAI Codex, Copilot, Cursor, Mistral, Kimi, Goose, …) are out
  of scope.
- **Native Windows.** `platformdirs` in place of `xdg-base-dirs`; paths
  resolve to `%LOCALAPPDATA%\peach\peach.db` on Windows,
  `~/Library/Application Support/peach/peach.db` on macOS,
  `~/.local/share/peach/peach.db` on Linux.
- **No integrated shell.** The persistent inline shell and PTY-based
  interactive tool execution (Unix-only `fcntl` / `pty` / `termios`) are
  removed. ACP `terminal/create` over pipes is the only execution channel.
- **Resumable sessions.** Startup picker lists recent sessions grouped by
  project path; resume reloads the prior ACP conversation context via
  `loadSession`.

## Install

```
uv tool install git+https://github.com/niclasedge/peach-cli
```

Or, from a cloned checkout:

```
uv sync --group dev
```

## Run

```
peach
```

Inside a project directory, `peach` opens Claude Code ACP in the current
working directory and persists the session to the platform-appropriate
state directory listed above.

### Environment

- `PEACH_LOG` — path to ACP agent log file (overrides default under state dir).
- `PEACH_CWD` — override cwd passed to the ACP subprocess.
- `PEACH_ACP_INITIALIZE` — set to `0` to skip ACP handshake (replay mode).

### Web UI (`peach serve`)

```
peach serve -H 0.0.0.0 -p 8822
```

Binds to all interfaces. The public URL embedded in the served HTML
(WebSocket + static asset URLs) is auto-derived from the machine's
primary LAN IP so remote browsers can connect. Pass `--public-url
https://example.com` to override (e.g. behind a reverse proxy).

## Sessions

Every conversation is a *session*. Peach persists them automatically so you
can pick up where you left off.

- **Auto-save** — each new conversation creates a row in the `sessions` table
  on first message; `last_used` and `prompt_count` are updated as you type.
  No "save" button, no manual export.
- **SQLite storage** — single file `peach.db`, created on first run under
  the platform state directory:

  | OS | Path |
  |----|------|
  | Windows | `%LOCALAPPDATA%\peach\peach.db` |
  | macOS | `~/Library/Application Support/peach/peach.db` |
  | Linux | `~/.local/share/peach/peach.db` |

  The schema is migrated in-place on startup, so upgrades don't wipe history.
- **Startup picker** — launching `peach` without args shows recent sessions
  grouped by project path. `Enter` resumes the highlighted one (reloads the
  ACP context via `loadSession`); `n` starts a fresh session in the current
  directory; `d` deletes a session row after confirmation; `Esc` quits.
- **Active-session cards** — above the picker tree, full-width cards show
  the latest *You* prompt (left) and *Agent* reply (right) for sessions
  whose `last_used` is within the last 10 minutes. Cards show a green
  border when the turn is finished and `last_used < 60s`, a yellow
  border with `⏵ replying…` when the agent is mid-turn, and a grey
  border when the session is idle. Click or `Enter` on a card to
  resume — if the session is already loaded as a mode in this process,
  Peach switches to it instead of spawning a duplicate.
- **Auto-resume** — when exactly one session has `last_used < 60s` at
  startup (typical hand-off case from another device), Peach skips the
  picker and resumes that session directly. `Ctrl+H` always returns to
  the picker.
- **Sidebar panel** — `Ctrl+B` opens the sidebar; the top panel *Sessions*
  lists recent conversations of the current project with a compact timestamp
  (`HH:MM` today, `dd.mm. HH:MM` otherwise). `Enter` on a leaf resumes that
  session in place.
- **Sessions screen** — `Ctrl+S` opens the full sessions view across all
  projects. `Ctrl+[` / `Ctrl+]` navigate between open sessions without
  leaving the main screen.
- **Rename & close** — use `/peach:rename <name>` to give a session a
  friendly title (shown in the picker and sidebar), `/peach:session-close`
  to end the current one, and `/peach:session-new` to branch off a new one
  in the same working directory.

## Project overview (TaskMD integration)

Optional sidebar panel that surfaces the current project's TaskMD state.
Only shown when the [`task` CLI](https://github.com/niclasedge/cc-task)
is installed on `PATH`; otherwise the panel is silently omitted.

When present, it runs `task info --format json` in the project cwd and
renders the project name plus any non-empty task lists:

- **Termine** — tasks with due dates
- **In Arbeit** — currently in-progress / in-review tasks
- **Waiting** — tasks waiting on dependencies
- **Next** — top-N recommended tasks from `task next`

Task rows display as `{id}  {P}  {title}` with a color-coded priority
letter (H/M/L). Empty sections are omitted.

If `task` is installed but the current directory is not a tracked
TaskMD project, the panel shows `No TaskMD project for this directory.`
instead of the sections.

## Slash commands

Type `/` in the prompt to open the command menu. Peach ships these built-ins:

| Command | Purpose |
|---------|---------|
| `/peach:about` | Show the about screen |
| `/peach:clear` `<n?>` | Clear the conversation window (optional: keep last *n* lines) |
| `/peach:rename <name>` | Give the current session a friendly name |
| `/peach:session-new <prompt?>` | Open a new session in the current working directory |
| `/peach:session-close` | Close the current session |

Claude Code ACP also publishes its own slash commands (`/compact`, `/review`,
project-level custom commands, …). Peach merges them into the same menu — just
keep typing after `/` to filter.

## Keyboard shortcuts

### Global (anywhere in the app)

| Key | Action |
|-----|--------|
| `Ctrl+B` | Toggle sidebar (project files, sessions, tool log) |
| `Ctrl+S` | Sessions screen |
| `Ctrl+H` | Home |
| `Ctrl+[` / `Ctrl+]` | Previous / next session |
| `F1` | Help panel |
| `F2` or `Ctrl+,` | Settings |
| `Ctrl+Q` | Quit Peach |
| `Ctrl+C` | Interrupt running command (press again to quit) |

### Prompt (where you type)

| Key | Action |
|-----|--------|
| `Enter` | Send prompt to the agent |
| `Shift+Enter` / `Ctrl+J` | Insert newline / send multi-line prompt |
| `Tab` | Path auto-complete |
| `@` | Open file picker / fuzzy path search |
| `/` | Open slash-command menu |
| `Esc` | Dismiss popup (slash menu, path search, mode switcher) |
| `Ctrl+O` | Mode switcher (plan / accept edits / bypass) |

### Conversation view

| Key | Action |
|-----|--------|
| `Alt+↑` / `Alt+↓` | Move block cursor up / down |
| `Space` | Expand / collapse the focused block |
| `Enter` | Select / act on the focused block |
| `Esc` | Cancel the agent's current turn |
| `Ctrl+F` | Focus the active terminal block |
| `End` | Jump back to the prompt |

### Startup picker

| Key | Action |
|-----|--------|
| `Enter` | Resume the highlighted session (or click an active card) |
| `n` | Start a new session in the current directory |
| `d` | Delete the highlighted session (with confirmation) |
| `Esc` | Quit |

## Development

```
just test
```

or

```
uv run pytest -vv
```

Tests require Python 3.14+.

## License

AGPL-3.0. See [`LICENSE`](./LICENSE) and [`NOTICE.md`](./NOTICE.md) for
attribution to the upstream toad project. The `UPSTREAM_README.md` file
preserves the original toad README for reference.
