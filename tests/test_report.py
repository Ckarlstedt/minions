from __future__ import annotations

from minions.report import (
    Confidence,
    Evidence,
    Finding,
    InvestigationReport,
    ReportSubmission,
    RunStats,
)

STATS = RunStats(
    model="test-model", steps=3, prompt_tokens=100, completion_tokens=50, duration_seconds=1.5
)


def submission(**overrides) -> ReportSubmission:
    base = {
        "summary": "The config is loaded in src/app.py.",
        "findings": [
            Finding(
                claim="load_config reads JSON",
                confidence=Confidence.HIGH,
                evidence=[
                    Evidence(
                        file="src/app.py", start_line=5, end_line=8, excerpt="def load_config"
                    )
                ],
            )
        ],
        "unanswered": [],
    }
    base.update(overrides)
    return ReportSubmission(**base)


def test_status_complete() -> None:
    report = InvestigationReport.from_submission("q?", submission(), STATS)
    assert report.status == "complete"


def test_status_partial_when_unanswered() -> None:
    report = InvestigationReport.from_submission("q?", submission(unanswered=["tests?"]), STATS)
    assert report.status == "partial"


def test_failure_report() -> None:
    report = InvestigationReport.failure("q?", "budget exhausted", STATS)
    assert report.status == "failed"
    assert "budget exhausted" in report.summary


def test_markdown_rendering() -> None:
    report = InvestigationReport.from_submission("Where is config loaded?", submission(), STATS)
    report.findings[0].evidence[0].verified = True
    report.verification_rate = 1.0
    md = report.to_markdown()
    assert "**Question:** Where is config loaded?" in md
    assert "`src/app.py:5-8` ✓" in md
    assert "100% of citations verified" in md
    assert "> def load_config" in md


def test_markdown_marks_unverified() -> None:
    report = InvestigationReport.from_submission("q?", submission(), STATS)
    report.findings[0].evidence[0].verified = False
    md = report.to_markdown()
    assert "✗ UNVERIFIED" in md


def test_markdown_truncates_long_excerpts() -> None:
    sub = submission()
    sub.findings[0].evidence[0].excerpt = "x" * 900
    report = InvestigationReport.from_submission("q?", sub, STATS)
    md = report.to_markdown()
    assert "x" * 301 not in md and "…" in md


def test_flat_submission_converts_to_rich() -> None:
    from minions.report import FlatSubmission

    flat = FlatSubmission.model_validate(
        {
            "summary": "s",
            "findings": [
                {
                    "claim": "c",
                    "file": "a.py",
                    "start_line": 1,
                    "end_line": 2,
                    "excerpt": "x",
                    "extra_field_from_model": "ignored",
                }
            ],
        }
    )
    sub = flat.to_submission()
    assert sub.findings[0].confidence == Confidence.MEDIUM  # default when omitted
    assert sub.findings[0].evidence[0].file == "a.py"
    assert sub.unanswered == []


def test_line_number_prefixes_stripped_at_intake() -> None:
    from minions.report import FlatSubmission, strip_line_number_prefixes

    prefixed = "57|     def resolve(self, path):\n58|         candidate = Path(path)"
    assert strip_line_number_prefixes(prefixed) == (
        "    def resolve(self, path):\n        candidate = Path(path)"
    )

    flat = FlatSubmission(
        summary="s",
        findings=[
            {
                "claim": "c",
                "file": "a.py",
                "start_line": 57,
                "end_line": 58,
                "excerpt": prefixed,
            }
        ],
    )
    assert "57|" not in flat.to_submission().findings[0].evidence[0].excerpt


def test_json_round_trip() -> None:
    report = InvestigationReport.from_submission("q?", submission(), STATS)
    restored = InvestigationReport.model_validate_json(report.model_dump_json())
    assert restored == report
