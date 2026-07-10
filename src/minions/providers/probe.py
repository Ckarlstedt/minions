"""Preflight probe: can this server+model combination actually call tools?

"OpenAI-compatible" does not guarantee functional tool calling per model —
the server's chat-template parser for each model family matters as much as
the model itself (observed live: Devstral emitted raw template artifacts,
Qwen emitted unparsed <tool_call> text). This probe costs one tiny completion
and turns an 18-minute failed investigation into a two-second doctor verdict.
"""

from __future__ import annotations

from minions.providers.base import ChatProvider, Message, ToolSpec

PROBE_TOOL = ToolSpec(
    name="ping",
    description="Reply to the user by calling this tool.",
    parameters={"type": "object", "properties": {}},
)

PROBE_MESSAGE = Message(role="user", content="Call the ping tool now.")


def probe_tool_calling(provider: ChatProvider) -> tuple[bool, str]:
    """One tiny completion offering a dummy tool. Raises ProviderError on
    transport failure; returns (ok, human-readable detail) otherwise."""
    result = provider.complete([PROBE_MESSAGE], [PROBE_TOOL])
    if result.message.tool_calls:
        return True, "model emitted a structured tool call"
    reply = " ".join((result.message.content or "").split())[:80]
    return False, (
        "model replied with text instead of a structured tool call — "
        f"minions cannot work with this server+model combination (got: {reply!r})"
    )
