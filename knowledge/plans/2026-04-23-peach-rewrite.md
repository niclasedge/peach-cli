# Peach Rewrite Plan — Toad Fork → Claude-Code-ACP-only Windows Port

**Date:** 2026-04-23
**Source repo:** `/Users/niclasedge/GITHUB/toad-windows` (fork of `batrachianai/toad`)
**Target binary:** `peach` (parallel-installable next to `toad`)
**TaskMD project:** `toad-windows` (prefix `toad-`)

---

## Scope & Principles

**Goal.** Transform this fork of Toad into `peach` — a Claude-Code-ACP-only TUI that runs on Windows, with resumable sessions and a startup picker listing recent sessions by project.

**Non-goals** (explicitly out of scope):
- Upstream-merge compatibility with `batrachianai/toad` after the rename. This is a hard fork.
- The persistent inline Toad shell / interactive PTY tool-execution (uses fcntl, pty, termios — Unix-only).
- Any non-Claude provider (Gemini, OpenAI Codex, Copilot, Cursor, Mistral, Kimi, Kiro, Goose, etc.).
- Agent-store / agent-picker UI.

**Principles.**
- **TDD red–green.** Every code change inside Phases 1–3 is preceded by a failing test that describes the intended behavior. Phase 0 exists to make TDD possible.
- **Phase-gated.** The last task in each phase is *"tests green"*. The first task of the next phase lists the previous phase's test-task as its only dependency — no phase-hopping.
- **Small, isolated tasks.** One concern per task (rename one surface, delete one subsystem, add one migration).
- **Behavior tests over unit tests** for TUI code. We lean on `pytest-textual-snapshot` for screen regressions and `pytest-asyncio` for ACP coroutines — not a mock-heavy unit suite.
- **User checkpoint after Phase 2.** User runs `peach` hands-on before Phase 3 begins; Phase 3 tasks stay `pending` until the user confirms Phase 2 is usable.

**Reference template.** Simon Willison's `llm` repo test setup — copied verbatim to `knowledge/reference/simonw-llm-testing/` (gitignored). We adopt his PEP 735 `[dependency-groups]` convention, `pytest.ini` one-liner, flat `tests/conftest.py`, `uv run pytest` via Justfile, and `pip install . --group dev` CI-install. Same Python matrix (3.10–3.14 × Ubuntu/macOS/Windows) works for us.

---

## Phase Overview

```
Phase 0  Test-Baseline          (~2h)   — makes TDD possible on `toad` before any rename
   ↓ (0.end tests green)
Phase 1  Rename toad → peach    (~3h)   — mechanical, verified by the same tests migrated to peach names
   ↓ (1.end tests green)
Phase 2  Cleanup — shell + picker removal + Windows path fixes  (~5h)
   ↓ (2.end tests green)
━━━━━━━━  Checkpoint: user runs `peach` on macOS + Windows  ━━━━━━━━
   ↓ (user confirms)
Phase 3  Session features — startup picker, project filter, resume  (~4h)
```

**Task-ID prefix:** `toad-` (the TaskMD project is `toad-windows`; the prefix stays even after the rename, since TaskMD IDs are per-project-register, not per-repo-identity).

---

## Phase 0 — Test-Baseline (phase slug: `test-baseline`)

**Purpose.** Bootstrap pytest + a minimal green test suite against the *current* `toad` code, so the Phase 1 rename is verified end-to-end rather than by manual smoke-testing.

**Dependency chain (within phase):**

```
0.1 pytest-setup
   ↓
0.2 smoke-tests-cli
   ↓
0.3 test-db-open  ──┐
                    ├─→ 0.5 ci-workflow ─→ 0.6 phase-0-tests-green
0.4 snapshot-main ──┘
```

| ID | Title | Depends on | Done when |
|----|-------|------------|-----------|
| toad-1 | pytest-setup: add `[dependency-groups] dev` with pytest + pytest-asyncio + pytest-textual-snapshot + syrupy; create `pytest.ini`; add `test` target to `Justfile` | — | `uv sync --group dev` succeeds; `uv run pytest` exits 0 on empty suite |
| toad-2 | smoke-tests-cli: `tests/test_cli.py` — `toad --version` prints version string; `toad --help` lists `run`, `acp`, `replay`, `serve`, `about`, `settings`; import `toad` succeeds | toad-1 | 3 CLI assertions green |
| toad-3 | test-db-open: `tests/test_db.py` — open `toad.db` via `toad.db.open_db(tmp_path)` on a temp path; assert sessions table schema exists (9 columns) | toad-2 | Test green |
| toad-4 | snapshot-main: `tests/test_main_screen.py` — boot `ToadApp` via `App.run_test()`, screenshot Main screen, store snapshot baseline | toad-2 | Snapshot stored, test green |
| toad-5 | ci-workflow: `.github/workflows/test.yml` — matrix (ubuntu, macos, windows) × (py3.11, 3.12, 3.13); `pip install . --group dev` + `python -m pytest -vv` | toad-3, toad-4 | Workflow committed; local `act` or first push shows green on ubuntu & macos (windows may red — that's Phase 2's job) |
| **toad-6** | **phase-0-tests-green** — run `uv run pytest -vv` locally; all 4 test files green | toad-5 | Exit 0, ≥6 tests passed |

