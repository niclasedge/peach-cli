"""Active-sessions card list for the startup picker.

Shows recently-active sessions as full-width vertical cards above the
picker tree. "Recently active" is defined cross-process from the DB
column `last_used`:

- `last_used < 60s`  → active (green pill, highlighted border)
- `60s ≤ x < 10min`  → idle (grey pill, dim border)
- `≥ 10min`          → hidden (still reachable via the tree below)

Each card shows the project basename above the session title and a
preview of the last agent reply (or the last user prompt as fallback).

Turn-state is derived from `turn_ended_at` vs `last_used`:

- `turn_ended_at >= last_used`  → done — show full reply text
- otherwise                     → busy — show "Agent is replying…"
  in place of the preview

Clicking / Enter on a card posts an `ActiveSessionCards.Resume`
message that the picker turns into the same session-resume flow used
by the tree.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalGroup
from textual.content import Content
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Label, Static

from peach.db import Session


ACTIVE_THRESHOLD_SECONDS = 60.0
VISIBLE_THRESHOLD_SECONDS = 600.0  # 10 minutes


def _seconds_since(iso_or_sqlite: str | None) -> float | None:
    if not iso_or_sqlite:
        return None
    text = iso_or_sqlite.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0.0, (datetime.now(timezone.utc) - dt).total_seconds())


def _relative_age(seconds: float) -> str:
    if seconds < 5:
        return "just now"
    if seconds < 60:
        return f"{int(seconds)}s ago"
    if seconds < 3600:
        return f"{int(seconds // 60)}m ago"
    return f"{int(seconds // 3600)}h ago"


def _is_turn_done(session: Session) -> bool:
    """True iff `turn_ended_at` is at-or-after `last_used` (i.e. the agent
    has finished replying to the latest prompt)."""
    ended = _seconds_since(session.get("turn_ended_at"))
    used = _seconds_since(session.get("last_used"))
    if ended is None:
        return False
    if used is None:
        return True
    # smaller seconds-since means newer; turn_end is newer than last_used → done
    return ended <= used


def filter_active(
    sessions: Iterable[Session], cutoff_seconds: float = VISIBLE_THRESHOLD_SECONDS
) -> list[Session]:
    """Return sessions whose last_used is within `cutoff_seconds`, newest first."""
    keep: list[tuple[float, Session]] = []
    for s in sessions:
        age = _seconds_since(s.get("last_used"))
        if age is None or age > cutoff_seconds:
            continue
        keep.append((age, s))
    keep.sort(key=lambda pair: pair[0])
    return [s for _, s in keep]


class ActiveSessionCard(VerticalGroup, can_focus=True):
    """One full-width card for an active or recently-active session."""

    BINDINGS = [Binding("enter", "select", "Resume", show=False)]

    DEFAULT_CSS = """
    ActiveSessionCard {
        width: 1fr;
        height: auto;
        border: round $surface-lighten-1;
        padding: 0 1;
        margin: 0 0 1 0;
        background: $boost;

        &.-active { border: round $success; }
        &.-loaded { border: round $warning; }
        &:focus, &:focus-within {
            background: $boost-darken-1;
            border: round $primary;
        }
        .header { color: $text-secondary; height: 1; }
        .body {
            height: auto;
            margin-top: 1;
        }
        .col-user, .col-agent {
            width: 1fr;
            height: auto;
            padding: 0 1 0 1;
        }
        .col-user { border-right: heavy $surface; }
        .col-label-row { height: 1; }
        .col-label {
            color: $text-secondary;
            text-style: dim italic;
            width: auto;
        }
        .col-prior-inline {
            color: $text-secondary;
            text-style: dim italic;
            width: 1fr;
        }
        .col-text { color: $text-secondary; height: auto; }
        .col-prior-text {
            color: $text-secondary;
            text-style: dim;
            height: auto;
        }
        .col-busy {
            color: $text-warning;
            text-style: italic;
            height: 1;
        }
    }
    """

    def __init__(self, session: Session, is_loaded: bool = False) -> None:
        super().__init__()
        self.session = session
        self.is_loaded = is_loaded

    def compose(self) -> ComposeResult:
        path = self.session.get("project_path") or ""
        project = Path(path).name if path else "(no project)"
        title = self.session.get("title") or "(untitled)"
        age = _seconds_since(self.session.get("last_used")) or 0.0
        is_active = age < ACTIVE_THRESHOLD_SECONDS
        done = _is_turn_done(self.session)

        # Border priority: loaded (orange) > active (green) > default.
        # Orange = a tab for this session is open in the current process,
        # so click jumps right back to it instead of resuming via ACP.
        if self.is_loaded:
            self.add_class("-loaded")
        elif done and is_active:
            self.add_class("-active")

        pill_color = "$text-success" if is_active else "$text-secondary"
        pill_glyph = "●" if is_active else "○"
        state_label = "busy" if not done else (
            "active" if is_active else "idle"
        )

        user_prompt = (self.session.get("last_user_prompt") or "").strip()
        last_reply = (self.session.get("last_reply") or "").strip()

        yield Static(
            Content.from_markup(
                f"[b]$title[/]  [dim]· $project · [{pill_color}]$glyph $state[/] · $age[/]",
                title=title,
                project=project,
                glyph=pill_glyph,
                state=state_label,
                age=_relative_age(age),
            ),
            classes="header",
        )
        with Horizontal(classes="body"):
            with VerticalGroup(classes="col-user"):
                yield Static("You", classes="col-label")
                yield Static(user_prompt or "—", classes="col-text", markup=False)
            with VerticalGroup(classes="col-agent"):
                if not done and last_reply:
                    # Busy AND a newer user prompt exists → the visible
                    # reply is the answer to the *previous* turn. Keep
                    # it on screen but spell that out, plus a "replying
                    # to new prompt" indicator so the relationship
                    # between the You / Agent columns is unambiguous.
                    with Horizontal(classes="col-label-row"):
                        yield Static("Agent", classes="col-label")
                        yield Static(
                            " ↑ reply to previous prompt",
                            classes="col-prior-inline",
                        )
                    yield Static(
                        last_reply, classes="col-prior-text", markup=False
                    )
                    yield Static(
                        "⏵ replying to new prompt…", classes="col-busy"
                    )
                elif not done:
                    # First-turn busy: the upcoming reply is the answer
                    # to the prompt shown in the You column, so don't
                    # add any "replying to new prompt" framing — the
                    # busy state is already visible from the header pill.
                    yield Static("Agent", classes="col-label")
                else:
                    yield Static("Agent", classes="col-label")
                    yield Static(
                        last_reply or "—", classes="col-text", markup=False
                    )

    def action_select(self) -> None:
        self.post_message(ActiveSessionCards.Resume(self.session))

    def on_click(self) -> None:
        self.post_message(ActiveSessionCards.Resume(self.session))


class ActiveSessionCards(VerticalGroup):
    """Header + vertical stack of full-width `ActiveSessionCard`s."""

    DEFAULT_CSS = """
    ActiveSessionCards {
        height: auto;
        margin: 0 0 1 0;

        .section-header {
            color: $text-secondary;
            text-style: bold;
        }
        &.-empty { display: none; }
    }
    """

    sessions: reactive[list[Session]] = reactive(list, recompose=True)

    class Resume(Message):
        def __init__(self, session: Session) -> None:
            super().__init__()
            self.session = session

    def __init__(self, id: str | None = None) -> None:
        super().__init__(id=id)
        # Set externally by the picker before assigning `sessions` so the
        # resulting recompose can colour the right cards orange.
        self.loaded_db_ids: set[int] = set()

    def watch_sessions(self, new: list[Session]) -> None:
        self.set_class(not new, "-empty")

    def compose(self) -> ComposeResult:
        if not self.sessions:
            return
        yield Label("Active sessions", classes="section-header")
        for session in self.sessions:
            yield ActiveSessionCard(
                session,
                is_loaded=session.get("id") in self.loaded_db_ids,
            )
