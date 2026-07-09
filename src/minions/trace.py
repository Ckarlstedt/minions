"""JSONL run traces: the audit trail behind every report (ADR-004).

Traces live in the state directory (default ~/.local/state/minions/runs/),
never inside the investigated repository — minions are read-only there.
"""

from __future__ import annotations

import json
import re
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
