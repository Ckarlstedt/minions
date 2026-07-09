from __future__ import annotations

import json

from minions.cli import main


def test_investigate_missing_repo_exits_1(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("MINIONS_STATE_DIR", str(tmp_path / "state"))
    code = main(["investigate", "q?", "--repo", str(tmp_path / "nope")])
    assert code == 1
    assert "error:" in capsys.readouterr().err


def test_doctor_reports_unreachable_server(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("MINIONS_BASE_URL", "http://127.0.0.1:1/v1")
    monkeypatch.setenv("MINIONS_API_KEY", "sk-test")
    monkeypatch.setenv("MINIONS_STATE_DIR", str(tmp_path / "state"))
    code = main(["doctor", "--repo", str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 1
    assert "server reachable" in out and "FAIL" in out
    assert "state dir writable" in out


def test_service_end_to_end_with_fake_provider(tmp_path, plain_ws) -> None:
    """Full service path (loop → stats → verification → markdown) without a server."""
    from minions.config import Settings
    from minions.providers.base import ChatResult, Message, ToolCall, Usage
    from minions.providers.fake import FakeProvider
    from minions.service import InvestigationService

    args = {
        "summary": "Config loading lives in src/app.py.",
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
    }
    provider = FakeProvider(
        [
            ChatResult(
                message=Message(
                    role="assistant",
                    tool_calls=(
                        ToolCall(id="c1", name="submit_report", arguments=json.dumps(args)),
                    ),
                ),
                usage=Usage(500, 100),
            )
        ]
    )
    settings = Settings(state_dir=tmp_path / "state")
    service = InvestigationService(settings, provider=provider)
    report = service.investigate("Where is config loaded?", repo=plain_ws.root)

    assert report.status == "complete"
    assert report.verification_rate == 1.0
    assert report.findings[0].evidence[0].verified is True
    assert report.stats is not None
    assert report.stats.prompt_tokens == 500
    trace_file = tmp_path / "state" / "runs"
    assert any(trace_file.iterdir())
    md = report.to_markdown()
    assert "✓" in md and "Config loading lives" in md
