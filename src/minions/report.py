"""Report schema: the contract between a minion and GRU.

The minion submits a ``ReportSubmission`` (via the submit_report tool); the
service wraps it into an ``InvestigationReport`` with run statistics and
deterministic verification results (see minions.verification, ADR-004).
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

MAX_EXCERPT_CHARS = 2_000
_RENDERED_EXCERPT_CHARS = 300


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Evidence(BaseModel):
    """A verbatim citation. `verified` is set by the deterministic verifier."""

    file: str = Field(description="Repository-relative file path")
    start_line: int = Field(ge=1, description="First line of the cited region (1-based)")
    end_line: int = Field(ge=1, description="Last line of the cited region (inclusive)")
    excerpt: str = Field(
        max_length=MAX_EXCERPT_CHARS,
        description="Verbatim text copied exactly from the file, without line numbers",
    )
    verified: bool | None = Field(
        default=None,
        description="Set by the verifier; never set this yourself",
    )


class Finding(BaseModel):
    claim: str = Field(description="One factual statement answering part of the question")
    confidence: Confidence = Field(description="Your confidence in the claim")
    evidence: list[Evidence] = Field(
        default_factory=list,
        description="Citations backing the claim; a claim without evidence is weak",
    )


class ReportSubmission(BaseModel):
    """What the minion itself provides through the submit_report tool."""

    summary: str = Field(description="2-5 sentence direct answer to the question")
    findings: list[Finding] = Field(description="Individual evidence-backed findings")
    unanswered: list[str] = Field(
        default_factory=list,
        description="Parts of the question you could not answer — never guess instead",
    )


class FlatFinding(BaseModel):
    """One finding with exactly one citation, as small models actually submit them.

    gpt-oss-class models ignore nested $defs schemas in tool definitions (see
    .agents/findings/2026-07-09-gpt-oss-tool-calling.md), so the submit_report
    wire format is flat; the service converts to the rich Finding/Evidence model.
    """

    claim: str
    confidence: Confidence = Confidence.MEDIUM
    file: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    excerpt: str = Field(max_length=MAX_EXCERPT_CHARS)


# Matches the "NN| " prefixes of read_file output. Small models copy excerpts
# from tool output verbatim *including* these prefixes no matter what the
# prompt says; stripping them at intake is engineering, prompting is hope.
# (Risk: a real file line starting with `123|` loses its prefix and may fail
# verification — visible as ✗, never as a false ✓.)
_LINE_NUMBER_PREFIX = re.compile(r"^\s*\d+\|\s?", flags=re.MULTILINE)


def strip_line_number_prefixes(excerpt: str) -> str:
    return _LINE_NUMBER_PREFIX.sub("", excerpt)


class FlatSubmission(BaseModel):
    summary: str
    findings: list[FlatFinding] = Field(default_factory=list)
    unanswered: list[str] = Field(default_factory=list)

    def to_submission(self) -> ReportSubmission:
        return ReportSubmission(
            summary=self.summary,
            findings=[
                Finding(
                    claim=flat.claim,
                    confidence=flat.confidence,
                    evidence=[
                        Evidence(
                            file=flat.file,
                            start_line=flat.start_line,
                            end_line=flat.end_line,
                            excerpt=strip_line_number_prefixes(flat.excerpt),
                        )
                    ],
                )
                for flat in self.findings
            ],
            unanswered=self.unanswered,
        )


# Hand-written (not model_json_schema()): flat, no $defs/$refs, short descriptions.
SUBMIT_REPORT_PARAMETERS: dict = {
    "type": "object",
    "properties": {
        "summary": {
            "type": "string",
            "description": "2-5 sentence direct answer to the question",
        },
        "findings": {
            "type": "array",
            "description": "Evidence-backed findings; each cites one file region verbatim",
            "items": {
                "type": "object",
                "properties": {
                    "claim": {"type": "string", "description": "One factual statement"},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    "file": {"type": "string", "description": "Repository-relative file path"},
                    "start_line": {"type": "integer", "description": "First cited line (1-based)"},
                    "end_line": {"type": "integer", "description": "Last cited line (inclusive)"},
                    "excerpt": {
                        "type": "string",
                        "description": "Verbatim text copied exactly from the file",
                    },
                },
                "required": ["claim", "file", "start_line", "end_line", "excerpt"],
            },
        },
        "unanswered": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Parts of the question you could not answer",
        },
    },
    "required": ["summary", "findings"],
}


class RunStats(BaseModel):
    model: str
    steps: int
    prompt_tokens: int
    completion_tokens: int
    duration_seconds: float
    trace_path: str | None = None


class InvestigationReport(BaseModel):
    version: int = 1
    question: str
    status: Literal["complete", "partial", "failed"]
    summary: str
    findings: list[Finding] = Field(default_factory=list)
    unanswered: list[str] = Field(default_factory=list)
    verification_rate: float | None = None
    stats: RunStats | None = None

    @classmethod
    def from_submission(
        cls, question: str, submission: ReportSubmission, stats: RunStats
    ) -> InvestigationReport:
        return cls(
            question=question,
            status="partial" if submission.unanswered else "complete",
            summary=submission.summary,
            findings=submission.findings,
            unanswered=submission.unanswered,
            stats=stats,
        )

    @classmethod
    def failure(cls, question: str, reason: str, stats: RunStats) -> InvestigationReport:
        return cls(
            question=question,
            status="failed",
            summary=f"Investigation failed: {reason}",
            stats=stats,
        )

    def to_markdown(self) -> str:
        lines = [f"**Question:** {self.question}", f"**Status:** {self._status_line()}", ""]
        lines += ["**Answer:** " + self.summary, ""]
        if self.findings:
            lines.append("**Findings:**")
            for i, finding in enumerate(self.findings, 1):
                lines.append(f"{i}. {finding.claim} _({finding.confidence})_")
                for ev in finding.evidence:
                    mark = {True: "✓", False: "✗ UNVERIFIED", None: "?"}[ev.verified]
                    lines.append(f"   - `{ev.file}:{ev.start_line}-{ev.end_line}` {mark}")
                    excerpt = " ".join(ev.excerpt.split())
                    if len(excerpt) > _RENDERED_EXCERPT_CHARS:
                        excerpt = excerpt[:_RENDERED_EXCERPT_CHARS] + "…"
                    if excerpt:
                        lines.append(f"     > {excerpt}")
            lines.append("")
        if self.unanswered:
            lines.append("**Not answered:**")
            lines += [f"- {item}" for item in self.unanswered]
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def _status_line(self) -> str:
        parts = [self.status]
        if self.verification_rate is not None:
            parts.append(f"{self.verification_rate:.0%} of citations verified")
        if self.stats is not None:
            parts.append(
                f"{self.stats.steps} steps, "
                f"{self.stats.prompt_tokens + self.stats.completion_tokens} local tokens, "
                f"{self.stats.duration_seconds:.1f}s, {self.stats.model}"
            )
        return " — ".join(parts)
