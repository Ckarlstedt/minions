from __future__ import annotations

from pathlib import Path

import pytest

from minions.cli import main
from minions.integrate import (
    BEGIN_MARK,
    END_MARK,
    INSTRUCTIONS_BLOCK,
    write_agent_instructions,
)


def test_creates_file_when_missing(tmp_path: Path) -> None:
    assert write_agent_instructions(tmp_path) == "created"
    text = (tmp_path / "AGENTS.md").read_text()
    assert text.startswith(BEGIN_MARK)
    assert "minions investigate" in text


def test_appends_without_touching_existing_content(tmp_path: Path) -> None:
    target = tmp_path / "AGENTS.md"
    original = "# My project\n\nHand-written agent notes.\n"
    target.write_text(original)
    assert write_agent_instructions(tmp_path) == "added"
    text = target.read_text()
    assert text.startswith(original)
    assert text.count(BEGIN_MARK) == 1


def test_rerun_is_idempotent(tmp_path: Path) -> None:
    write_agent_instructions(tmp_path)
    assert write_agent_instructions(tmp_path) == "unchanged"
    assert (tmp_path / "AGENTS.md").read_text().count(BEGIN_MARK) == 1


def test_stale_block_is_updated_in_place(tmp_path: Path) -> None:
    target = tmp_path / "AGENTS.md"
    stale = f"# Intro\n\n{BEGIN_MARK}\nold instructions\n{END_MARK}\n\n# Outro\n"
    target.write_text(stale)
    assert write_agent_instructions(tmp_path) == "updated"
    text = target.read_text()
    assert "old instructions" not in text
    assert INSTRUCTIONS_BLOCK in text
    assert text.startswith("# Intro") and text.rstrip().endswith("# Outro")


def test_custom_file_name(tmp_path: Path) -> None:
    write_agent_instructions(tmp_path, "CLAUDE.md")
    assert (tmp_path / "CLAUDE.md").exists()
    assert not (tmp_path / "AGENTS.md").exists()


def test_missing_repo_rejected(tmp_path: Path) -> None:
    with pytest.raises(NotADirectoryError):
        write_agent_instructions(tmp_path / "nope")


def test_cli_init(tmp_path: Path, capsys) -> None:
    assert main(["init", "--repo", str(tmp_path)]) == 0
    assert "created" in capsys.readouterr().out
    assert main(["init", "--repo", str(tmp_path)]) == 0
    assert "up to date" in capsys.readouterr().out


def test_cli_init_missing_repo(tmp_path: Path, capsys) -> None:
    assert main(["init", "--repo", str(tmp_path / "nope")]) == 1
    assert "error:" in capsys.readouterr().err
