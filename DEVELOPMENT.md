# Development

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Python ≥ 3.12 (uv will fetch
one if needed):

```bash
uv sync                            # creates .venv, installs deps + dev group
cp .env.example.toml .env.toml     # optional: local configuration
```

## Everyday commands

```bash
uv run pytest                  # test suite (offline; no server needed)
uv run ruff check src tests    # lint
uv run ruff format src tests   # format
uv run ty check                # type check
uv run minions doctor          # verify server/key/environment
uv run minions investigate "…" # run a real investigation
```

## Configuration

Copy `.env.example.toml` to `.env.toml` (per-repo, gitignored) or to
`~/.config/minions/config.toml` (machine-wide) — every key is documented
there, alongside its `MINIONS_*` environment-variable override. Precedence:
**process env > `./.env.toml` > `~/.config/minions/config.toml` > defaults**,
with file layers merging per key. The full key table lives in the README's
Configuration section.

```toml
[provider]
base_url = "http://127.0.0.1:8000/v1"   # any OpenAI-compatible endpoint
model = "gpt-oss-20b-MXFP4-Q8"          # id exactly as the server advertises it
#api_key = ""                           # if the server requires one

[provider.omlx]
# omlx-only: fallback API-key discovery from omlx's own settings file
#settings_path = "~/.omlx/settings.json"

[budgets]
#max_steps = 16
```

**Provider support:** the code speaks the generic OpenAI chat-completions
protocol, but is currently developed and tested against **omlx** only. Other
servers (vLLM, Ollama, LM Studio, llama.cpp) should work and PRs improving
support for them are very welcome — see the `ChatProvider` protocol in
`src/minions/providers/base.py` for the extension point. The
`[provider.omlx]` block exists because omlx stores its API key in a settings
file we can discover; other providers have no equivalent.

**Never commit the API key.** It is read at runtime from the environment,
`.env.toml`, or omlx's own settings file, and is never logged.

## Repo conventions

- `src/` layout; keep runtime dependencies minimal (currently `pydantic`,
  `httpx` — adding one is an architectural decision, record it).
- Every significant decision gets an ADR in `.agents/decisions/`; progress
  and findings go to `.agents/progress.md` / `.agents/findings/`.
- The tool layer must stay read-only and shell-free (ADR-005). A new tool
  needs containment-checked paths and tests proving its guards.
- Tests are offline by default; anything needing the live server gets
  `@pytest.mark.live`.

## Debugging an investigation

Every run writes a JSONL trace (path printed on stderr, kept under
`$MINIONS_STATE_DIR/runs/`). It contains each model response, every tool
call and its full untruncated-at-source output, forced-finish events, and the
final report — read it bottom-up to see why a report says what it says.
