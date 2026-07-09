# ADR-002: Library core with a CLI as the first adapter (not MCP)

Status: accepted (2026-07-09)

## Problem

How does GRU (Claude Code, Codex, Cursor, any frontier agent) invoke a minion?
The brief explicitly says: do not assume MCP.

## Alternatives considered

- **MCP server** — standard for tool integration, but only reaches MCP hosts,
  adds a session/protocol layer, and (critically) MCP tool *definitions and
  results* live in GRU's context — the thing we're trying to shrink.
- **HTTP/gRPC daemon** — a daemon earns its keep when it holds expensive
  state. Here the expensive state (model weights, KV cache) already lives in
  the omlx server; a resident minion daemon would hold nothing but config.
- **CLI over stdio** — every frontier agent already has a shell tool; a CLI
  is the lowest-common-denominator integration with zero protocol overhead.
  Cost per invocation is process startup, which is noise vs. inference.

## Decision

Architecture is a **library core** (`InvestigationService`) with thin
adapters. The first adapter is a CLI: `minions investigate "<question>"`.
GRU reads the report from stdout. MCP and HTTP adapters remain cheap to add
later because nothing in the core knows about the transport.

## Drawbacks

- No streaming/progress to GRU mid-investigation (acceptable: the compact
  final report is the product).
- CLI arg/stdout contract must stay stable once GRU-side docs (AGENTS.md)
  reference it; version it via `--json` schema `version` field.
