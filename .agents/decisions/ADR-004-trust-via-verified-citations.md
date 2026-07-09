# ADR-004: Trust = schema-validated reports + deterministic citation verification

Status: accepted (2026-07-09)

## Problem

A small model's report is only useful if GRU can trust it without re-reading
the sources (which would erase the savings). Prompting alone cannot guarantee
this; the brief demands engineering.

## Alternatives considered

- **Prompt-only** ("cite your sources") — no enforcement; hallucinated paths
  and line numbers pass through silently.
- **LLM judge** — pays tokens to guess about trust; probabilistic on top of
  probabilistic.
- **Deterministic post-hoc verification** — citations carry verbatim excerpts;
  a verifier re-reads the cited lines and checks the excerpt actually appears.
  Cheap, exact, and it converts "trust me" into "checked: true/false".

## Decision

1. Reports are **Pydantic-validated JSON** submitted through a `submit_report`
   tool call (schema-constrained arguments), not free text.
2. Every finding carries `Evidence` items: repo-relative path, line range, and
   a **verbatim excerpt**.
3. After submission, the deterministic **verifier** re-reads each cited range
   (with a ±10-line tolerance window) and marks each evidence item
   `verified: true/false` using whitespace-normalized containment.
4. A finding with zero verified evidence is downgraded to `confidence: low`
   and flagged `[unverified]` in the rendered report. The report header shows
   the aggregate verification rate.
5. Every run writes a full JSONL trace (outside the repo) so any claim can be
   audited back to the tool outputs the minion actually saw.

## Drawbacks

- Verbatim excerpts cost minion output tokens (local, ~free) and report bytes
  (bounded by excerpt caps).
- Verification proves the excerpt *exists*, not that the *interpretation* is
  correct — interpretation risk stays with GRU, which is exactly the intended
  division of labor.
