"""Provider-neutral chat types and the ChatProvider protocol (ADR-006).

These types are deliberately minimal and shaped by what the agent loop needs,
not by any vendor SDK. Adapters translate to/from wire formats.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol


class ProviderError(Exception):
    """A provider could not produce a completion (network, auth, bad response)."""


@dataclass(frozen=True)
class ToolSpec:
    """A tool offered to the model. `parameters` is a JSON Schema object."""

    name: str
    description: str
    parameters: dict


@dataclass(frozen=True)
class ToolCall:
    """A tool invocation requested by the model.

    `arguments` is the raw JSON string as produced by the model — parsing (and
    handling of malformed JSON) is the loop's responsibility, so that a parse
    failure can be reported back to the model instead of crashing the run.
    """

    id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class Message:
    role: str  # "system" | "user" | "assistant" | "tool"
    content: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None  # set on role="tool" messages


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
        )

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass(frozen=True)
class ChatResult:
    message: Message
    usage: Usage = field(default_factory=Usage)
    finish_reason: str | None = None
    # Reasoning-model thinking (e.g. gpt-oss reasoning_content). Kept for run
    # traces only — it must never be fed back into the message history.
    reasoning: str | None = None


class ChatProvider(Protocol):
    def complete(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec] = (),
    ) -> ChatResult:
        """Run one chat completion. Raises ProviderError on failure."""
        ...
