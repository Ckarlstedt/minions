# GRU & Minions

Frontier reasoning agents (**GRU**) burn most of their expensive tokens on
*investigation* — grepping, reading files, tracing git history — before any
actual reasoning happens. **Minions** moves that investigation to a cheap
local model, which explores the repository with read-only tools and returns a
compact report whose citations are **machine-verified** against the real
files.

GRU keeps doing what it is good at: reasoning, architecture, editing.
Minions do the legwork.

```
┌─────────┐  question (one CLI call)   ┌────────┐  read-only tools  ┌──────┐
│   GRU   │ ─────────────────────────▶ │ minion │ ────────────────▶ │ repo │
│(frontier│ ◀───────────────────────── │ (local │ ◀──────────────── │      │
│  agent) │  verified compact report   │ model) │                   └──────┘
└─────────┘                            └────────┘
```

## Quickstart

```bash
uv sync                            # set up the environment
cp .env.example.toml .env.toml     # optional: configure server/model/budgets

# check server, key, and environment
uv run minions doctor

# ask a question about any repository
uv run minions investigate "Where is retry logic implemented, and is it tested?" --repo ~/code/myproject
```

By default minions talks to a local OpenAI-compatible server at
`http://127.0.0.1:8000/v1`. It is currently developed and tested against
[omlx](https://omlx.app) (whose API key it can auto-discover); other
OpenAI-compatible servers (vLLM, Ollama, LM Studio, …) should work but are
unverified — PRs welcome. Configure via `.env.toml`
(see [DEVELOPMENT.md](DEVELOPMENT.md)).

## What a report looks like

```markdown
**Question:** Where is retry logic implemented, and is it tested?
**Status:** complete — 100% of citations verified — 7 steps, 21403 local tokens, 48.2s, gpt-oss-20b-MXFP4-Q8

**Answer:** Retry logic lives in src/http/retry.py as an exponential-backoff
decorator; it is covered by tests/test_retry.py.

**Findings:**
1. `with_retry` implements capped exponential backoff _(high)_
   - `src/http/retry.py:14-31` ✓
     > def with_retry(max_attempts=3, base_delay=0.5): ...
```

The `✓` is not decoration: a deterministic verifier re-read those lines and
confirmed the excerpt is real. Fabricated citations are flagged `✗ UNVERIFIED`
and downgrade the finding's confidence.

## Why trust a small model?

You don't — you trust the engineering around it:

- **Read-only by construction**: the tool registry contains no write-capable
  operation and no shell. Path containment is enforced on every access.
- **Verified citations**: every claim cites file, line range, and a verbatim
  excerpt; excerpts are checked against the actual files after the run.
- **Full audit trail**: each run writes a JSONL trace of every model response
  and tool result to `~/.local/state/minions/runs/`.
- **Honest gaps**: the report schema has an `unanswered` section; the minion
  is instructed (and budgeted) to admit what it couldn't confirm.

## Documentation

- [AGENTS.md](AGENTS.md) — how a frontier agent should delegate to minions
- [ARCHITECTURE.md](ARCHITECTURE.md) — design, components, decision summaries
- [DEVELOPMENT.md](DEVELOPMENT.md) — setup, configuration, testing
- [.agents/](.agents/) — engineering memory: plans, ADRs, findings, open questions