---

## Phase 1 — Rename `toad` → `peach` (phase slug: `rename`)

**Purpose.** Fully rebrand the package, binary, env vars, file names, and agent identity so `peach` installs alongside `toad` without collision. No behavior changes.

**Dependency chain:**

```
toad-7 (depends on toad-6)
   ↓
toad-8 pyproject
   ↓
toad-9 core-strings ──┐
                        ├─→ toad-13 docs ─→ toad-14 test-migrate ─→ toad-15 phase-1-tests-green
toad-10 env-vars     ──┤
toad-11 file-names   ──┤
toad-12 agent-identity┘
```

| ID | Title | Depends on | Done when |
|----|-------|------------|-----------|
| toad-7 | package-dir-rename: `git mv src/toad src/peach` preserving history; update all relative-import paths; `grep -r "from toad\." src/` returns 0 hits | toad-6 | `grep -r "from toad" src/peach/` empty |
| toad-8 | pyproject-rename: `name = "peach"`, entry `peach = "peach.cli:main"`, `members = ["peach"]`, `packages = ["src/peach"]`; `uv sync` rebuilds to `.venv/bin/peach` | toad-7 | `uv run peach --version` works |
| toad-9 | core-strings: `src/peach/__init__.py:NAME = "peach"`, `paths.py:APP_NAME = "peach"`, `cli.py` docstrings, `about.py` template | toad-8 | Grep `"toad"` inside `src/peach/` drops to ≤ historical references (NOTICE, attribution) |
| toad-10 | env-vars: rename `TOAD_ACP_INITIALIZE`, `TOAD_LOG`, `TOAD_CWD` → `PEACH_*`; update all consumers in `constants.py`, `acp/agent.py` | toad-8 | Grep `TOAD_` → 0 hits in code (non-comment) |
| toad-11 | file-names: `app.py:319,321` → `peach.json`, `peach.db`; any other `toad.*` literal filenames | toad-8 | App writes to `~/Library/Application Support/peach/peach.db` on macOS |
| toad-12 | agent-identity: `cli.py:208` identity domain `batrachian.ai` → `peach.local` (or user-chosen); upstream repo URL → fork URL | toad-8 | Identity string in ACP handshake reflects new domain |
| toad-13 | docs-update: README.md, NOTICE.md, CONTRIBUTING.md, CHANGELOG.md — all user-facing strings reflect `peach`; attribution to upstream Toad preserved in NOTICE | toad-9, toad-10, toad-11, toad-12 | `grep -i toad README.md` only in attribution/history paragraphs |
| toad-14 | tests-migrate: Phase-0 tests updated — `test_cli.py` asserts `peach --version`; `test_db.py` opens `peach.db`; snapshot baselines regenerated for renamed app title | toad-13 | `uv run pytest` — all 4 test files pass with peach identifiers |
| **toad-15** | **phase-1-tests-green** — full `uv run pytest -vv` green locally; snapshot diff reviewed and committed | toad-14 | Exit 0, same test count as toad-6, all green |

---

## Phase 2 — Cleanup (phase slug: `cleanup`)

**Purpose.** Delete the inline shell subsystem, the non-Claude agent picker, shell-related settings, and fix Windows-path issues. Result: `peach` opens a single Claude-Code ACP session with no provider choice and no embedded shell.

**TDD pattern for each removal task:** write one red test asserting the absence or the remaining behavior → delete code → green.

**Dependency chain:**

```
toad-16 (depends on toad-15)
   ↓
toad-17 shell-core-delete ──┐
                             ├─→ toad-20 agents-tomls-delete ──┐
toad-18 shell-conversation ─┤                                  ├─→ toad-23 settings-shell-section
toad-19 shell-prompt-mode  ─┘                                  │
                                                                ├─→ toad-24 windows-paths ─→ toad-25 phase-2-tests-green
                             toad-21 picker-screens-delete ────┤
                             toad-22 cli-claude-only          ─┘
```

