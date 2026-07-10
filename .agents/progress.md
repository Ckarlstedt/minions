# Progress log

Newest first. One entry per meaningful step; keep entries short and factual.

## 2026-07-10 — Tool ergonomics from live-trace evidence (ADR-008)

- A live run against an external repo (trace `20260710T134018`) showed the
  tool layer inducing waste: fnmatch silently mis-reading ripgrep-style
  globs (`*.{ts,js}` → false "No matches"), 4/15 steps spent on identical
  repeated searches, two 300-path `list_files` floods, and a blind start.
- Fixes, all within ADR-005: gitignore-style glob matcher
  (`tools/globmatch.py` — braces, segment-scoped `*`, zero-dir `**/`,
  explicit errors on malformed patterns), depth-limited tree rendering with
  per-dir counts (`tools/tree.py`) used for the orientation listing and
  oversized `list_files` results, README/AGENTS/CLAUDE doc heads injected
  into the task message (capped 4k chars), and loop-level duplicate-call
  suppression. Details: decisions/ADR-008.
- 157 offline tests green; ruff + ty clean. Live smoke on this repo
  (gpt-oss): run 1 failed on trailing empty-response turns (known variance,
  see open-questions), run 2 complete with an accurate answer naming
  globmatch/validate_glob and the brace tests — citations 0% verified due to
  the known gpt-oss excerpt-quality issue (`\n…` in excerpts), not the new
  code.

## 2026-07-10 — Tool framing, `minions model`, init creates global config

- README rewritten tool-first: install → `minions init` in your project →
  investigate. Development framing moved entirely to DEVELOPMENT.md; the
  "never commit an API key" paragraph dropped per review.
- `minions model [NAME] [--local]` added: shows the effective model and its
  source, or sets `provider.model` in the global config (default) / repo
  `.env.toml` (--local). Edits are surgical (comments preserved, result
  re-parsed and verified before writing) via config_edit.py.
- `minions init` now also creates `~/.config/minions/config.toml` as a fully
  commented template when absent — no more "copy the example file" step. The
  template is embedded in the package; a drift-guard test keeps
  `.env.example.toml` identical to it. 127 tests green.

## 2026-07-10 — Global config layer

- Added `~/.config/minions/config.toml` (XDG-aware): machine-wide preferences
  for the installed CLI. Precedence: env > `./.env.toml` > user config >
  defaults, with file layers merging per key (a repo file setting only
  `budgets.max_steps` still inherits the globally-configured model).
- `minions doctor` prints both config paths (found/absent) and the api-key
  source now names the exact file. README gained a Configuration section
  with the full key/env-var/default table; tests isolate XDG so they never
  read a developer's real user config. 116 tests green.

## 2026-07-10 — Published

- Repo published: https://github.com/Ckarlstedt/minions (public, GPL-3.0).
  Local history rebased onto GitHub's initial LICENSE commit; pyproject
  license metadata corrected from the bootstrap-era MIT to GPL-3.0-only.
- `minions doctor` gained the tool-calling preflight probe
  (providers/probe.py): one tiny completion proves the server+model combo
  emits structured tool calls — FAILs fast on combos like Devstral that
  previously burned 18 minutes. Verified live (gpt-oss and GLM both pass).

## 2026-07-10 — GRU integration, model verdict, DX

- **`minions init`** added (ADR-007): appends a sentinel-marked instruction
  block to a target repo's AGENTS.md (idempotent, refresh-in-place, never
  touches surrounding content). The only write path into any repo, by design.
  README gained a "Use it from your other projects" section (uv tool install
  → doctor → init).
- **Model evaluation concluded** (findings/2026-07-10-model-comparison.md):
  gpt-oss-20b stays the minion. LFM2.5-8B-A1B tested live: ~10s/step but
  fabricates evidence after one tool call — rejected. Env stays pointed at
  gpt-oss.
- **Live progress output** added (`--progress`, auto-on for TTY): per-step
  tool calls, results, nudges with elapsed time. ProgressTrace decorates the
  JSONL trace writer.
- **Salvage extended**: unparsed tool-call envelopes (Qwen `<tool_call>`
  text, repeated blocks, string-encoded arguments) now recovered; report
  channel grants no extra trust.
- **ty** type checker added to the dev group and the standard gate;
  109 tests + ruff + ty all green.

## 2026-07-10 — Packaging, configuration, portability

- Switched to **uv** (`uv sync`, `uv.lock` committed, dev deps in a
  dependency group). ADR-001 amended.
- Added `.env` support (gitignored) + `.env.example`: process env >
  `.env` > defaults; new `MINIONS_OMLX_SETTINGS_PATH` for key discovery on
  non-default omlx locations. Dependency-free ~15-line parser in config.py.
- Scrubbed host-specific setup details from docs and `.agents/` — the
  project must read as portable open source, not one person's machine.
- Config file switched from `.env` to **`.env.toml`** (`.env.example.toml`
  committed): typed values, comments, stdlib `tomllib`; omlx key discovery
  now clearly scoped under `[provider.omlx]` since it is an omlx-only
  convenience. README/DEVELOPMENT now state provider support honestly:
  developed against omlx, other OpenAI-compatible servers unverified, PRs
  welcome. 96 tests green.
- `GLM-4.7-Flash-6bit` evaluation attempted (`MINIONS_MODEL=…`): blocked by
  the omlx prefill memory guard — with gpt-oss still resident, loading GLM
  predicts ~26.3 GB peak vs a ~26.1 GB cap. Not a code issue (the CLI
  surfaced a clean provider error, exit 1). Needs gpt-oss unloaded in the
  oMLX app or a looser memory-guard tier before the comparison can run.
  When it runs, compare against the gpt-oss baseline: complete, 75%
  verified, 17 steps, 107s, on the standard read-only-enforcement question.

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
