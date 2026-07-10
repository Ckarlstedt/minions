from __future__ import annotations

from pathlib import Path

from minions.agent.prompts import orientation_docs, orientation_listing, task_message
from minions.tools.workspace import Workspace


def test_orientation_listing_is_a_tree(plain_ws: Workspace) -> None:
    out = orientation_listing(plain_ws)
    assert "src/ (1 file)" in out
    assert "README.md" in out
    assert ".venv" not in out


def test_task_message_includes_readme_head(plain_ws: Workspace) -> None:
    msg = task_message("Where is X?", plain_ws, max_steps=8)
    assert "--- README.md ---" in msg
    assert "# Demo" in msg


def test_orientation_docs_absent(tmp_path: Path) -> None:
    root = tmp_path / "bare"
    root.mkdir()
    (root / "code.py").write_text("x = 1\n", encoding="utf-8")
    ws = Workspace.discover(root)
    assert orientation_docs(ws) == ""
    assert "Orientation docs" not in task_message("q", ws, 8)


def test_orientation_docs_are_line_capped(tmp_path: Path) -> None:
    root = tmp_path / "big"
    root.mkdir()
    (root / "README.md").write_text(
        "\n".join(f"line {n}" for n in range(500)), encoding="utf-8"
    )
    ws = Workspace.discover(root)
    docs = orientation_docs(ws)
    assert "line 0" in docs
    assert "line 499" not in docs
    assert "read_file for the rest" in docs


def test_orientation_docs_total_budget_spans_files(tmp_path: Path) -> None:
    root = tmp_path / "two"
    root.mkdir()
    (root / "README.md").write_text("R" * 5000, encoding="utf-8")
    (root / "AGENTS.md").write_text("agents doc\n", encoding="utf-8")
    ws = Workspace.discover(root)
    docs = orientation_docs(ws)
    assert len(docs) < 5000  # README head alone exceeds the budget and is cut
    assert "AGENTS.md" not in docs  # nothing left in the budget for the second doc
