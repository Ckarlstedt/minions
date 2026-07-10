# GRU & Minions

Frontier coding agents (**GRU** — Claude Code, Codex, Cursor, …) burn most of
their expensive tokens on *investigation* — grepping, reading files, tracing
git history — before any actual reasoning happens. **minions** is a CLI tool
you add to your projects: it delegates that investigation to a cheap local
model, which explores the repository with read-only tools and returns a
compact report whose citations are **machine-verified** against the real
files.

Your agent keeps doing what it is good at: reasoning, architecture, editing.
Minions do the legwork.

```
┌─────────┐  question (one CLI call)   ┌────────┐  read-only tools  ┌──────┐
│   GRU   │ ─────────────────────────▶ │ minion │ ────────────────▶ │ repo │
│(frontier│ ◀───────────────────────── │ (local │ ◀──────────────── │      │
│  agent) │  verified compact report   │ model) │                   └──────┘
└─────────┘                            └────────┘
```

## Install

Requires [uv](https://docs.astral.sh/uv/) and a local OpenAI-compatible model
server (developed and tested against [omlx](https://omlx.app); vLLM, Ollama,
LM Studio and friends should work but are unverified — PRs welcome):

```bash
uv tool install git+https://github.com/Ckarlstedt/minions

minions doctor    # verifies server, model, API key, and that tool calling works
```

## Add it to a project

```bash
cd ~/code/your-project
minions init      # AGENTS.md by default; --file CLAUDE.md if that's your convention
```

`minions init` does two things:

- **Appends** a short, clearly-marked instruction block to the repo's
  `AGENTS.md` (creating the file if needed) telling coding agents when to
  delegate investigation, how to call the CLI, and how to read verified
  citations. It never touches anything outside its
  `<!-- minions:begin/end -->` markers — re-running refreshes the block in
  place and your own content is preserved. This block is the only thing
  minions ever writes inside a repository; investigations themselves are
  read-only by construction.
- **Creates the global config** (`~/.config/minions/config.toml`) as a fully
  commented template if it doesn't exist yet.

From then on, any agent working in that repo reads the instructions and runs
`minions investigate "…"` instead of burning its context on grep-and-read
loops. You can also use it directly:

```bash
minions investigate "Where is retry logic implemented, and is it tested?"
```

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

- **Read-only by construction**: the minion's tool registry contains no
  write-capable operation and no shell. Path containment is enforced on every
  access.
- **Verified citations**: every claim cites file, line range, and a verbatim
  excerpt; excerpts are checked against the actual files after the run.
- **Full audit trail**: each run writes a JSONL trace of every model response
  and tool result to `~/.local/state/minions/runs/`.
- **Honest gaps**: the report schema has an `unanswered` section; the minion
  is instructed (and budgeted) to admit what it couldn't confirm.

## Configuration

Zero configuration is the intended default: a standard local omlx setup
(server on `127.0.0.1:8000`, gpt-oss-20b, API key auto-discovered from omlx's
own settings) works out of the box. When you want different settings, three
layers apply — highest precedence first:

1. **`MINIONS_*` environment variables** — one-off overrides:
   `MINIONS_MODEL=other-model minions investigate "…"`
2. **`.env.toml` in the working directory** — per-repo overrides (gitignore it)
3. **`~/.config/minions/config.toml`** — machine-wide preferences, created by
   `minions init` as a commented template (respects `XDG_CONFIG_HOME`)

Both files use the same schema, and layers merge per key: a repo `.env.toml`
that only changes `budgets.max_steps` still inherits the model from your
global config. `minions doctor` shows which files were found and which source
each value came from.

Switching models is common enough to have its own command:

```bash
minions model                       # show the effective model and where it came from
minions model GLM-4.7-Flash-6bit    # set it in the global config
minions model gpt-oss-20b --local   # set it in this repo's .env.toml only
```

All keys, with their env-var equivalents:

| Key | Env var | Default | Meaning |
| --- | --- | --- | --- |
| `provider.base_url` | `MINIONS_BASE_URL` | `http://127.0.0.1:8000/v1` | OpenAI-compatible endpoint |
| `provider.model` | `MINIONS_MODEL` | `gpt-oss-20b-MXFP4-Q8` | model id as the server advertises it |
| `provider.api_key` | `MINIONS_API_KEY` | auto-discovered | server API key, if required |
| `provider.request_timeout` | `MINIONS_REQUEST_TIMEOUT` | `180.0` | seconds per model call |
| `provider.omlx.settings_path` | `MINIONS_OMLX_SETTINGS_PATH` | `~/.omlx/settings.json` | omlx-only: where to auto-discover the key |
| `budgets.max_steps` | `MINIONS_MAX_STEPS` | `16` | tool calls per investigation |
| `budgets.context_token_limit` | `MINIONS_CONTEXT_TOKEN_LIMIT` | `24000` | force-finish before the server's context cap |
| `budgets.max_tool_output_chars` | `MINIONS_MAX_TOOL_OUTPUT_CHARS` | `8000` | per-tool-result truncation |
| `budgets.max_completion_tokens` | `MINIONS_MAX_COMPLETION_TOKENS` | `4096` | per-call cap (includes reasoning tokens) |
| `sampling.temperature` | `MINIONS_TEMPERATURE` | `0.2` | sampling temperature |
| `trace.state_dir` | `MINIONS_STATE_DIR` | `~/.local/state/minions` | run traces (never inside the investigated repo) |

## Documentation

- [AGENTS.md](AGENTS.md) — how a frontier agent should delegate to minions
- [ARCHITECTURE.md](ARCHITECTURE.md) — design, components, decision summaries
- [DEVELOPMENT.md](DEVELOPMENT.md) — hacking on minions itself (setup, tests, lint)
- [.agents/](.agents/) — engineering memory: plans, ADRs, findings, open questions
