# ADR-001: Python 3.12+ + uv + minimal dependencies

Status: accepted (2026-07-09), amended (2026-07-10: uv replaces venv+pip)

## Problem

Pick the implementation language and build tooling for the minions service.

## Alternatives considered

- **TypeScript/Node** — the MCP ecosystem is JS-first, but we are
  deliberately not MCP-first (ADR-002), and the local ML/tokenizer ecosystem
  (mlx, tiktoken-style counting) is Python-native.
- **Go/Rust** — great CLIs, but slower iteration for an architecture that must
  stay easy to evolve, and no advantage for an I/O-bound orchestrator.
- **Python** — the MLX/local-model ecosystem is Python-native, and Pydantic
  gives us schema-validated structured outputs (a trust requirement, ADR-004).

## Decision

Python ≥ 3.12, src layout, **uv** for environment + lockfile (`uv sync`,
`uv run …`; dev tools in a `[dependency-groups]` dev group). Runtime deps
kept to two: `pydantic` (report schema/validation) and `httpx` (HTTP client
with sane timeouts). CLI on stdlib `argparse`. Dev deps: `pytest`, `ruff`.

History: v1 bootstrapped with plain venv+pip because uv wasn't present in the
initial environment; switched to uv (with committed `uv.lock`) as soon as it
was, for reproducible installs.

## Drawbacks

- Python startup (~100ms) per CLI invocation; negligible vs. inference time.
- uv is an external tool contributors must install (single binary, standard
  in 2026 Python practice).
