from __future__ import annotations

import pytest

from minions.tools.base import ToolError
from minions.tools.workspace import Workspace


def test_resolve_inside(plain_ws: Workspace) -> None:
    resolved = plain_ws.resolve("src/app.py")
    assert resolved == plain_ws.root / "src" / "app.py"


def test_resolve_root_itself(plain_ws: Workspace) -> None:
    assert plain_ws.resolve(".") == plain_ws.root


def test_resolve_rejects_dotdot_escape(plain_ws: Workspace) -> None:
    with pytest.raises(ToolError, match="outside the workspace"):
        plain_ws.resolve("../outside.txt")


def test_resolve_rejects_absolute_outside(plain_ws: Workspace) -> None:
    with pytest.raises(ToolError, match="outside the workspace"):
        plain_ws.resolve("/etc/passwd")


def test_resolve_rejects_symlink_escape(plain_ws: Workspace, tmp_path) -> None:
    secret = tmp_path / "secret.txt"
    secret.write_text("secret", encoding="utf-8")
    (plain_ws.root / "link.txt").symlink_to(secret)
    with pytest.raises(ToolError, match="outside the workspace"):
        plain_ws.resolve("link.txt")


def test_is_git(plain_ws: Workspace, git_ws: Workspace) -> None:
    assert not plain_ws.is_git
    assert git_ws.is_git


def test_iter_files_skips_junk_dirs(plain_ws: Workspace) -> None:
    rels = [plain_ws.relative(f) for f in plain_ws.iter_files()]
    assert "src/app.py" in rels
    assert not any(rel.startswith(".venv") for rel in rels)


def test_iter_files_respects_gitignore(git_ws: Workspace) -> None:
    rels = [git_ws.relative(f) for f in git_ws.iter_files()]
    assert "src/app.py" in rels
    assert "ignored.txt" not in rels


def test_discover_rejects_missing_dir(tmp_path) -> None:
    with pytest.raises(NotADirectoryError):
        Workspace.discover(tmp_path / "nope")