| ID | Title | Depends on | Done when |
|----|-------|------------|-----------|
| toad-16 | red-test-shell-gone: `tests/test_no_shell.py` — assert `import peach.shell` raises ImportError; assert `peach.settings.Settings().shell` is not a valid field | toad-15 | Test red (reason: module + field still present) |
| toad-17 | shell-core-delete: remove `shell.py`, `shell_read.py`, `widgets/shell_terminal.py`; remove their imports from `widgets/conversation.py` (top of file) | toad-16 | toad-16 flips green; `grep "from peach.shell" src/peach/` empty |
| toad-18 | shell-conversation-cleanup: in `widgets/conversation.py` remove shell property, `post_shell()`, history-class binding, shell input/interrupt handlers, completion caching (~150 LOC); add/update snapshot test for Conversation widget | toad-17 | Conversation widget snapshot regenerated; `grep -n shell src/peach/widgets/conversation.py` only in comments or 0 hits |
| toad-19 | shell-prompt-mode-delete: in `widgets/prompt.py` remove `likely_shell()`, `is_shell_mode`, `RequestShellMode`, `CancelShell`; all input becomes pure agent prompt | toad-18 | Prompt widget snapshot still green; no `shell_mode` references |
| toad-20 | agents-tomls-delete: delete all 18 non-`claude.com.toml` files under `src/peach/data/agents/`; keep only `claude.com.toml` | toad-17 | `ls src/peach/data/agents/` == `claude.com.toml` (+ any README) |
| toad-21 | picker-screens-delete: remove `screens/store.py` and `screens/agent_modal.py`; remove their mounts from `app.py`; replace "store" default with direct Claude launch | toad-20 | `grep -rn "store\|agent_modal" src/peach/screens/ src/peach/app.py` → 0 hits |
| toad-22 | cli-claude-only: `cli.py` — accept only `claude` / `claude.com` agent id; raise on others; simplify `agents.py` to hardcode Claude Code ACP config | toad-21 | `peach --agent gemini` errors with clear message; `peach` (no flag) launches Claude Code ACP |
| toad-23 | settings-shell-section-delete: remove 48 LOC `shell` section from `settings_schema.py`; regenerate any default-settings JSON; test asserts settings schema no longer exposes `shell` key | toad-19, toad-20 | Test green; schema dump doesn't include `shell` |
| toad-24 | windows-paths-fix: replace `xdg-base-dirs` import with `platformdirs` in `paths.py`; fix `paths.py:20` `lstrip("/")` to use `Path.as_posix().lstrip("/").replace("/", "-")` so `C:\Users\...` paths work; remove `xdg-base-dirs` from pyproject deps; add `sys.platform` smoke test for path resolution | toad-23 | On macOS DB path unchanged; on Windows path resolves to `%LOCALAPPDATA%\peach\peach.db` (verified via unit test mocking `sys.platform`) |
| **toad-25** | **phase-2-tests-green** — full `uv run pytest -vv` green on macOS; manual smoke `peach` opens a Claude Code ACP session in cwd; ≤1 window, no picker UI visible | toad-24 | Exit 0; manual smoke checklist below passed |

**Phase-2 manual smoke checklist (part of toad-25):**
- [ ] `peach --help` shows no shell / no agent-picker options
- [ ] `peach` in a project dir opens Claude Code ACP without prompting
- [ ] Typing a prompt yields a response
- [ ] Ctrl-R opens SessionResumeModal (existing feature) and lists the just-created session
- [ ] `~/Library/Application Support/peach/peach.db` exists and has a new row in `sessions`

---

## ━━━ CHECKPOINT — User tests Peach ━━━

After toad-25 is **completed** (user-approved, not just tests green), the user runs `peach` hands-on. Phase 3 tasks stay `pending` until the user sets toad-25 to `completed` (not just `in-review`).

---

## Phase 3 — Session Features (phase slug: `session-features`)

**Purpose.** Resumable sessions across restarts, a **startup picker** listing recent sessions with project name + preview, project-filtered resume.

**Existing foundation** (discovered during Phase 0 exploration):
- `db.py` already has `sessions` table with `agent_session_id` (ACP resume id), `title`, `last_used`, `meta_json` (cwd lives here).
- `screens/session_resume_modal.py` already displays recent sessions.
- ACP client in `acp/agent.py` already supports `loadSession`.

