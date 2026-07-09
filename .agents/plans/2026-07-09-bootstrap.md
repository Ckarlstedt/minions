# Plan: Bootstrap GRU & Minions v1 (2026-07-09)

Status: **in progress**

## Problem restatement

Frontier agents (GRU) burn most of their tokens on *investigation* — reading
files, grepping, tracing git history — before any reasoning happens. A small
local model (minion) can do that investigation for near-zero cost if, and only
if, its output can be trusted. The deliverable is therefore not "an agent
wrapper around a small model"; it is a **trustworthy investigation service**
whose reports are cheap, compact, and verifiable.

## What v1 is

A Python library (`minions`) plus a thin CLI:

```
minions investigate "Where is retry logic implemented and is it covered by tests?" --repo .
minions doctor
```

- One **investigation** = one semantic question + optional scope.
- Executed by one minion running a tool-calling loop against an
  OpenAI-compatible endpoint (initially omlx / gpt-oss-20b).
- Tools are read-only *by construction* (in-process implementations, no shell).
- Output: structured report (findings + verbatim citations + confidence),
  passed through a **deterministic citation verifier** before delivery.
- Default rendering: compact markdown for GRU; `--json` for full structure.
- Full JSONL trace of every run stored outside the repo for auditability.

## What v1 is not (deliberate deferrals)

- No MCP server, no HTTP daemon (thin adapters can wrap the service later — see ADR-002).
- No planner / DAG / multi-minion workflows (see ADR-003).
- No semantic index / embeddings / LSP integration — evaluate after measuring
  where v1 investigations fail (recorded in open-questions.md).
- No streaming to the caller; the report is the deliverable.

## Build order

1. `.agents/` memory: this plan, ADR-001..006, environment findings. ✅ when committed
2. Skeleton: pyproject (src layout), venv on Python 3.14.6, ruff + pytest.
3. Bottom-up modules: config → report schema → tools → provider → verifier → agent loop → CLI.
4. Tests alongside each module; loop tested with a scripted FakeProvider.
5. Docs: README, AGENTS, ARCHITECTURE, DEVELOPMENT.
6. Live end-to-end run against omlx on this very repo; record token stats.

## Success measures for v1

- A live investigation returns a verified-citation report using fewer than
  ~2k tokens of GRU context (report size), regardless of how many tokens the
  minion spent locally (local tokens are ~free).
- Citation verifier catches fabricated citations in tests.
- `pytest` and `ruff` clean; no write-capable code path exists in the tool layer.

## Constraints discovered during recon (see findings/2026-07-09-environment.md)

- omlx server caps context at **32k tokens** → minion needs output caps per tool
  call and a context budget.
- omlx supports native OpenAI tool calling with gpt-oss-20b (verified live).
- External binaries (ripgrep etc.) can't be assumed on target hosts → search
  uses `git grep` with a pure-Python fallback.
- Packaging: bootstrapped with venv+pip; moved to uv on 2026-07-10 (ADR-001).
