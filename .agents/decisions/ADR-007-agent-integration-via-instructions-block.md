# ADR-007: GRU integration via a managed AGENTS.md instructions block

Status: accepted (2026-07-10)

## Problem

A frontier agent working in some *other* repository has no way to know that
minions exists, when to delegate, or how to read the reports. How does the
capability get discovered per-repo?

## Alternatives considered

- **MCP server registration** — only reaches MCP hosts and puts the tool
  schema in the agent's context on every session; rejected as primary
  integration for the same reasons as ADR-002.
- **Rely on the human to paste instructions** — works once, drifts forever;
  no upgrade path when the CLI contract changes.
- **A managed block in the repo's agent-instructions file** — every serious
  coding agent already reads AGENTS.md/CLAUDE.md; a short block there is the
  cheapest possible discovery mechanism and costs tokens only in repos that
  opted in.

## Decision

`minions init [--repo PATH] [--file AGENTS.md]` appends a sentinel-marked
block (`<!-- minions:begin -->` … `<!-- minions:end -->`) to the target
repo's AGENTS.md (creating the file if absent):

- **Append, never replace** — hand-written content around the block is
  untouched (verified by tests).
- **Idempotent and upgradeable** — re-running replaces only the block
  between the markers, so new CLI versions can refresh stale instructions.
- **Token-conscious** — the block is ~25 lines; it rides in every agent
  context for that repo, so brevity is a feature requirement, not style.
- This is deliberately the **only write path into any repository** in the
  package. Investigation remains read-only by construction (ADR-005); init
  is an explicit human-invoked setup step touching exactly one file.

## Drawbacks

- Repos whose agents read a different file need `--file` (e.g. CLAUDE.md).
- The block describes the CLI contract; if the contract changes, users must
  re-run `minions init` per repo. Acceptable: the marker structure makes that
  a one-command refresh, and the exit-code/flag contract is versioned
  conservatively (ADR-002).
