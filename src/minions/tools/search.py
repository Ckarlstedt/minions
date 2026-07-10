"""Content search: `git grep` where available, pure-Python scan otherwise."""

from __future__ import annotations

import re
import subprocess

from minions.tools.base import Tool, ToolError, require_int
from minions.tools.globmatch import glob_match, validate_glob
from minions.tools.workspace import Workspace

MAX_RESULTS_CAP = 100
MAX_MATCH_LINE_CHARS = 300


def make_search(workspace: Workspace) -> Tool:
    def search(pattern: str, path: str = ".", glob: str = "", max_results: int = 50) -> str:
        if not pattern:
            raise ToolError("pattern must not be empty")
        limit = min(require_int(max_results, "max_results", minimum=1), MAX_RESULTS_CAP)
        base = workspace.resolve(path or ".")
        if not base.exists():
            raise ToolError(f"No such path: {path}")
        if glob:
            validate_glob(glob)

        matches = (
            _git_grep(workspace, pattern, base)
            if workspace.is_git
            else _python_grep(workspace, pattern, base)
        )
        if glob:
            matches = [m for m in matches if glob_match(glob, m[0])]
        if not matches:
            return "No matches found."

        shown = matches[:limit]
        rendered = [
            f"{rel}:{number}: {text[:MAX_MATCH_LINE_CHARS]}" for rel, number, text in shown
        ]
        header = f"{len(matches)} matches" + (
            f" (showing first {len(shown)})" if len(matches) > len(shown) else ""
        )
        return header + "\n" + "\n".join(rendered)

    return Tool(
        name="search",
        description=(
            "Search file contents with a regular expression (extended/POSIX syntax). "
            "Returns 'path:line: text' matches. Search first, then read_file the region."
        ),
        parameters={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex to search for"},
                "path": {"type": "string", "description": "Restrict to this subdirectory"},
                "glob": {
                    "type": "string",
                    "description": (
                        "Restrict to paths matching this glob, e.g. '**/*.py' or "
                        "'*.{ts,tsx}'. A pattern without '/' matches file names at any depth."
                    ),
                },
                "max_results": {
                    "type": "integer",
                    "description": "Max matches to return (default 50)",
                },
            },
            "required": ["pattern"],
        },
        handler=search,
    )


def _git_grep(workspace: Workspace, pattern: str, base) -> list[tuple[str, int, str]]:
    command = [
        "git",
        "--no-pager",
        "-C",
        str(workspace.root),
        "grep",
        "-I",  # skip binaries
        "-n",
        "-E",
        "--no-color",
        "-e",
        pattern,
    ]
    if base != workspace.root:
        command += ["--", workspace.relative(base)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    if result.returncode == 1:  # git grep: 1 = no matches
        return []
    if result.returncode != 0:
        raise ToolError(f"search failed: {result.stderr.strip()[:300]}")
    matches: list[tuple[str, int, str]] = []
    for raw in result.stdout.splitlines():
        rel, _, rest = raw.partition(":")
        line_number, _, text = rest.partition(":")
        if not line_number.isdigit():
            continue
        matches.append((rel, int(line_number), text))
    return matches


def _python_grep(workspace: Workspace, pattern: str, base) -> list[tuple[str, int, str]]:
    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        raise ToolError(f"invalid regex: {exc}") from None
    matches: list[tuple[str, int, str]] = []
    for file in workspace.iter_files():
        if base != workspace.root and not file.is_relative_to(base):
            continue
        try:
            with file.open("rb") as handle:
                if b"\x00" in handle.read(1024):
                    continue
            text = file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line_number, line in enumerate(text.splitlines(), 1):
            if compiled.search(line):
                matches.append((workspace.relative(file), line_number, line))
    return matches
