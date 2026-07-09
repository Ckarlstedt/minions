from __future__ import annotations

import dataclasses
import json

from minions.agent.loop import run_loop
from minions.agent.prompts import FORCE_REPORT_MESSAGE
from minions.config import Settings
from minions.providers.base import ChatResult, Message, ToolCall, Usage
from minions.providers.fake import FakeProvider
from minions.tools.registry import build_registry
from minions.tools.workspace import Workspace
from minions.trace import NullTrace

SETTINGS = Settings(max_steps=8, max_tool_output_chars=8000)

VALID_REPORT_ARGS = {
    "summary": "load_config parses JSON config files.",
    "findings": [
        {
            "claim": "load_config reads JSON",
            "confidence": "high",
            "file": "src/app.py",
            "start_line": 5,
            "end_line": 8,
            "excerpt": "def load_config(path):",
        }
    ],
    "unanswered": [],
}


def tool_call(name: str, args: dict | str, call_id: str = "c1", prompt_tokens: int = 100):
    arguments = args if isinstance(args, str) else json.dumps(args)
    return ChatResult(
        message=Message(
            role="assistant",
            tool_calls=(ToolCall(id=call_id, name=name, arguments=arguments),),
        ),
        usage=Usage(prompt_tokens=prompt_tokens, completion_tokens=20),
    )


def text_reply(text: str) -> ChatResult:
    return ChatResult(message=Message(role="assistant", content=text), usage=Usage(50, 10))


def run(provider: FakeProvider, ws: Workspace, settings: Settings = SETTINGS):
    registry = build_registry(ws, settings.max_tool_output_chars)
    return run_loop("Where is config loaded?", ws, provider, registry, settings, NullTrace())


def test_tool_then_submit(plain_ws: Workspace) -> None:
    provider = FakeProvider(
        [
            tool_call("search", {"pattern": "load_config"}),
            tool_call("submit_report", VALID_REPORT_ARGS, call_id="c2"),
        ]
    )
    outcome = run(provider, plain_ws)
    assert outcome.submission is not None
    assert outcome.submission.summary.startswith("load_config")
    assert outcome.steps == 2
    assert outcome.usage.prompt_tokens == 200

    # The second request must contain the real tool result of the first search.
    second_request_messages = provider.requests[1][0]
    tool_messages = [m for m in second_request_messages if m.role == "tool"]
    assert any("src/app.py:5:" in (m.content or "") for m in tool_messages)


def test_invalid_submission_gets_retried(plain_ws: Workspace) -> None:
    provider = FakeProvider(
        [
            tool_call("submit_report", '{"summary": broken json'),
            # finding item missing file/lines/excerpt → schema error
            tool_call(
                "submit_report", {"summary": "s", "findings": [{"claim": "c"}]}, call_id="c2"
            ),
            tool_call("submit_report", VALID_REPORT_ARGS, call_id="c3"),
        ]
    )
    outcome = run(provider, plain_ws)
    assert outcome.submission is not None
    errors = [
        m.content
        for request, _ in provider.requests
        for m in request
        if m.role == "tool" and (m.content or "").startswith("Error")
    ]
    assert any("valid JSON" in e for e in errors)
    assert any("schema" in e for e in errors)


def test_plain_text_gets_nudged_then_fails(plain_ws: Workspace) -> None:
    provider = FakeProvider([text_reply(f"reply {n}") for n in range(4)])
    outcome = run(provider, plain_ws)
    assert outcome.submission is None
    assert "stopped calling tools" in (outcome.failure_reason or "")


def test_report_as_plain_text_is_salvaged(plain_ws: Workspace) -> None:
    content = "Here is my report:\n" + json.dumps(VALID_REPORT_ARGS)
    provider = FakeProvider([text_reply(content)])
    outcome = run(provider, plain_ws)
    assert outcome.submission is not None
    assert outcome.submission.summary.startswith("load_config")


def test_non_report_text_is_not_salvaged(plain_ws: Workspace) -> None:
    provider = FakeProvider(
        [
            text_reply('I found {"pattern": "load_config"} interesting.'),
            tool_call("submit_report", VALID_REPORT_ARGS),
        ]
    )
    outcome = run(provider, plain_ws)
    assert outcome.submission is not None
    assert outcome.steps == 2  # first reply was nudged, not salvaged


def test_empty_response_gets_specific_nudge(plain_ws: Workspace) -> None:
    from minions.agent.prompts import EMPTY_MESSAGE_NUDGE

    provider = FakeProvider(
        [
            ChatResult(message=Message(role="assistant", content=None), usage=Usage(50, 10)),
            tool_call("submit_report", VALID_REPORT_ARGS),
        ]
    )
    outcome = run(provider, plain_ws)
    assert outcome.submission is not None
    second_request_messages = provider.requests[1][0]
    assert any(m.content == EMPTY_MESSAGE_NUDGE for m in second_request_messages)


def test_budget_forces_report_request(plain_ws: Workspace) -> None:
    settings = dataclasses.replace(SETTINGS, max_steps=2)
    provider = FakeProvider(
        [
            tool_call("search", {"pattern": "config"}),
            tool_call("submit_report", VALID_REPORT_ARGS, call_id="c2"),
        ]
    )
    outcome = run(provider, plain_ws, settings)
    assert outcome.submission is not None
    second_request_messages = provider.requests[1][0]
    assert any(m.content == FORCE_REPORT_MESSAGE for m in second_request_messages)


def test_budget_exhaustion_fails(plain_ws: Workspace) -> None:
    settings = dataclasses.replace(SETTINGS, max_steps=2)
    provider = FakeProvider(
        [tool_call("search", {"pattern": "config"}, call_id=f"c{n}") for n in range(4)]
    )
    outcome = run(provider, plain_ws, settings)
    assert outcome.submission is None
    assert "budget exhausted" in (outcome.failure_reason or "")
    # After forcing, further tool calls are refused.
    last_request_messages = provider.requests[-1][0]
    refusals = [
        m for m in last_request_messages
        if m.role == "tool" and "budget exhausted" in (m.content or "")
    ]
    assert refusals


def test_context_pressure_forces_report(plain_ws: Workspace) -> None:
    provider = FakeProvider(
        [
            tool_call("search", {"pattern": "config"}, prompt_tokens=30_000),
            tool_call("submit_report", VALID_REPORT_ARGS, call_id="c2"),
        ]
    )
    outcome = run(provider, plain_ws)
    assert outcome.submission is not None
    second_request_messages = provider.requests[1][0]
    assert any(m.content == FORCE_REPORT_MESSAGE for m in second_request_messages)


def test_git_tools_only_offered_in_git_repos(plain_ws: Workspace, git_ws: Workspace) -> None:
    plain_names = {t.name for t in build_registry(plain_ws, 8000).specs}
    git_names = {t.name for t in build_registry(git_ws, 8000).specs}
    assert "git_log" not in plain_names
    assert {"git_log", "git_diff", "git_blame"} <= git_names
