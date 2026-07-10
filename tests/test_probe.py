from __future__ import annotations

from minions.providers.base import ChatResult, Message, ToolCall, Usage
from minions.providers.fake import FakeProvider
from minions.providers.probe import probe_tool_calling


def test_probe_passes_on_structured_tool_call() -> None:
    provider = FakeProvider(
        [
            ChatResult(
                message=Message(
                    role="assistant",
                    tool_calls=(ToolCall(id="c1", name="ping", arguments="{}"),),
                ),
                usage=Usage(10, 5),
            )
        ]
    )
    ok, detail = probe_tool_calling(provider)
    assert ok
    assert "structured tool call" in detail
    # The probe offered exactly one dummy tool.
    _, tools = provider.requests[0]
    assert [t.name for t in tools] == ["ping"]


def test_probe_fails_on_text_reply() -> None:
    provider = FakeProvider(
        [ChatResult(message=Message(role="assistant", content="pong! how can I help?"))]
    )
    ok, detail = probe_tool_calling(provider)
    assert not ok
    assert "cannot work" in detail and "pong!" in detail
