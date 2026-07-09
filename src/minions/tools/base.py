"""Tool primitives: definition, registry, error type.

Handlers are plain Python callables with keyword arguments. There is no
generic shell tool anywhere in this package and there must never be one —
read-only is enforced by what the registry contains (ADR-005).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from minions.providers.base import ToolSpec

logger = logging.getLogger(__name__)

TRUNCATION_NOTICE = "\n[output truncated — narrow your query for more detail]"


class ToolError(Exception):
    """A tool-level failure whose message is safe and useful to show the model."""


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict  # JSON Schema for the arguments object
    handler: Callable[..., str]

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(name=self.name, description=self.description, parameters=self.parameters)


class ToolRegistry:
    def __init__(self, tools: list[Tool], max_output_chars: int) -> None:
        self._tools = {tool.name: tool for tool in tools}
        self._max_output_chars = max_output_chars

    @property
    def specs(self) -> list[ToolSpec]:
        return [tool.spec for tool in self._tools.values()]

    def run(self, name: str, arguments: dict) -> str:
        """Execute a tool. Returns output or an `Error: ...` string for the model.

        Failures are returned (not raised) so the loop can hand them back to
        the model as tool results and let it correct course.
        """
        tool = self._tools.get(name)
        if tool is None:
            available = ", ".join(sorted(self._tools))
            return f"Error: unknown tool {name!r}. Available tools: {available}"
        try:
            output = tool.handler(**arguments)
        except ToolError as exc:
            logger.debug("tool %s rejected input %r: %s", name, arguments, exc)
            return f"Error: {exc}"
        except TypeError as exc:
            # Wrong/missing argument names from the model.
            return f"Error: invalid arguments for {name}: {exc}"
        if len(output) > self._max_output_chars:
            output = output[: self._max_output_chars] + TRUNCATION_NOTICE
        return output


def require_int(value: object, name: str, *, minimum: int | None = None) -> int:
    """Coerce a model-supplied argument to int with a model-readable error."""
    try:
        result = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise ToolError(f"{name} must be an integer, got {value!r}") from None
    if minimum is not None and result < minimum:
        raise ToolError(f"{name} must be >= {minimum}, got {result}")
    return result
