# ADR-005: Read-only enforced by construction, not by prompt

Status: accepted (2026-07-09)

## Problem

Minions must never mutate the repository (no writes, commits, branch changes).

## Alternatives considered

- **Prompt instructions** — not enforcement.
- **Generic shell tool + command blocklist** — blocklists on arbitrary shell
  are famously leaky (`bash -c`, redirection, `tee`, git aliases...).
- **OS sandboxing** (sandbox-exec, containers) — real defense but heavy for
  v1 and platform-specific.
- **In-process tools with no shell access** — the tool registry simply
  contains no write-capable operation; there is nothing to escape *to*.

## Decision

All minion tools are Python implementations with typed arguments:

- Filesystem tools resolve every path against the repo root and reject
  escapes via `Path.resolve()` containment checks (symlink-safe).
- `search` uses `git grep` / pure-Python scanning — read-only by nature.
- Git tools shell out to `git` with a **fixed argv allowlist per tool**
  (`log`, `diff`, `blame`, `show`), never through a shell, with `--no-pager`
  and no user-controlled flag injection (arguments that start with `-` are
  rejected; paths go after `--`).
- The only filesystem write in the whole system is the run trace, written to
  a state directory *outside* the repo (`~/.local/state/minions/`).

## Drawbacks

- Less flexible than a shell for exotic investigations (e.g. running a build
  to read its errors). If that need materializes it must arrive as a new
  vetted read-only tool, never as a generic shell.
