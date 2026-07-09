# Progress log

Newest first. One entry per meaningful step; keep entries short and factual.

## 2026-07-10 — Packaging, configuration, portability

- Switched to **uv** (`uv sync`, `uv.lock` committed, dev deps in a
  dependency group). ADR-001 amended.
- Added `.env` support (gitignored) + `.env.example`: process env >
  `.env` > defaults; new `MINIONS_OMLX_SETTINGS_PATH` for key discovery on
  non-default omlx locations. Dependency-free ~15-line parser in config.py.
- Scrubbed host-specific setup details from docs and `.agents/` — the
  project must read as portable open source, not one person's machine.
- New candidate model available on the local server: `GLM-4.7-Flash-6bit`
  (and an 8bit variant) — evaluation pending/below.

## 2026-07-09 — Bootstrap session (continued)

- v1 implemented end to end: config, report schema, read-only tool layer
  (list_files/read_file/search + git log/diff/blame), OpenAI-compat provider,
  citation verifier, agent loop, CLI (`investigate`, `doctor`). 86 offline
  tests passing, ruff clean.
- `minions doctor` against the live server surfaced that omlx advertises the
  model as `gpt-oss-20b-MXFP4-Q8` (no org prefix) → default updated.
- First live run FAILED usefully: gpt-oss ignored the nested submit_report
  schema and sometimes emitted reasoning-only empty turns. Root-caused via
  the run trace + API probes; fixed with a flat submission schema, prompt
  shape example, empty-turn nudges, and reasoning capture in traces.
  Details: findings/2026-07-09-gpt-oss-tool-calling.md.
- Live run iterations (same question, this repo): run 1 failed (nested
  schema), run 2 complete but 0% verified (line-number prefixes), run 3
  failed (report as plain text), run 4 **complete, 75% verified, exit 0** —
  accurate answer naming Workspace.resolve, fs/git tool guards, registry
  containment. Each failure produced an engineering fix, not a prompt tweak:
  flat schema, prefix stripping, text salvage. 90 offline tests green.
- Token economics of run 4: minion consumed ~76k local (free) tokens in 17
  steps / 107s; the report GRU actually pays to read is ~450 tokens. The
  equivalent direct investigation (reads of 4 modules + several searches)
  would have put roughly 10-15k tokens into frontier context.

## 2026-07-09 — Bootstrap session

- Recon done: omlx live at :8000 (API key required, 32k context cap,
  native tool calling verified with gpt-oss-20b). Details in
  findings/2026-07-09-environment.md.
- Plan written: plans/2026-07-09-bootstrap.md.
- Decisions recorded: ADR-001 (Python), ADR-002 (CLI-first), ADR-003
  (investigation as unit), ADR-004 (verified citations), ADR-005 (read-only
  by construction), ADR-006 (provider abstraction).
- Next: project skeleton → core modules → tests → docs → live e2e run.
