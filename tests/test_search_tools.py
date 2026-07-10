from __future__ import annotations

from minions.tools.base import ToolRegistry
from minions.tools.search import make_search
from minions.tools.workspace import Workspace


def run_search(ws: Workspace, args: dict) -> str:
    registry = ToolRegistry([make_search(ws)], max_output_chars=100_000)
    return registry.run("search", args)


def test_git_grep_finds_match(git_ws: Workspace) -> None:
    out = run_search(git_ws, {"pattern": "load_config"})
    assert "src/app.py:5:" in out and "def load_config" in out


def test_plain_grep_finds_match(plain_ws: Workspace) -> None:
    out = run_search(plain_ws, {"pattern": "load_config"})
    assert "src/app.py:5:" in out


def test_no_matches(git_ws: Workspace) -> None:
    assert run_search(git_ws, {"pattern": "zebra_unicorn"}) == "No matches found."


def test_glob_filter(plain_ws: Workspace) -> None:
    out = run_search(plain_ws, {"pattern": "Demo", "glob": "*.py"})
    assert out == "No matches found."


def test_glob_braces(git_ws: Workspace) -> None:
    out = run_search(git_ws, {"pattern": "Demo", "glob": "*.{md,rst}"})
    assert "README.md" in out


def test_glob_matches_root_level_files(git_ws: Workspace) -> None:
    out = run_search(git_ws, {"pattern": "Demo", "glob": "**/*.md"})
    assert "README.md" in out  # '**/' must also match zero directories


def test_invalid_glob_is_reported(plain_ws: Workspace) -> None:
    out = run_search(plain_ws, {"pattern": "Demo", "glob": "*.{md"})
    assert out.startswith("Error:") and "glob" in out


def test_path_restriction(plain_ws: Workspace) -> None:
    out = run_search(plain_ws, {"pattern": "line", "path": "src"})
    assert "big.txt" not in out


def test_max_results(plain_ws: Workspace) -> None:
    out = run_search(plain_ws, {"pattern": "line", "max_results": 3})
    assert "showing first 3" in out


def test_invalid_regex_python(plain_ws: Workspace) -> None:
    out = run_search(plain_ws, {"pattern": "[unclosed"})
    assert out.startswith("Error:") and "invalid regex" in out


def test_invalid_regex_git(git_ws: Workspace) -> None:
    out = run_search(git_ws, {"pattern": "[unclosed"})
    assert out.startswith("Error:")


def test_empty_pattern(plain_ws: Workspace) -> None:
    out = run_search(plain_ws, {"pattern": ""})
    assert out.startswith("Error:")


def test_binary_files_skipped(plain_ws: Workspace) -> None:
    out = run_search(plain_ws, {"pattern": "."})
    assert "data.bin" not in out
