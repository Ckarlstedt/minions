"""Deterministic citation verification (ADR-004).

For every Evidence item the verifier re-reads the cited file and checks that
the verbatim excerpt actually appears near the cited lines. Comparison is
whitespace-normalized (formatting-tolerant, content-exact). A tolerance
window of ±TOLERANCE_LINES forgives slightly-off line numbers — small models
are reliably right about *what* they saw and less reliable about exactly
*where*, and a near-miss on line numbers should not discredit real evidence.

This proves the excerpt exists; whether the excerpt supports the claim
remains GRU's judgment. That split is the point: existence is checkable by a
machine, interpretation is what GRU is paid tokens for.
"""

from __future__ import annotations

from minions.report import Confidence, InvestigationReport
from minions.tools.base import ToolError
from minions.tools.fs import read_file_text
from minions.tools.workspace import Workspace

TOLERANCE_LINES = 10


def _normalize(text: str) -> str:
    return " ".join(text.split())


def verify_report(report: InvestigationReport, workspace: Workspace) -> InvestigationReport:
    """Set Evidence.verified in place; downgrade findings with no verified evidence.

    Returns the same report object for chaining.
    """
    total = 0
    verified_count = 0

    for finding in report.findings:
        for evidence in finding.evidence:
            total += 1
            evidence.verified = _verify_one(evidence, workspace)
            verified_count += evidence.verified

        if finding.evidence and not any(ev.verified for ev in finding.evidence):
            finding.confidence = Confidence.LOW

    report.verification_rate = (verified_count / total) if total else None
    return report


def _verify_one(evidence, workspace: Workspace) -> bool:
    needle = _normalize(evidence.excerpt)
    if not needle:
        return False
    try:
        lines = read_file_text(workspace, evidence.file)
    except ToolError:
        return False

    if evidence.end_line < evidence.start_line:
        return False
    window_start = max(0, evidence.start_line - 1 - TOLERANCE_LINES)
    window_end = min(len(lines), evidence.end_line + TOLERANCE_LINES)
    haystack = _normalize("\n".join(lines[window_start:window_end]))
    return needle in haystack
