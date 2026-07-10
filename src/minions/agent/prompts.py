"""Prompt construction for the minion.

Written for a small model: short imperative rules, budget stated explicitly,
and orientation material (a structure tree plus the head of the repo's own
README/AGENTS docs) so the first tool calls are not spent discovering that
the repo exists. Local prompt tokens are cheap; minion steps are the scarce
resource.
"""

from __future__ import annotations

from minions.tools.base import ToolError
from minions.tools.fs import read_file_text
from minions.tools.tree import render_tree
from minions.tools.workspace import Workspace

SYSTEM_PROMPT = """\
You are a repository investigation agent. Answer the investigator's question \
about a codebase using the read-only tools, then deliver your report by \
calling the submit_report tool.

Rules:
- Only state what you saw in tool output. Never invent file contents, paths, or line numbers.
- Every finding must cite evidence: file path, line range, and a VERBATIM excerpt copied \
exactly from the file text (without the line-number prefixes shown by read_file). \
Citations are machine-checked against the real files; fabricated ones are flagged.
- Work efficiently: search first, then read only the matching regions. You have a limited \
tool-call budget, stated in the task message.
- If part of the question cannot be answered from this repository, list it under \
"unanswered" instead of guessing.
- Finish by calling submit_report exactly once. Never write the report as plain chat text.

submit_report arguments must follow exactly this shape:
{"summary": "<2-5 sentence answer>",
 "findings": [{"claim": "<one factual statement>", "confidence": "high|medium|low",
 "file": "<repo-relative path>", "start_line": <int>, "end_line": <int>,
 "excerpt": "<verbatim text copied from the file>"}],
 "unanswered": ["<anything you could not answer>"]}
"""

_ORIENTATION_MAX_ENTRIES = 60
_ORIENTATION_MAX_DEPTH = 2
_DOC_NAMES = ("README.md", "AGENTS.md", "CLAUDE.md")
_DOC_MAX_LINES = 60  # per document
_DOC_MAX_CHARS = 4000  # across all documents; the head is re-sent on every loop step


def orientation_listing(workspace: Workspace) -> str:
    """A compact structure tree to ground the model before its first tool call."""
    rels = sorted(workspace.relative(file) for file in workspace.iter_files())
    if not rels:
        return "(empty workspace)"
    return render_tree(
        rels, max_depth=_ORIENTATION_MAX_DEPTH, max_entries=_ORIENTATION_MAX_ENTRIES
    )


def orientation_docs(workspace: Workspace) -> str:
    """The head of the repo's own orientation documents, so the minion starts
    from the map the authors wrote instead of exploring blind."""
    sections: list[str] = []
    budget = _DOC_MAX_CHARS
    for name in _DOC_NAMES:
        if budget < 200 or not (workspace.root / name).is_file():
            continue
        try:
            lines = read_file_text(workspace, name)
        except ToolError:
            continue
        head = "\n".join(lines[:_DOC_MAX_LINES]).strip()[:budget]
        if not head:
            continue
        note = " (beginning; read_file for the rest)" if len(lines) > _DOC_MAX_LINES else ""
        sections.append(f"--- {name}{note} ---\n{head}")
        budget -= len(head)
    return "\n\n".join(sections)


def task_message(question: str, workspace: Workspace, max_steps: int) -> str:
    kind = "a git repository" if workspace.is_git else "a plain directory (git tools unavailable)"
    docs = orientation_docs(workspace)
    doc_block = f"\n\nOrientation docs:\n{docs}" if docs else ""
    return (
        f"Question: {question}\n\n"
        f"Workspace: {workspace.root.name} — {kind}.\n"
        f"Budget: at most {max_steps} tool calls; leave one for submit_report.\n\n"
        f"Structure (file counts in parentheses; dirs collapsed below depth "
        f"{_ORIENTATION_MAX_DEPTH} — use list_files for detail):\n"
        f"{orientation_listing(workspace)}"
        f"{doc_block}"
    )

FORCE_REPORT_MESSAGE = (
    "Your tool-call budget is exhausted. Call submit_report NOW with what you have. "
    "Put anything you could not confirm into 'unanswered'. Do not call any other tool."
)

NUDGE_MESSAGE = (
    "Do not answer in plain text. Use the investigation tools, or call submit_report "
    "to deliver your final report."
)

EMPTY_MESSAGE_NUDGE = (
    "Your last message was empty — you must act, not just think. Call an investigation "
    "tool, or call submit_report with your report."
)