**What's missing:**
- `project_path` column for grouping/filtering (currently in `meta_json` as free-form).
- Startup picker (currently the resume modal is only reachable via Ctrl-R *after* launch).
- Persistent insert timing: session currently DB-inserted only after ACP sessionId arrives (race condition if agent crashes early).

**Dependency chain:**

```
toad-26 (depends on toad-25)
   ↓
toad-27 migration-project-path
   ↓
toad-28 session-tracker-persist-early
   ↓
toad-29 recent-query-api ──┐
                            ├─→ toad-31 picker-wire-app-launch ─→ toad-32 resume-roundtrip-test ─→ toad-33 phase-3-tests-green
toad-30 startup-picker-screen ┘
```

| ID | Title | Depends on | Done when |
|----|-------|------------|-----------|
| toad-26 | red-test-startup-picker: `tests/test_startup_picker.py` (skipped-red) — assert `peach` without args launches a picker screen listing sessions grouped by project_path | toad-25 | Test fails (no such screen yet) |
| toad-27 | db-migration-project-path: add `project_path TEXT` column to `sessions` table via migration; backfill from `meta_json.cwd` where possible; update schema tests | toad-26 | Migration applied on existing DB; test asserts column exists and backfill worked |
| toad-28 | session-tracker-persist-early: move DB insert from `acp_new_session` response-handler to `SessionTracker.new_session()`; insert with `project_path = cwd`; update later with ACP sessionId when it arrives | toad-27 | Closing peach before ACP handshake still leaves a row in DB; test covers race |
| toad-29 | recent-query-api: `db.sessions_recent(limit=N, project_path=None)` — returns list grouped/sortable by project; test with 5 fixture sessions across 3 projects | toad-28 | Query returns correct grouping; `[project_path → [sessions]]` shape |
| toad-30 | startup-picker-screen: `screens/startup_picker.py` — Textual screen showing "New Session in \<cwd\>", then recent sessions grouped by project with age + title preview; bindings: `enter`=select, `n`=new, `esc`=quit | toad-28 | Screen renders correctly; snapshot test covers empty state + populated state |
| toad-31 | picker-wire-app-launch: `cli.py` / `app.py` — when `peach` invoked with no explicit session flag, show StartupPickerScreen as first screen; on "new" → current behavior; on resume → call `acp_load_session(sessionId, cwd)` | toad-29, toad-30 | toad-26 (previously red) now green |
| toad-32 | resume-roundtrip-test: integration test — create a session, close app, reopen peach, pick recent session from startup picker, assert ACP `loadSession` fires with correct id | toad-31 | End-to-end test green (uses mocked ACP subprocess) |
| **toad-33** | **phase-3-tests-green** — full `uv run pytest -vv` green on macOS + Windows; manual checklist passed | toad-32 | Exit 0; picker works hands-on |

---

## Task Count Summary

| Phase | Tasks | First ID | Last ID |
|---|---|---|---|
| 0 Test-Baseline | 6 | toad-1 | toad-6 |
| 1 Rename | 9 | toad-7 | toad-15 |
| 2 Cleanup | 10 | toad-16 | toad-25 |
| 3 Session Features | 8 | toad-26 | toad-33 |
| **Total** | **33** | | |

---

## Open questions (to resolve before / during Phase 1)

1. **Agent identity domain** — `peach.local`, `peach.custom.niclasedge.com`, or other? Used in `cli.py:208` as `identity = f"{command_name}.custom.{domain}"`. Default suggested: `peach.local`.
2. **Startup picker scope when cwd is a known project** — show all sessions, or project-filtered by default with "show all" toggle? Suggested: filtered by default, `a` to show all.
3. **DB migration from existing `toad.db`** — offer one-time import on first `peach` run, or start fresh? Suggested: start fresh (YAGNI, user is testing in parallel anyway).

These do not block Phase 0 or Phase 1 and will be resolved when the respective tasks start.

---

## Success Criteria (overall)

- `peach` binary exists and runs on macOS (Phase 2) and Windows (Phase 2 windows-paths task verified).
- No trace of `toad` as a user-facing identifier anywhere in `src/peach/` (attribution to upstream in NOTICE.md is the only exception).
- All 18 non-Claude provider TOMLs gone; shell subsystem gone; agent-picker UI gone.
- Startup of `peach` shows a session picker with recent sessions grouped by project, resumable via ACP `loadSession`.
- `uv run pytest -vv` is green on the current platform, CI matrix runs all three OSes.
