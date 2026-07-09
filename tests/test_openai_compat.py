from __future__ import annotations

import json

import httpx
import pytest

from minions.config import Settings
from minions.providers.base import Message, ProviderError, ToolCall, ToolSpec
from minions.providers.openai_compat import OpenAICompatProvider

SETTINGS = Settings(base_url="http://test/v1", model="test-model", api_key="sk-test")


def provider_with(handler) -> OpenAICompatProvider:
    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test/v1")
    return OpenAICompatProvider(SETTINGS, client=client)


def ok_response(message: dict, usage: dict | None = None) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [{"message": message, "finish_reason": "stop"}],
            "usage": usage or {"prompt_tokens": 10, "completion_tokens": 5},
        },
    )


def test_payload_and_parsing() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        captured["path"] = request.url.path
        return ok_response({"role": "assistant", "content": "hello"})

    result = provider_with(handler).complete(
        [
            Message(role="system", content="sys"),
            Message(
                role="assistant",
                tool_calls=(ToolCall(id="c1", name="search", arguments='{"pattern":"x"}'),),
            ),
            Message(role="tool", content="out", tool_call_id="c1"),
        ],
        tools=[ToolSpec(name="search", description="d", parameters={"type": "object"})],
    )

    assert captured["path"] == "/v1/chat/completions"
    assert captured["model"] == "test-model"
    assert captured["messages"][0] == {"role": "system", "content": "sys"}
    assert captured["messages"][1]["tool_calls"][0]["function"]["name"] == "search"
    assert captured["messages"][2]["tool_call_id"] == "c1"
    assert captured["tools"][0]["function"]["name"] == "search"
    assert result.message.content == "hello"
    assert result.usage.prompt_tokens == 10
    assert result.finish_reason == "stop"


def test_tool_calls_parsed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return ok_response(
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "grep", "arguments": '{"pattern": "x"}'},
                    },
                    {
                        "type": "function",
                        "function": {"name": "read", "arguments": {"path": "a.py"}},
                    },
                ],
            }
        )

    result = provider_with(handler).complete([Message(role="user", content="q")])
    first, second = result.message.tool_calls
    assert first == ToolCall(id="call_1", name="grep", arguments='{"pattern": "x"}')
    assert second.id  # generated when the server omits one
    assert json.loads(second.arguments) == {"path": "a.py"}


def test_http_error_raises_provider_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "Invalid API key"}})

    with pytest.raises(ProviderError, match="401"):
        provider_with(handler).complete([Message(role="user", content="q")])


def test_network_error_raises_provider_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    with pytest.raises(ProviderError, match="Cannot reach model server"):
        provider_with(handler).complete([Message(role="user", content="q")])


def test_malformed_response_raises_provider_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": True})

    with pytest.raises(ProviderError, match="Malformed response"):
        provider_with(handler).complete([Message(role="user", content="q")])


def test_list_models() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/models"
        return httpx.Response(200, json={"data": [{"id": "m1"}, {"id": "m2"}]})

    assert provider_with(handler).list_models() == ["m1", "m2"]
