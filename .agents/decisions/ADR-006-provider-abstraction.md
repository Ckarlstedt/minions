# ADR-006: ChatProvider protocol; OpenAI-compatible adapter first

Status: accepted (2026-07-09)

## Problem

Providers and models must be interchangeable (omlx today; vLLM, Ollama,
OpenAI, Anthropic tomorrow) without the core knowing which is in use.

## Decision

- Core defines a `ChatProvider` protocol: `complete(request) -> ChatResult`
  where the request carries messages + tool schemas + sampling params, and the
  result carries content, tool calls, and usage stats in provider-neutral
  dataclasses.
- First adapter: `OpenAICompatProvider` (httpx, `/v1/chat/completions`).
  This one adapter already covers omlx, vLLM, Ollama, LM Studio, llama.cpp
  and OpenAI itself — which is why it's first, not because omlx is special.
- Config selects provider/model/base-url/key via file + env
  (`MINIONS_BASE_URL`, `MINIONS_MODEL`, `MINIONS_API_KEY`), with a
  convenience fallback that discovers the omlx key from
  `~/.omlx/settings.json` (never committed, never logged).
- Tests use a `FakeProvider` (scripted responses) — the agent loop is fully
  testable offline.

## Drawbacks

- The protocol is shaped by the chat-completions model (messages, tool_calls).
  An Anthropic-native adapter needs a small message-shape translation — the
  neutral dataclasses exist precisely so that translation lives inside the
  adapter.
- Assumes native tool calling (verified for omlx/gpt-oss-20b). A provider
  without it would need a text-protocol emulation layer inside its adapter;
  deferred until such a provider matters.
