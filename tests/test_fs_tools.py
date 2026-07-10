from __future__ import annotations

from pathlib import Path

from minions.tools.base import ToolRegistry
from minions.tools.fs import MAX_LIST_RESULTS, MAX_READ_LINES, make_list_files, make_read_file
from minions.tools.workspace import Workspace


def registry_for(ws: Workspace) -> ToolRegistry:
    return ToolRegistry([make_list_files(ws), make_read_file(ws)], max_output_chars=100_000)


def test_read_file_full(plain_ws: Workspace) -> None:
    out = registry_for(plain_ws).run("read_file", {"path": "README.md"})
    assert out.startswith("README.md lines 1-3 of 3")
    assert "1| # Demo" in out


def test_read_file_range(plain_ws: Workspace) -> None:
    args = {"path": "big.txt", "start_line": 5, "end_line": 7}
    out = registry_for(plain_ws).run("read_file", args)
    assert "5| line 5" in out and "7| line 7" in out and "8|" not in out


def test_read_file_caps_lines(plain_ws: Workspace) -> None:
    out = registry_for(plain_ws).run("read_file", {"path": "big.txt"})
    assert f"lines 1-{MAX_READ_LINES} of 300" in out
    assert "capped" in out


def test_read_file_binary_rejected(plain_ws: Workspace) -> None:
    out = registry_for(plain_ws).run("read_file", {"path": "data.bin"})
    assert out.startswith("Error:") and "binary" in out


def test_read_file_missing(plain_ws: Workspace) -> None:
    out = registry_for(plain_ws).run("read_file", {"path": "nope.py"})
    assert out.startswith("Error: No such file")


def test_read_file_start_past_end(plain_ws: Workspace) -> None:
    out = registry_for(plain_ws).run("read_file", {"path": "README.md", "start_line": 99})
    assert out.startswith("Error:") and "past the end" in out


def test_read_file_directory(plain_ws: Workspace) -> None:
    out = registry_for(plain_ws).run("read_file", {"path": "src"})
    assert out.startswith("Error:") and "directory" in out


def test_read_file_escape_rejected(plain_ws: Workspace) -> None:
    out = registry_for(plain_ws).run("read_file", {"path": "../../etc/passwd"})
    assert out.startswith("Error:") and "outside the workspace" in out


def test_list_files_all(plain_ws: Workspace) -> None:
    out = registry_for(plain_ws).run("list_files", {})
    assert "src/app.py" in out and "README.md" in out
    assert ".venv" not in out


def test_list_files_glob(plain_ws: Workspace) -> None:
    out = registry_for(plain_ws).run("list_files", {"glob": "**/*.py"})
    assert "src/app.py" in out and "README.md" not in out


def test_list_files_subdir(plain_ws: Workspace) -> None:
    out = registry_for(plain_ws).run("list_files", {"path": "src"})
    assert "src/app.py" in out and "README.md" not in out


def test_list_files_missing_path(plain_ws: Workspace) -> None:
    out = registry_for(plain_ws).run("list_files", {"path": "nope"})
    assert out.startswith("Error: No such path")


def test_list_files_brace_glob(plain_ws: Workspace) -> None:
    out = registry_for(plain_ws).run("list_files", {"glob": "*.{py,md}"})
    assert "src/app.py" in out and "README.md" in out
    assert "big.txt" not in out


def test_list_files_invalid_glob_is_reported(plain_ws: Workspace) -> None:
    out = registry_for(plain_ws).run("list_files", {"glob": "broken{a,b"})
    assert out.startswith("Error:") and "glob" in out


def test_list_files_overflow_returns_tree(tmp_path: Path) -> None:
    root = tmp_path / "many"
    (root / "pile").mkdir(parents=True)
    for n in range(MAX_LIST_RESULTS + 1):
        (root / "pile" / f"f{n:03}.txt").write_text("x", encoding="utf-8")
    ws = Workspace.discover(root)
    out = ToolRegistry([make_list_files(ws)], max_output_chars=100_000).run("list_files", {})
    assert "structure overview" in out
    assert f"pile/ ({MAX_LIST_RESULTS + 1} files)" in out
    # The overview is entry-capped, not a full dump of all 301 paths.
    assert "f300.txt" not in out
    assert "more entries" in out
    assert len(out.splitlines()) < 90


def test_unknown_tool(plain_ws: Workspace) -> None:
    out = registry_for(plain_ws).run("delete_everything", {})
    assert out.startswith("Error: unknown tool")


def test_bad_argument_name(plain_ws: Workspace) -> None:
    out = registry_for(plain_ws).run("read_file", {"file": "README.md"})
    assert out.startswith("Error: invalid arguments")


def test_output_truncation(plain_ws: Workspace) -> None:
    registry = ToolRegistry([make_read_file(plain_ws)], max_output_chars=50)
    out = registry.run("read_file", {"path": "big.txt"})
    assert "[output truncated" in out
