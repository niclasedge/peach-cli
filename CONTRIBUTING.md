# Contributing to Peach CLI

Thanks for your interest in Peach!

Before sending a PR, please open a
[Discussion](https://github.com/niclasedge/peach-cli/discussions) so the
change can be scoped together. PRs that do not reference a discussion may
be closed without review.

## Development

```
uv sync --group dev
uv run peach
uv run pytest -vv
```

Tests require Python 3.14+.

## Upstream

Peach is a rewrite inspired by, and derived from, Will McGugan's
[toad](https://github.com/batrachianai/toad). Peach's scope is narrower
(Claude Code ACP only, native Windows) — changes aimed at upstream toad's
broader feature set belong in the upstream repository, not here.
