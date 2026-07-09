"""OpenAI-compatible chat-completions adapter.

One adapter covers omlx, vLLM, Ollama, LM Studio, llama.cpp and OpenAI —
anything speaking POST {base_url}/chat/completions.

Notes specific to reasoning models (gpt-oss on omlx): responses may carry a
`reasoning_content` field; it is intentionally dropped — feeding thinking back
into history would burn the 32k context budget for nothing.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence

import httpx

from minions.config import Settings
from minions.providers.base import (
    ChatResult,
    Message,
    ProviderError,
    ToolCall,
    ToolSpec,
    Usage,
)

logger = logging.getLogger(__name__)


class OpenAICompatProvider:
    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self._settings = settings
        headers = {"Content-Type": "application/json"}
        if settings.api_key:
            headers["Authorization"] = f"Bearer {settings.api_key}"
        self._client = client or httpx.Client(
            base_url=settings.base_url,
            headers=headers,
            timeout=httpx.Timeout(settings.request_timeout, connect=10.0),
        )

    def complete(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec] = (),
    ) -> ChatResult:
        payload: dict = {
            "model": self._settings.model,
            "messages": [_message_to_wire(m) for m in messages],
            "temperature": self._settings.temperature,
            "max_tokens": self._settings.max_completion_tokens,
        }
        if tools:
            payload["tools"] = [_tool_to_wire(t) for t in tools]

        try:
            response = self._client.post("/chat/completions", json=payload)
        except httpx.HTTPError as exc:
            raise ProviderError(
                f"Cannot reach model server at {self._settings.base_url}: {exc}"
            ) from exc

        if response.status_code != 200:
            raise ProviderError(
                f"Model server returned HTTP {response.status_code}: {response.text[:500]}"
            )

        try:
            data = response.json()
            return _parse_response(data)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderError(f"Malformed response from model server: {exc}") from exc

    def list_models(self) -> list[str]:
        """Used by `minions doctor`; raises ProviderError on failure."""
        try:
            response = self._client.get("/models")
        except httpx.HTTPError as exc:
            raise ProviderError(
                f"Cannot reach model server at {self._settings.base_url}: {exc}"
            ) from exc
        if response.status_code != 200:
            raise ProviderError(
                f"Model server returned HTTP {response.status_code}: {response.text[:500]}"
            )
        data = response.json()
        return [m.get("id", "?") for m in data.get("data", [])]

    def close(self) -> None:
        self._client.close()


def _message_to_wire(message: Message) -> dict:
    # Reasoning models sometimes produce empty assistant turns; send "" rather
    # than null so chat templates that expect a string don't misrender history.
    content = message.content
    if content is None and not message.tool_calls:
        content = ""
    wire: dict = {"role": message.role, "content": content}
    if message.tool_calls:
        wire["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.name, "arguments": call.arguments},
            }
            for call in message.tool_calls
        ]
    if message.tool_call_id is not None:
        wire["tool_call_id"] = message.tool_call_id
    return wire


def _tool_to_wire(tool: ToolSpec) -> dict:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        },
    }


def _parse_response(data: dict) -> ChatResult:
    choice = data["choices"][0]
    raw_message = choice["message"]

    tool_calls = tuple(
        ToolCall(
            id=raw_call.get("id") or f"call_{i}",
            name=raw_call["function"]["name"],
            arguments=_ensure_str(raw_call["function"].get("arguments", "{}")),
        )
        for i, raw_call in enumerate(raw_message.get("tool_calls") or [])
    )

    raw_usage = data.get("usage") or {}
    usage = Usage(
        prompt_tokens=int(raw_usage.get("prompt_tokens") or 0),
        completion_tokens=int(raw_usage.get("completion_tokens") or 0),
    )

    return ChatResult(
        message=Message(
            role=raw_message.get("role", "assistant"),
            content=raw_message.get("content"),
            tool_calls=tool_calls,
        ),
        usage=usage,
        finish_reason=choice.get("finish_reason"),
        reasoning=raw_message.get("reasoning_content"),
    )


def _ensure_str(arguments: object) -> str:
    # Some servers return arguments as an already-parsed object.
    if isinstance(arguments, str):
        return arguments
    return json.dumps(arguments)
