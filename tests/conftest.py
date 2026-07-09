from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from minions.tools.workspace import Workspace

APP_PY_V1 = '''\
import json
from pathlib import Path


def load_config(path):
    """Load configuration from a JSON file."""
    text = Path(path).read_text()
    return json.loads(text)
'''

APP_PY_V2 = APP_PY_V1 + '''\


def retry(times):
    """Naive retry helper."""
    return times
'''


def run_git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=Test", "-c", "user.email=test@example.com",
         *args],
        check=True,
        capture_output=True,
        text=True,
    )


def make_tree(root: Path) -> None:
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.py").write_text(APP_PY_V2, encoding="utf-8")
    (root / "README.md").write_text("# Demo\n\nA demo project.\n", encoding="utf-8")


@pytest.fixture
def plain_ws(tmp_path: Path) -> Workspace:
    root = tmp_path / "plain"
    root.mkdir()
    make_tree(root)
    (root / "data.bin").write_bytes(b"\x00\x01\x02")
    (root / ".venv").mkdir()
    (root / ".venv" / "skip.txt").write_text("should never be listed", encoding="utf-8")
    big = "\n".join(f"line {n}" for n in range(1, 301)) + "\n"
    (root / "big.txt").write_text(big, encoding="utf-8")
    return Workspace.discover(root)


@pytest.fixture
def git_ws(tmp_path: Path) -> Workspace:
    root = tmp_path / "repo"
    root.mkdir()
    run_git(root, "init", "-q", "-b", "main")
    (root / "src").mkdir()
    (root / "src" / "app.py").write_text(APP_PY_V1, encoding="utf-8")
    (root / "README.md").write_text("# Demo\n\nA demo project.\n", encoding="utf-8")
    (root / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
    run_git(root, "add", ".")
    run_git(root, "commit", "-qm", "initial commit")
    (root / "src" / "app.py").write_text(APP_PY_V2, encoding="utf-8")
    run_git(root, "add", ".")
    run_git(root, "commit", "-qm", "add retry logic")
    (root / "ignored.txt").write_text("gitignored file", encoding="utf-8")
    return Workspace.discover(root)
