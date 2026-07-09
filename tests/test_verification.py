from __future__ import annotations

from minions.report import Confidence, Evidence, Finding, InvestigationReport
from minions.tools.workspace import Workspace
from minions.verification import verify_report


def report_with(*evidence: Evidence, confidence: Confidence = Confidence.HIGH):
    return InvestigationReport(
        question="q?",
        status="complete",
        summary="s",
        findings=[Finding(claim="c", confidence=confidence, evidence=list(evidence))],
    )


def test_exact_excerpt_verifies(plain_ws: Workspace) -> None:
    ev = Evidence(file="src/app.py", start_line=5, end_line=6, excerpt="def load_config(path):")
    report = verify_report(report_with(ev), plain_ws)
    assert ev.verified is True
    assert report.verification_rate == 1.0


def test_whitespace_differences_tolerated(plain_ws: Workspace) -> None:
    ev = Evidence(
        file="src/app.py", start_line=5, end_line=8,
        excerpt="def  load_config(path):\n    \"\"\"Load configuration",
    )
    verify_report(report_with(ev), plain_ws)
    assert ev.verified is True


def test_line_numbers_slightly_off_tolerated(plain_ws: Workspace) -> None:
    ev = Evidence(file="src/app.py", start_line=1, end_line=2, excerpt="def load_config(path):")
    verify_report(report_with(ev), plain_ws)
    assert ev.verified is True  # actual line 5 is within the ±10 window


def test_fabricated_excerpt_fails_and_downgrades(plain_ws: Workspace) -> None:
    ev = Evidence(file="src/app.py", start_line=5, end_line=8, excerpt="def load_yaml_config():")
    report = verify_report(report_with(ev), plain_ws)
    assert ev.verified is False
    assert report.findings[0].confidence == Confidence.LOW
    assert report.verification_rate == 0.0


def test_far_off_line_numbers_fail(plain_ws: Workspace) -> None:
    # "def load_config" really exists — but at line 5, far outside the cited window.
    ev = Evidence(file="src/app.py", start_line=200, end_line=201, excerpt="def load_config")
    verify_report(report_with(ev), plain_ws)
    assert ev.verified is False


def test_missing_file_fails(plain_ws: Workspace) -> None:
    ev = Evidence(file="nope.py", start_line=1, end_line=2, excerpt="anything")
    verify_report(report_with(ev), plain_ws)
    assert ev.verified is False


def test_path_escape_fails(plain_ws: Workspace) -> None:
    ev = Evidence(file="../../etc/passwd", start_line=1, end_line=2, excerpt="root")
    verify_report(report_with(ev), plain_ws)
    assert ev.verified is False


def test_empty_excerpt_fails(plain_ws: Workspace) -> None:
    ev = Evidence(file="src/app.py", start_line=1, end_line=2, excerpt="   ")
    verify_report(report_with(ev), plain_ws)
    assert ev.verified is False


def test_inverted_range_fails(plain_ws: Workspace) -> None:
    ev = Evidence(file="src/app.py", start_line=8, end_line=5, excerpt="def load_config")
    verify_report(report_with(ev), plain_ws)
    assert ev.verified is False


def test_excerpt_copied_from_read_file_output_verifies(plain_ws: Workspace) -> None:
    """End-to-end shape of the real failure mode: model copies 'NN| ' prefixes."""
    from minions.report import FlatSubmission

    submission = FlatSubmission(
        summary="s",
        findings=[
            {
                "claim": "c",
                "file": "src/app.py",
                "start_line": 5,
                "end_line": 6,
                "excerpt": '5| def load_config(path):\n6|     """Load configuration',
            }
        ],
    ).to_submission()
    report = report_with(*submission.findings[0].evidence)
    verify_report(report, plain_ws)
    assert report.verification_rate == 1.0


def test_no_evidence_rate_is_none(plain_ws: Workspace) -> None:
    report = verify_report(report_with(), plain_ws)
    assert report.verification_rate is None


def test_mixed_evidence_keeps_confidence(plain_ws: Workspace) -> None:
    good = Evidence(file="src/app.py", start_line=5, end_line=6, excerpt="def load_config(path):")
    bad = Evidence(file="src/app.py", start_line=5, end_line=6, excerpt="fabricated nonsense")
    report = verify_report(report_with(good, bad), plain_ws)
    assert report.findings[0].confidence == Confidence.HIGH
    assert report.verification_rate == 0.5
