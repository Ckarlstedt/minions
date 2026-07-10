"""Gitignore-style glob matching for model-supplied patterns.

Models write ripgrep/gitignore-style globs (`**/*.{ts,js}`, `*.py`).
Python's fnmatch quietly means something else: `{a,b}` is literal, `*`
crosses `/`, and `**/` demands at least one directory — so a reasonable
pattern returns a wrong-but-plausible "No matches found" that the model
cannot distinguish from a true absence (ADR-008). This module implements
the semantics the model expects:

- `*` matches within one path segment (never `/`)
- `?` matches one character except `/`
- `**` spans segments; `**/` also matches zero directories
- `{a,b}` alternation, may nest
- `[...]` character classes (`!` or `^` negates)
- a pattern without `/` matches the file name at any depth
- a trailing `/` means everything under that directory

Malformed patterns raise ToolError so the model sees an explicit error
instead of an empty result.
"""

from __future__ import annotations

import re
from functools import lru_cache

from minions.tools.base import ToolError


def glob_match(pattern: str, path: str) -> bool:
    """True if the repo-relative `path` matches the gitignore-style `pattern`."""
    return _compile(pattern).match(path) is not None


def validate_glob(pattern: str) -> None:
    """Raise ToolError for a malformed `pattern` before any scanning starts."""
    _compile(pattern)


@lru_cache(maxsize=256)
def _compile(pattern: str) -> re.Pattern[str]:
    effective = pattern + "**" if pattern.endswith("/") else pattern
    body = _translate(effective, pattern)
    if "/" not in effective:
        body = r"(?:[^/]+/)*" + body
    try:
        return re.compile(body + r"\Z")
    except re.error as exc:
        raise ToolError(f"invalid glob {pattern!r}: {exc}") from None


def _translate(pattern: str, original: str) -> str:
    parts: list[str] = []
    i = 0
    while i < len(pattern):
        char = pattern[i]
        if char == "*":
            if pattern[i : i + 3] == "**/":
                parts.append(r"(?:[^/]+/)*")
                i += 3
            elif pattern[i : i + 2] == "**":
                parts.append(r".*")
                i += 2
            else:
                parts.append(r"[^/]*")
                i += 1
        elif char == "?":
            parts.append(r"[^/]")
            i += 1
        elif char == "[":
            end = _class_end(pattern, i, original)
            inner = pattern[i + 1 : end]
            if inner.startswith("!"):
                inner = "^" + inner[1:]
            parts.append(f"[{inner}]")
            i = end + 1
        elif char == "{":
            end = _brace_end(pattern, i, original)
            alternatives = _split_alternatives(pattern[i + 1 : end])
            parts.append("(?:" + "|".join(_translate(a, original) for a in alternatives) + ")")
            i = end + 1
        else:
            parts.append(re.escape(char))
            i += 1
    return "".join(parts)


def _class_end(pattern: str, start: int, original: str) -> int:
    i = start + 1
    if i < len(pattern) and pattern[i] in "!^":
        i += 1
    if i < len(pattern) and pattern[i] == "]":
        i += 1  # a leading ']' is a literal member of the class
    while i < len(pattern) and pattern[i] != "]":
        i += 1
    if i >= len(pattern):
        raise ToolError(f"invalid glob {original!r}: unterminated '[' character class")
    return i


def _brace_end(pattern: str, start: int, original: str) -> int:
    depth = 0
    for i in range(start, len(pattern)):
        if pattern[i] == "{":
            depth += 1
        elif pattern[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    raise ToolError(f"invalid glob {original!r}: unterminated '{{'")


def _split_alternatives(body: str) -> list[str]:
    alternatives: list[str] = []
    depth = 0
    current = ""
    for char in body:
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        if char == "," and depth == 0:
            alternatives.append(current)
            current = ""
        else:
            current += char
    alternatives.append(current)
    return alternatives
