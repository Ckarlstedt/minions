"""Compact tree rendering of file listings.

A flat several-hundred-path dump costs thousands of context tokens and
buries the structure the model actually needs; a depth-limited tree with
per-directory file counts carries the same orientation in a fraction of
the space (ADR-008).
"""

from __future__ import annotations


def render_tree(paths: list[str], *, max_depth: int = 2, max_entries: int = 60) -> str:
    """Render repo-relative `paths` as an indented tree.

    Directories at `max_depth` are collapsed into a single counted line;
    output is capped at `max_entries` lines.
    """
    root = _Node()
    for path in paths:
        parts = path.split("/")
        node = root
        for part in parts[:-1]:
            node = node.dirs.setdefault(part, _Node())
        node.files.append(parts[-1])

    lines: list[str] = []
    _render(root, 0, max_depth, lines)
    if len(lines) > max_entries:
        omitted = len(lines) - max_entries
        lines = lines[:max_entries]
        lines.append(f"…({omitted} more entries — use list_files with a path or glob)")
    return "\n".join(lines) if lines else "(no files)"


class _Node:
    __slots__ = ("dirs", "files")

    def __init__(self) -> None:
        self.dirs: dict[str, _Node] = {}
        self.files: list[str] = []


def _count(node: _Node) -> int:
    return len(node.files) + sum(_count(child) for child in node.dirs.values())


def _label(count: int) -> str:
    return "1 file" if count == 1 else f"{count} files"


def _render(node: _Node, depth: int, max_depth: int, lines: list[str]) -> None:
    indent = "  " * depth
    for name in sorted(node.dirs):
        child = node.dirs[name]
        lines.append(f"{indent}{name}/ ({_label(_count(child))})")
        if depth + 1 < max_depth:
            _render(child, depth + 1, max_depth, lines)
    for name in sorted(node.files):
        lines.append(f"{indent}{name}")
