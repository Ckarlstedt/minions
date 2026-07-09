from __future__ import annotations

from minions.tools.base import ToolRegistry
from minions.tools.git import make_git_blame, make_git_diff, make_git_log
from minions.tools.workspace import Workspace


def registry_for(ws: Workspace) -> ToolRegistry:
    return ToolRegistry(
        [make_git_log(ws), make_git_diff(ws), make_git_blame(ws)], max_output_chars=100_000
    )


def test_git_log(git_ws: Workspace) -> None:
    out = registry_for(git_ws).run("git_log", {})
    assert "add retry logic" in out and "initial commit" in out


def test_git_log_grep(git_ws: Workspace) -> None:
    out = registry_for(git_ws).run("git_log", {"grep": "retry"})
    assert "add retry logic" in out and "initial commit" not in out


def test_git_log_path(git_ws: Workspace) -> None:
    out = registry_for(git_ws).run("git_log", {"path": "README.md"})
    assert "initial commit" in out and "add retry logic" not in out


def test_git_diff(git_ws: Workspace) -> None:
    out = registry_for(git_ws).run("git_diff", {"base": "HEAD~1"})
    assert "def retry" in out and out.lstrip().startswith("diff --git")


def test_git_diff_stat_only(git_ws: Workspace) -> None:
    out = registry_for(git_ws).run("git_diff", {"base": "HEAD~1", "stat_only": True})
    assert "src/app.py" in out and "def retry" not in out


def test_git_blame(git_ws: Workspace) -> None:
    args = {"path": "src/app.py", "start_line": 1, "end_line": 3}
    out = registry_for(git_ws).run("git_blame", args)
    assert "Test" in out and "import json" in out


def test_ref_injection_rejected(git_ws: Workspace) -> None:
    out = registry_for(git_ws).run("git_diff", {"base": "--output=/tmp/pwned"})
    assert out.startswith("Error:") and "invalid git ref" in out


def test_path_flag_rejected(git_ws: Workspace) -> None:
    out = registry_for(git_ws).run("git_log", {"path": "-oops"})
    assert out.startswith("Error:") and "invalid path" in out


def test_path_escape_rejected(git_ws: Workspace) -> None:
    out = registry_for(git_ws).run("git_blame", {"path": "../x", "start_line": 1, "end_line": 2})
    assert out.startswith("Error:") and "outside the workspace" in out


def test_non_git_workspace(plain_ws: Workspace) -> None:
    out = registry_for(plain_ws).run("git_log", {})
    assert out.startswith("Error:") and "not a git repository" in out
