from __future__ import annotations

from minions.tools.tree import render_tree

PATHS = [
    "README.md",
    "src/app.py",
    "src/engine/core.py",
    "src/engine/util.py",
    "src/engine/deep/thing.py",
    "assets/a.png",
    "assets/b.png",
]


def test_dirs_carry_recursive_counts() -> None:
    out = render_tree(PATHS, max_depth=2, max_entries=60)
    assert "src/ (4 files)" in out
    assert "assets/ (2 files)" in out
    assert "README.md" in out


def test_collapses_below_max_depth() -> None:
    out = render_tree(PATHS, max_depth=2, max_entries=60)
    assert "engine/ (3 files)" in out
    assert "core.py" not in out
    assert "  app.py" in out


def test_depth_one_collapses_top_level_dirs() -> None:
    out = render_tree(PATHS, max_depth=1, max_entries=60)
    assert "src/ (4 files)" in out
    assert "engine" not in out


def test_singular_file_count() -> None:
    out = render_tree(["lonely/one.txt"], max_depth=2, max_entries=60)
    assert "lonely/ (1 file)" in out


def test_entry_cap_appends_note() -> None:
    paths = [f"dir{n:02}/file.txt" for n in range(50)]
    out = render_tree(paths, max_depth=2, max_entries=10)
    lines = out.splitlines()
    assert len(lines) == 11
    assert "more entries" in lines[-1]


def test_empty_input() -> None:
    assert render_tree([], max_depth=2, max_entries=10) == "(no files)"
