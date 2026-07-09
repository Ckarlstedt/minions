"""Read-only git tools: log, diff, blame.

Safety model (ADR-005): git is invoked with a fixed argv per tool (never via a
shell), refs are validated against a conservative pattern, any argument that
begins with '-' is rejected, and paths are placed after `--` so nothing a
model supplies can become a flag.
"""

from __future__ import annotations

import re
import subprocess

from minions.tools.base import Tool, ToolError, require_int
from minions.tools.workspace import Workspace

MAX_LOG_COUNT = 50
MAX_BLAME_LINES = 100

_REF_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_./~^@{}-]*")


def _validate_ref(ref: str) -> str:
    if not ref or ref.startswith("-") or not _REF_PATTERN.fullmatch(ref):
        raise ToolError(f"invalid git ref: {ref!r}")
    return ref


def _validate_path(workspace: Workspace, path: str) -> str:
    if path.startswith("-"):
        raise ToolError(f"invalid path: {path!r}")
    return workspace.relative(workspace.resolve(path))


def _run_git(workspace: Workspace, *args: str) -> str:
    if not workspace.is_git:
        raise ToolError("this workspace is not a git repository")
    command = ["git", "--no-pager", "-C", str(workspace.root), *args]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        raise ToolError("git command timed out") from None
    if result.returncode != 0:
        raise ToolError(f"git failed: {result.stderr.strip()[:300]}")
    return result.stdout


def make_git_log(workspace: Workspace) -> Tool:
    def git_log(path: str = "", max_count: int = 20, grep: str = "") -> str:
        count = min(require_int(max_count, "max_count", minimum=1), MAX_LOG_COUNT)
        args = [
            "log",
            "--no-decorate",
            "--date=short",
            "--pretty=format:%h %ad %an: %s",
            f"-n{count}",
        ]
        if grep:
            args.append(f"--grep={grep}")
        if path:
            args += ["--", _validate_path(workspace, path)]
        output = _run_git(workspace, *args)
        return output.strip() or "No commits found."

    return Tool(
        name="git_log",
        description=(
            "Show recent commits (hash, date, author, subject), optionally limited to a "
            "path and/or filtered by a --grep pattern on commit messages."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Only commits touching this path"},
                "max_count": {"type": "integer", "description": "How many commits (default 20)"},
                "grep": {"type": "string", "description": "Filter commit messages by this pattern"},
            },
        },
        handler=git_log,
    )


def make_git_diff(workspace: Workspace) -> Tool:
    def git_diff(base: str, head: str = "HEAD", path: str = "", stat_only: bool = False) -> str:
        args = ["diff"]
        if stat_only:
            args.append("--stat")
        args.append(f"{_validate_ref(base)}..{_validate_ref(head)}")
        if path:
            args += ["--", _validate_path(workspace, path)]
        output = _run_git(workspace, *args)
        return output.strip() or "No differences."

    return Tool(
        name="git_diff",
        description=(
            "Show the diff between two refs (commits, branches, tags). "
            "Use stat_only=true first for an overview when the diff may be large."
        ),
        parameters={
            "type": "object",
            "properties": {
                "base": {"type": "string", "description": "Base ref, e.g. 'main' or a commit hash"},
                "head": {"type": "string", "description": "Head ref (default HEAD)"},
                "path": {"type": "string", "description": "Restrict the diff to this path"},
                "stat_only": {"type": "boolean", "description": "Only show per-file change counts"},
            },
            "required": ["base"],
        },
        handler=git_diff,
    )


def make_git_blame(workspace: Workspace) -> Tool:
    def git_blame(path: str, start_line: int, end_line: int) -> str:
        start = require_int(start_line, "start_line", minimum=1)
        end = require_int(end_line, "end_line", minimum=start)
        end = min(end, start + MAX_BLAME_LINES - 1)
        rel = _validate_path(workspace, path)
        output = _run_git(
            workspace, "blame", "--date=short", "-L", f"{start},{end}", "--", rel
        )
        return output.strip() or "No blame output."

    return Tool(
        name="git_blame",
        description="Show who last changed each line in a range of a file, with commit and date.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Repository-relative file path"},
                "start_line": {"type": "integer", "description": "First line (1-based)"},
                "end_line": {"type": "integer", "description": "Last line (inclusive)"},
            },
            "required": ["path", "start_line", "end_line"],
        },
        handler=git_blame,
    )
