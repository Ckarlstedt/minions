"""InvestigationService: the transport-agnostic core (ADR-002).

Adapters (CLI today; MCP/HTTP if ever needed) construct a service and call
investigate(). Nothing in here knows how it was invoked.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from minions.agent.loop import run_loop
from minions.config import Settings
from minions.providers.base import ChatProvider
from minions.providers.openai_compat import OpenAICompatProvider
from minions.report import InvestigationReport, RunStats
from minions.tools.registry import build_registry
from minions.tools.workspace import Workspace
from minions.trace import TraceWriter
from minions.verification import verify_report

logger = logging.getLogger(__name__)


class InvestigationService:
    def __init__(self, settings: Settings, provider: ChatProvider | None = None) -> None:
        self._settings = settings
        self._provider = provider or OpenAICompatProvider(settings)

    def investigate(
        self,
        question: str,
        repo: Path | str = ".",
        trace: TraceWriter | None = None,
    ) -> InvestigationReport:
        workspace = Workspace.discover(repo)
        registry = build_registry(workspace, self._settings.max_tool_output_chars)
        trace = trace or TraceWriter.create(self._settings.state_dir, question)

        started = time.monotonic()
        try:
            outcome = run_loop(question, workspace, self._provider, registry, self._settings, trace)
            stats = RunStats(
                model=self._settings.model,
                steps=outcome.steps,
                prompt_tokens=outcome.usage.prompt_tokens,
                completion_tokens=outcome.usage.completion_tokens,
                duration_seconds=time.monotonic() - started,
                trace_path=str(trace.path),
            )
            if outcome.submission is not None:
                report = InvestigationReport.from_submission(question, outcome.submission, stats)
            else:
                report = InvestigationReport.failure(
                    question, outcome.failure_reason or "unknown", stats
                )
            verify_report(report, workspace)
            trace.event(
                "end",
                status=report.status,
                verification_rate=report.verification_rate,
                stats=stats.model_dump(),
            )
            return report
        finally:
            trace.close()
