"""Assemble the tool registry for a workspace.

The roster is deliberately small: fewer, sharper tools measurably improve
tool selection in small models. Git tools are only offered when the
workspace actually is a git repository, so the model never sees tools that
cannot work.
"""

from __future__ import annotations

from minions.tools.base import Tool, ToolRegistry
from minions.tools.fs import make_list_files, make_read_file
from minions.tools.git import make_git_blame, make_git_diff, make_git_log
from minions.tools.search import make_search
from minions.tools.workspace import Workspace


def build_registry(workspace: Workspace, max_output_chars: int) -> ToolRegistry:
    tools: list[Tool] = [
        make_list_files(workspace),
        make_read_file(workspace),
        make_search(workspace),
    ]
    if workspace.is_git:
        tools += [
            make_git_log(workspace),
            make_git_diff(workspace),
            make_git_blame(workspace),
        ]
    return ToolRegistry(tools, max_output_chars=max_output_chars)
