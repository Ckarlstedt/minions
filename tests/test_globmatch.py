from __future__ import annotations

import pytest

from minions.tools.base import ToolError
from minions.tools.globmatch import glob_match, validate_glob


def test_star_stays_within_segment() -> None:
    assert glob_match("src/*.py", "src/app.py")
    assert not glob_match("src/*.py", "src/sub/app.py")


def test_double_star_spans_segments() -> None:
    assert glob_match("src/**/*.py", "src/a/b/c.py")
    assert glob_match("src/**", "src/a/b/c.py")


def test_double_star_slash_matches_zero_directories() -> None:
    assert glob_match("**/*.ts", "index.ts")
    assert glob_match("**/*.ts", "lib/app.ts")


def test_braces_expand() -> None:
    assert glob_match("**/*.{ts,js,py}", "lib/applications.ts")
    assert glob_match("**/*.{ts,js,py}", "tools/build.py")
    assert not glob_match("**/*.{ts,js}", "tools/build.py")


def test_nested_braces() -> None:
    assert glob_match("*.{py{,i},md}", "src/app.pyi")
    assert glob_match("*.{py{,i},md}", "src/app.py")
    assert not glob_match("*.{py{,i},md}", "src/app.pyc")


def test_pattern_without_slash_matches_at_any_depth() -> None:
    assert glob_match("*.py", "deep/nested/app.py")
    assert glob_match("*.py", "app.py")
    assert glob_match("conftest.py", "tests/conftest.py")
    assert not glob_match("*.py", "app.md")


def test_question_mark_does_not_cross_separator() -> None:
    assert glob_match("app.p?", "app.py")
    assert not glob_match("a?c", "a/c")


def test_character_class() -> None:
    assert glob_match("file[0-9].txt", "file1.txt")
    assert not glob_match("file[!0-9].txt", "file1.txt")
    assert glob_match("file[!0-9].txt", "fileA.txt")


def test_trailing_slash_means_everything_under() -> None:
    assert glob_match("src/", "src/a/b.py")
    assert not glob_match("src/", "lib/a.py")


def test_regex_metacharacters_are_literal() -> None:
    assert glob_match("a+b.txt", "a+b.txt")
    assert not glob_match("a+b.txt", "aab.txt")


def test_invalid_globs_raise_tool_error() -> None:
    with pytest.raises(ToolError, match="unterminated '\\['"):
        validate_glob("broken[")
    with pytest.raises(ToolError, match="unterminated '\\{'"):
        validate_glob("broken{a,b")
