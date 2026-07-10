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

## Releasing

Installs come straight from git, in three flavors:

```bash
uv tool install git+https://github.com/Ckarlstedt/minions            # HEAD of main
uv tool install git+https://github.com/Ckarlstedt/minions@latest     # moving 'latest' tag
uv tool install git+https://github.com/Ckarlstedt/minions@v0.1.0     # pinned release
```

To cut a release:

```bash
# 1. bump the package version FIRST — the tag alone does nothing:
#    `uv tool list` and `minions --version` report pyproject.toml's version,
#    not the git tag they were installed from.
uv version --bump patch      # edits pyproject.toml (use minor/major as appropriate)
uv lock
git commit -am "bump version to X.Y.Z" && git push

# 2. tag that commit and move the 'latest' alias.
#    `git tag -f latest` is required: force-PUSH alone moves nothing —
#    if the local tag still points at the old commit, git says "up to date".
git tag vX.Y.Z
git tag -f latest
git push origin vX.Y.Z
git push -f origin latest
```

`latest` is a deliberately *moving* tag (like GitHub Actions' `@v1`
convention) — hence the force-push. Users on `@latest` pick up the new
version with `uv tool upgrade minions`.

## Debugging an investigation

Every run writes a JSONL trace (path printed on stderr, kept under
`$MINIONS_STATE_DIR/runs/`). It contains each model response, every tool
call and its full untruncated-at-source output, forced-finish events, and the
final report — read it bottom-up to see why a report says what it says.
