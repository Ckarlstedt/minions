"""The minion loop: bounded tool-calling until a report is submitted.

Budget model (ADR-003):
- `max_steps` counts model calls. One step before the budget runs out the loop
  injects FORCE_REPORT_MESSAGE; the model then gets up to EXTRA_STEPS calls to
  produce a valid submit_report before the run is declared failed.
- The context guard uses exact `prompt_tokens` from the last response (the
  server reports them), forcing an early finish before the 32k server wall.

Invalid submissions (bad JSON, schema violations) are returned to the model
as tool results so it can correct itself — a small model's first JSON attempt
is not always its best.

A tool call byte-identical (after argument canonicalization) to an earlier
one is not re-run: the repository cannot change mid-run (the tools are
read-only), so the model gets a short pointer to the earlier result instead
of a repeated dump — small models loop on the same query when stuck, and
each repeat burns a step and re-buys the same tokens.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from pydantic import ValidationError

from minions.agent.prompts import (
    EMPTY_MESSAGE_NUDGE,
    FORCE_REPORT_MESSAGE,
    NUDGE_MESSAGE,
    SYSTEM_PROMPT,
    task_message,
)
from minions.config import Settings
from minions.providers.base import ChatProvider, Message, ToolCall, ToolSpec, Usage
from minions.report import SUBMIT_REPORT_PARAMETERS, FlatSubmission, ReportSubmission
from minions.tools.base import ToolRegistry
from minions.tools.workspace import Workspace
from minions.trace import TraceWriter

logger = logging.getLogger(__name__)

EXTRA_STEPS = 2
MAX_NUDGES = 3

SUBMIT_REPORT_SPEC = ToolSpec(
    name="submit_report",
    description=(
        "Deliver your final investigation report. Call this exactly once, as your last action."
    ),
    parameters=SUBMIT_REPORT_PARAMETERS,
)


@dataclass(frozen=True)
class LoopOutcome:
    submission: ReportSubmission | None
    failure_reason: str | None
    steps: int
    usage: Usage


def run_loop(
    question: str,
    workspace: Workspace,
    provider: ChatProvider,
    registry: ToolRegistry,
    settings: Settings,
    trace: TraceWriter,
) -> LoopOutcome:
    messages: list[Message] = [
        Message(role="system", content=SYSTEM_PROMPT),
        Message(role="user", content=task_message(question, workspace, settings.max_steps)),
    ]
    specs = [*registry.specs, SUBMIT_REPORT_SPEC]
    trace.event("start", question=question, workspace=str(workspace.root), model=settings.model)

    usage_total = Usage()
    steps = 0
    nudges = 0
    forced = False
    seen_calls: dict[tuple[str, str], int] = {}

    while steps < settings.max_steps + EXTRA_STEPS:
        result = provider.complete(messages, specs)
        steps += 1
        usage_total += result.usage
        trace.event(
            "model_response",
            step=steps,
            content=result.message.content,
            reasoning=result.reasoning,
            tool_calls=[
                {"name": c.name, "arguments": c.arguments} for c in result.message.tool_calls
            ],
            prompt_tokens=result.usage.prompt_tokens,
            completion_tokens=result.usage.completion_tokens,
        )
        messages.append(result.message)

        if result.message.tool_calls:
            for call in result.message.tool_calls:
                if call.name == "submit_report":
                    submission, error = _parse_submission(call)
                    if submission is not None:
                        trace.event("report_submitted", step=steps)
                        return LoopOutcome(submission, None, steps, usage_total)
                    messages.append(Message(role="tool", content=error, tool_call_id=call.id))
                    trace.event("invalid_submission", step=steps, error=error)
                else:
                    output = _run_tool(call, registry, seen_calls, steps, forced=forced)
                    messages.append(Message(role="tool", content=output, tool_call_id=call.id))
                    trace.event("tool_result", step=steps, tool=call.name, output=output)
        else:
            # Small models sometimes emit the report JSON as plain text instead
            # of a tool call. Salvage it: same schema validation, and the
            # citation verifier still runs on the result — nothing is trusted
            # more just because it arrived through the wrong channel.
            salvaged = _salvage_submission(result.message.content or "")
            if salvaged is not None:
                trace.event("report_salvaged_from_text", step=steps)
                return LoopOutcome(salvaged, None, steps, usage_total)
            nudges += 1
            if nudges > MAX_NUDGES:
                return LoopOutcome(
                    None, "model stopped calling tools and never submitted a report",
                    steps, usage_total,
                )
            empty = not (result.message.content or "").strip()
            nudge = EMPTY_MESSAGE_NUDGE if empty else NUDGE_MESSAGE
            messages.append(Message(role="user", content=nudge))
            trace.event("nudge", step=steps, empty_response=empty)

        out_of_steps = steps >= settings.max_steps - 1
        out_of_context = result.usage.prompt_tokens > settings.context_token_limit
        if not forced and (out_of_steps or out_of_context):
            forced = True
            messages.append(Message(role="user", content=FORCE_REPORT_MESSAGE))
            trace.event(
                "forced_finish",
                step=steps,
                reason="context" if out_of_context else "steps",
            )

    return LoopOutcome(None, "budget exhausted without a valid report", steps, usage_total)


def _parse_submission(call: ToolCall) -> tuple[ReportSubmission | None, str | None]:
    try:
        raw = json.loads(call.arguments)
    except ValueError as exc:
        return None, (
            f"Error: submit_report arguments were not valid JSON ({exc}). "
            "Call submit_report again with valid JSON."
        )
    try:
        return FlatSubmission.model_validate(raw).to_submission(), None
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors()[:5]
        )
        return None, (
            f"Error: report does not match the required schema ({problems}). "
            "Fix these fields and call submit_report again."
        )


def _salvage_submission(content: str) -> ReportSubmission | None:
    """Extract a valid report from plain text the model emitted instead of a
    real submit_report call. Handles two observed shapes:

    - the bare report JSON pasted into chat content (gpt-oss), and
    - an unparsed tool-call envelope such as Qwen's
      ``<tool_call>{"name": "submit_report", "arguments": {…}}`` — possibly
      repeated — when the server's template parser fails to convert it.

    Returns None when nothing validates; the channel grants no extra trust
    (schema validation and citation verification still apply).
    """
    for candidate in _json_candidates(content):
        raw: object = candidate
        if candidate.get("name") == "submit_report":
            raw = candidate.get("arguments")
            if isinstance(raw, str):
                try:
                    raw = json.loads(raw)
                except ValueError:
                    continue
        if not isinstance(raw, dict) or "summary" not in raw:
            continue
        try:
            return FlatSubmission.model_validate(raw).to_submission()
        except ValidationError:
            continue
    return None


def _json_candidates(content: str) -> list[dict]:
    """Dicts worth trying: the widest {...} span, then the first balanced object
    (which survives concatenated/repeated blocks where the wide span is invalid)."""
    candidates = []
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end <= start:
        return []
    for text in (content[start : end + 1], _first_json_object(content, start)):
        if not text:
            continue
        try:
            parsed = json.loads(text)
        except ValueError:
            continue
        if isinstance(parsed, dict) and parsed not in candidates:
            candidates.append(parsed)
    return candidates


def _first_json_object(content: str, start: int) -> str | None:
    """Substring of the first balanced JSON object starting at `start`."""
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(content)):
        char = content[i]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return content[start : i + 1]
    return None


def _run_tool(
    call: ToolCall,
    registry: ToolRegistry,
    seen_calls: dict[tuple[str, str], int],
    step: int,
    *,
    forced: bool,
) -> str:
    if forced:
        return "Error: budget exhausted — call submit_report now, no other tools."
    try:
        arguments = json.loads(call.arguments) if call.arguments.strip() else {}
    except ValueError as exc:
        return f"Error: tool arguments were not valid JSON ({exc}). Retry with valid JSON."
    if not isinstance(arguments, dict):
        return "Error: tool arguments must be a JSON object."
    key = (call.name, json.dumps(arguments, sort_keys=True))
    first_step = seen_calls.get(key)
    if first_step is not None:
        return (
            f"Duplicate call: you already ran this exact {call.name} call at step "
            f"{first_step}, and the repository has not changed — the result would be "
            "identical. Vary the arguments, try a different tool, or call submit_report."
        )
    seen_calls[key] = step
    return registry.run(call.name, arguments)
