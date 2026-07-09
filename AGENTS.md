# AGENTS.md

Guidance for AI agents in two roles: **using** minions to investigate (GRU),
and **developing** this repository.

## Using minions as GRU

You are the expensive reasoner. Delegate investigation instead of reading the
repository yourself:

```bash
minions investigate "<one specific question>" --repo <path>       # markdown report
minions investigate "<question>" --repo <path> --json             # full structured report
minions doctor                                                    # if something seems broken
```

Exit codes: `0` report delivered (complete or partial), `2` investigation
failed (read stderr, consider rephrasing or investigating yourself), `1`
config/server problem (run `doctor`).

**Ask well.** One semantic question per invocation, with success criteria in
the question itself. Good: *"Where is pagination implemented in the API
layer, and which tests cover it?"* Bad: *"Audit this repo"* (too broad),
*"Run grep for me"* (no synthesis — just do that yourself).

**Reading reports:**

- `✓` citations were mechanically verified against the real files — you can
  cite them onward without re-reading the source.
- `✗ UNVERIFIED` means the excerpt did not match the file; treat that claim
  as a hint, not a fact, and check it yourself before acting on it.
- The `Not answered` section is trustworthy by design — the minion is
  rewarded for admitting gaps. Investigate those parts yourself or ask a
  narrower follow-up.
- Findings are leads with receipts, not decisions. Reasoning about what they
  mean is your job.

**Parallelism:** the local server handles up to 3 concurrent investigations;
launch independent questions as separate background invocations.

## Developing this repository

- Read `.agents/` first — it is the persistent engineering memory (plans,
  ADRs, findings, open questions, progress log). Update it as you work:
  decisions get an ADR, discoveries go to `findings/`, progress to
  `progress.md`.
- Verify before claiming: `uv run pytest` and `uv run ruff check src tests`
  must pass; `uv run minions doctor` plus one live `investigate` run for
  changes touching the loop, provider, or prompts.
- Invariants that must survive any change:
  - the tool layer stays read-only and shell-free (ADR-005);
  - reports stay schema-validated with verifiable citations (ADR-004);
  - the core stays transport- and provider-agnostic (ADR-002/006);
  - secrets (API keys) never enter the repo, logs, or traces.
- The project uses uv: `uv sync` to set up, `uv run <cmd>` to execute —
  don't call a bare system `python3`.
