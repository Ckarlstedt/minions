"""JSONL run traces: the audit trail behind every report (ADR-004).

Traces live in the state directory (default ~/.local/state/minions/runs/),
never inside the investigated repository — minions are read-only there.

`ProgressTrace` decorates any trace with live human-readable progress lines
(one per event, elapsed-time prefixed) so an interactive user can see that a
multi-minute investigation is actually moving.
"""

from __future__ import annotations

import json
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, Self


class TraceWriter:
    def __init__(self, path: Path, stream: IO[str]) -> None:
        self.path = path
        self._stream = stream

    @classmethod
    def create(cls, state_dir: Path, question: str) -> Self:
        runs_dir = state_dir / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%S")
        slug = re.sub(r"[^a-z0-9]+", "-", question.lower()).strip("-")[:40] or "investigation"
        path = runs_dir / f"{stamp}-{slug}.jsonl"
        return cls(path, path.open("a", encoding="utf-8"))

    def event(self, kind: str, **payload: object) -> None:
        record = {"ts": time.time(), "event": kind, **payload}
        self._stream.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        self._stream.flush()

    def close(self) -> None:
        self._stream.close()


class NullTrace(TraceWriter):
    """Used when tracing is disabled (e.g. in tests)."""

    def __init__(self) -> None:
        self.path = Path("/dev/null")

    def event(self, kind: str, **payload: object) -> None:
        pass

    def close(self) -> None:
        pass


_ARGS_PREVIEW_CHARS = 70


class ProgressTrace(TraceWriter):
    """Forwards events to an inner trace and renders progress to a stream."""

    def __init__(self, inner: TraceWriter, stream: IO[str] | None = None) -> None:
        self.path = inner.path
        self._inner = inner
        self._out = stream if stream is not None else sys.stderr
        self._started = time.monotonic()

    def event(self, kind: str, **payload: object) -> None:
        self._inner.event(kind, **payload)
        line = self._render(kind, payload)
        if line:
            elapsed = time.monotonic() - self._started
            print(f"[{elapsed:6.1f}s] {line}", file=self._out, flush=True)

    def close(self) -> None:
        self._inner.close()

    def _render(self, kind: str, payload: dict) -> str | None:
        step = payload.get("step")
        if kind == "start":
            return f"investigating with {payload.get('model')} — {payload.get('question')}"
        if kind == "model_response":
            calls = payload.get("tool_calls") or []
            if not calls:
                return f"step {step}: model replied without a tool call"
            rendered = ", ".join(
                f"{c['name']}({_clip(c.get('arguments', ''))})"
                for c in calls  # type: ignore[index]
            )
            return f"step {step}: {rendered}"
        if kind == "tool_result":
            output = str(payload.get("output", ""))
            return f"step {step}:   ↳ {_clip(output.splitlines()[0] if output else '')}"
        if kind == "nudge":
            return f"step {step}: nudging the model back to the tools"
        if kind == "forced_finish":
            return f"step {step}: budget low ({payload.get('reason')}) — demanding the report"
        if kind == "invalid_submission":
            return f"step {step}: report submission invalid — asking for a fix"
        if kind == "report_submitted":
            return f"step {step}: report received"
        if kind == "report_salvaged_from_text":
            return f"step {step}: report salvaged from plain-text reply"
        if kind == "end":
            rate = payload.get("verification_rate")
            verified = f", {rate:.0%} of citations verified" if isinstance(rate, float) else ""
            return f"done: {payload.get('status')}{verified}"
        return None


def _clip(text: str) -> str:
    text = " ".join(str(text).split())
    if len(text) > _ARGS_PREVIEW_CHARS:
        return text[:_ARGS_PREVIEW_CHARS] + "…"
    return text
