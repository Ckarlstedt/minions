"""Read-only filesystem tools: list_files and read_file."""

from __future__ import annotations

import fnmatch

from minions.tools.base import Tool, ToolError, require_int
from minions.tools.workspace import Workspace

MAX_LIST_RESULTS = 300
MAX_READ_LINES = 250
MAX_LINE_CHARS = 400


def make_list_files(workspace: Workspace) -> Tool:
    def list_files(path: str = ".", glob: str = "") -> str:
        base = workspace.resolve(path or ".")
        if not base.exists():
            raise ToolError(f"No such path: {path}")
        rels = []
        for file in workspace.iter_files():
            rel = workspace.relative(file)
            if base != workspace.root and not file.is_relative_to(base):
                continue
            if glob and not fnmatch.fnmatch(rel, glob):
                continue
            rels.append(rel)
        rels.sort()
        if not rels:
            return "No files found."
        shown = rels[:MAX_LIST_RESULTS]
        header = f"{len(rels)} files"
        if len(rels) > len(shown):
            header += f" (showing first {len(shown)})"
        return header + "\n" + "\n".join(shown)

    return Tool(
        name="list_files",
        description=(
            "List files in the repository (recursively), optionally under a subdirectory "
            "and/or filtered by a glob pattern such as 'src/**/*.py'."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Subdirectory to list (default: repo root)",
                },
                "glob": {"type": "string", "description": "Optional glob filter, e.g. '**/*.toml'"},
            },
        },
        handler=list_files,
    )


def read_file_text(workspace: Workspace, path: str) -> list[str]:
    """Shared reader used by tools and the citation verifier. Returns file lines."""
    resolved = workspace.resolve(path)
    if not resolved.exists():
        raise ToolError(f"No such file: {path}")
    if resolved.is_dir():
        raise ToolError(f"{path} is a directory; use list_files")
    with resolved.open("rb") as handle:
        head = handle.read(8192)
    if b"\x00" in head:
        raise ToolError(f"{path} is a binary file")
    return resolved.read_text(encoding="utf-8", errors="replace").splitlines()


def make_read_file(workspace: Workspace) -> Tool:
    def read_file(path: str, start_line: int = 1, end_line: int = 0) -> str:
        start = require_int(start_line, "start_line", minimum=1)
        end = require_int(end_line, "end_line") if end_line else 0
        lines = read_file_text(workspace, path)
        total = len(lines)
        if total == 0:
            return f"{path} is empty."
        if end <= 0 or end > total:
            end = total
        if start > total:
            raise ToolError(f"start_line {start} is past the end of {path} ({total} lines)")
        end = min(end, start + MAX_READ_LINES - 1)
        selected = lines[start - 1 : end]
        rendered = [
            f"{number}| {line[:MAX_LINE_CHARS]}{'…' if len(line) > MAX_LINE_CHARS else ''}"
            for number, line in enumerate(selected, start)
        ]
        header = f"{path} lines {start}-{end} of {total}"
        if end < total and end == start + MAX_READ_LINES - 1:
            header += f" (capped at {MAX_READ_LINES} lines per call)"
        return header + "\n" + "\n".join(rendered)

    return Tool(
        name="read_file",
        description=(
            "Read a file (or a line range of it) with line numbers. "
            f"At most {MAX_READ_LINES} lines per call — read regions, not whole large files."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Repository-relative file path"},
                "start_line": {"type": "integer", "description": "First line to read (1-based)"},
                "end_line": {"type": "integer", "description": "Last line to read (inclusive)"},
            },
            "required": ["path"],
        },
        handler=read_file,
    )
