# Environment recon: local omlx server (2026-07-09)

Verified live against a running omlx server, not assumed. These findings
shaped several defaults; on other setups, re-check with `minions doctor`.

## omlx server behavior

- Serves an OpenAI-compatible API (default `http://127.0.0.1:8000/v1`).
- Requires an API key (`auth.api_key` in its settings file, default
  `~/.omlx/settings.json`). Requests without it get `401
  authentication_error`. Keys must never be committed; config auto-discovers
  the key from that file, `MINIONS_API_KEY` overrides, and
  `MINIONS_OMLX_SETTINGS_PATH` relocates the discovery path.
- Advertises models *without* the HuggingFace org prefix (e.g.
  `gpt-oss-20b-MXFP4-Q8`, not `mlx-community/gpt-oss-20b-MXFP4-Q8`), though
  completions accept both forms.
- **Native OpenAI tool calling works** with gpt-oss-20b: a request with
  `tools=[...]` returns a well-formed `tool_calls` array with
  `finish_reason: "tool_calls"`. No text-based ReAct fallback needed in v1.
  (Caveats found later: see 2026-07-09-gpt-oss-tool-calling.md.)
- Responses include `usage` (prompt/completion tokens, cached_tokens,
  total_time) and a `reasoning_content` field (model thinking) — usable for
  token accounting; reasoning_content must NOT be fed back into history
  (it would burn the context budget).
- Server-side defaults observed: temperature 0.3, top_p 0.95,
  **max_context_window 32768** — hence the loop's force-finish context guard
  (`MINIONS_CONTEXT_TOKEN_LIMIT`, default 24k).
- Scheduler allows 3 concurrent requests → up to 3 parallel investigations.

## Portability decisions driven by recon

- The search tool is built on `git grep` with a pure-Python fallback rather
  than ripgrep: git is effectively always present in the target use case
  (investigating repositories), while external binary dependencies (rg, fd)
  cannot be assumed on arbitrary hosts.
- Traces are written to an XDG-style state dir (`~/.local/state/minions`,
  overridable) because the investigated repository itself must never be
  written to.
