"""Scripted provider for offline tests of the agent loop."""

from __future__ import annotations

from collections.abc import Sequence

from minions.providers.base import ChatResult, Message, ProviderError, ToolSpec


class FakeProvider:
    """Returns pre-scripted results in order; records every request it receives."""

    def __init__(self, script: Sequence[ChatResult]) -> None:
        self._script = list(script)
        self.requests: list[tuple[tuple[Message, ...], tuple[ToolSpec, ...]]] = []

    def complete(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec] = (),
    ) -> ChatResult:
        self.requests.append((tuple(messages), tuple(tools)))
        if not self._script:
            raise ProviderError("FakeProvider script exhausted")
        return self._script.pop(0)
