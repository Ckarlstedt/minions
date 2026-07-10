from __future__ import annotations

import io
import json
from pathlib import Path

from minions.trace import NullTrace, ProgressTrace, TraceWriter


class RecordingTrace(NullTrace):
    def __init__(self) -> None:
        super().__init__()
        self.events: list[tuple[str, dict]] = []

    def event(self, kind: str, **payload: object) -> None:
        self.events.append((kind, payload))


def test_trace_writer_writes_jsonl(tmp_path: Path) -> None:
    trace = TraceWriter.create(tmp_path, "Where is the config?")
    trace.event("start", model="m")
    trace.event("end", status="complete")
    trace.close()
    lines = [json.loads(line) for line in trace.path.read_text().splitlines()]
    assert [line["event"] for line in lines] == ["start", "end"]
    assert "where-is-the-config" in trace.path.name


def test_progress_trace_renders_and_forwards() -> None:
    inner = RecordingTrace()
    out = io.StringIO()
    trace = ProgressTrace(inner, stream=out)

    trace.event("start", question="q?", model="test-model", workspace="/x")
    trace.event(
        "model_response",
        step=1,
        tool_calls=[{"name": "search", "arguments": '{"pattern": "x"}'}],
        content=None,
        prompt_tokens=10,
        completion_tokens=5,
    )
    trace.event("tool_result", step=1, tool="search", output="3 matches\nsrc/a.py:1: x")
    trace.event("nudge", step=2, empty_response=False)
    trace.event("forced_finish", step=3, reason="steps")
    trace.event("report_submitted", step=4)
    trace.event("end", status="complete", verification_rate=0.75, stats={})

    text = out.getvalue()
    assert "test-model" in text
    assert 'search({"pattern": "x"})' in text
    assert "3 matches" in text
    assert "nudging" in text
    assert "budget low (steps)" in text
    assert "report received" in text
    assert "done: complete, 75% of citations verified" in text
    # Every event reached the inner (JSONL) trace regardless of rendering.
    assert [kind for kind, _ in inner.events] == [
        "start",
        "model_response",
        "tool_result",
        "nudge",
        "forced_finish",
        "report_submitted",
        "end",
    ]


def test_progress_trace_clips_long_arguments() -> None:
    inner = RecordingTrace()
    out = io.StringIO()
    ProgressTrace(inner, stream=out).event(
        "model_response",
        step=1,
        tool_calls=[{"name": "read_file", "arguments": "x" * 500}],
    )
    line = out.getvalue().strip()
    assert len(line) < 140
    assert "…" in line
