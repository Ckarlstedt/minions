# Development

## Setup

Requires Python ≥ 3.12 (this machine: pyenv 3.14.6 — note the system default
`python3` is 3.9 and will not work):

```bash
~/.pyenv/versions/3.14.6/bin/python -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

## Everyday commands

```bash
.venv/bin/python -m pytest          # test suite (offline; no server needed)
.venv/bin/ruff check src tests      # lint
.venv/bin/ruff format src tests     # format
.venv/bin/minions doctor            # verify server/key/environment
.venv/bin/minions investigate "…"   # run a real investigation
```

## Configuration

Everything is env-var based (defaults target the local omlx server):

| Variable | Default | Meaning |
| --- | --- | --- |
| `MINIONS_BASE_URL` | `http://127.0.0.1:8000/v1` | OpenAI-compatible endpoint |
| `MINIONS_MODEL` | `gpt-oss-20b-MXFP4-Q8` | model id as the server advertises it |
| `MINIONS_API_KEY` | auto-discovered | falls back to `~/.omlx/settings.json` `auth.api_key` |
| `MINIONS_MAX_STEPS` | `16` | tool-call budget per investigation |
| `MINIONS_CONTEXT_TOKEN_LIMIT` | `24000` | force-finish before the server's 32k context cap |
| `MINIONS_MAX_TOOL_OUTPUT_CHARS` | `8000` | per-tool-result truncation |
| `MINIONS_MAX_COMPLETION_TOKENS` | `4096` | per-call completion cap (includes gpt-oss thinking) |
| `MINIONS_TEMPERATURE` | `0.2` | sampling temperature |
| `MINIONS_REQUEST_TIMEOUT` | `180` | seconds per model call |
| `MINIONS_STATE_DIR` | `~/.local/state/minions` | run traces live here, never in the repo |

**Never commit the API key.** It is read at runtime from the environment or
omlx's own settings file and is never logged.

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
