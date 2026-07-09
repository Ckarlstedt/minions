"""Workspace: the directory a minion may look at, and nothing outside it.

Every filesystem access in the tool layer funnels through Workspace.resolve,
which rejects any path escaping the root — including via `..` and via
symlinks pointing outside (paths are fully resolved before the containment
check). This is the enforcement point for ADR-005.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from minions.tools.base import ToolError

# Directories that are never interesting to an investigation and often huge.
SKIP_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        "dist",
        "build",
        ".DS_Store",
    }
)


@dataclass(frozen=True)
class Workspace:
    root: Path  # absolute, fully resolved

    @classmethod
    def discover(cls, path: Path | str) -> Workspace:
        root = Path(path).resolve()
        if not root.is_dir():
            raise NotADirectoryError(f"Workspace root is not a directory: {root}")
        return cls(root=root)

    @cached_property
    def is_git(self) -> bool:
        result = subprocess.run(
            ["git", "-C", str(self.root), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"

    def resolve(self, path: str) -> Path:
        """Resolve a model-supplied path; raise ToolError if it escapes the root."""
        candidate = Path(path)
        absolute = candidate if candidate.is_absolute() else self.root / candidate
        resolved = absolute.resolve()
        if resolved != self.root and self.root not in resolved.parents:
            raise ToolError(
                f"Path {path!r} is outside the workspace; use paths relative to the repo root."
            )
        return resolved

    def relative(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix() or "."

    def iter_files(self) -> list[Path]:
        """All investigable files, repo-relative order. Respects .gitignore in git repos."""
        if self.is_git:
            result = subprocess.run(
                [
                    "git",
                    "-C",
                    str(self.root),
                    "ls-files",
                    "--cached",
                    "--others",
                    "--exclude-standard",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return [
                    self.root / line
                    for line in result.stdout.splitlines()
                    if line and (self.root / line).is_file()
                ]
        return self._walk()

    def _walk(self) -> list[Path]:
        found: list[Path] = []
        stack = [self.root]
        while stack:
            current = stack.pop()
            try:
                entries = sorted(current.iterdir())
            except OSError:
                continue
            for entry in entries:
                if entry.name in SKIP_DIRS:
                    continue
                if entry.is_symlink():
                    continue  # symlinks may point outside the workspace
                if entry.is_dir():
                    stack.append(entry)
                elif entry.is_file():
                    found.append(entry)
        return found
