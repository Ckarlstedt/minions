"""`minions init`: teach a repository's coding agents to delegate investigation.

Appends (never replaces) a sentinel-marked instruction block to the target
repo's agent-instructions file (AGENTS.md by convention). Re-running updates
the block in place, so instructions can be upgraded without duplication and
without touching anything a human wrote around them.

This is deliberately the only command in the package that writes inside a
repository. Investigation stays read-only by construction (ADR-005); init is
an explicit, human-invoked setup step that touches exactly one file
(ADR-007).
"""

from __future__ import annotations

from pathlib import Path

BEGIN_MARK = "<!-- minions:begin -->"
END_MARK = "<!-- minions:end -->"

DEFAULT_FILE = "AGENTS.md"

INSTRUCTIONS_BLOCK = f"""{BEGIN_MARK}
<!-- Managed by `minions init`; edits inside this block will be overwritten. -->
## Investigation delegation (minions)

`minions` is available on this machine: it delegates repository investigation
to a cheap local model and returns a compact report with machine-verified
citations. Prefer it over reading through the repo yourself whenever a
question requires multi-file searching or reading you don't need verbatim in
your context.

```bash
minions investigate "<one specific question>" [--repo PATH]   # report on stdout
minions doctor                                                # if it misbehaves
```

- Ask one semantic question per call, with success criteria in the question:
  "Where is pagination implemented in the API layer, and which tests cover
  it?" — not "audit this repo", and not "run grep" (just run grep yourself).
- Citations marked ✓ were mechanically verified against the real files — rely
  on them without re-reading the source. `✗ UNVERIFIED` means verify before
  acting on it.
- Items under "Not answered" are honest gaps: investigate those yourself or
  ask a narrower follow-up.
- Exit codes: 0 = report delivered; 2 = investigation failed (rephrase, or
  investigate yourself); 1 = setup problem (run `minions doctor`).
- Independent questions can run in parallel (up to 3 concurrent).
{END_MARK}"""


def write_agent_instructions(repo: Path, file_name: str = DEFAULT_FILE) -> str:
    """Create or update the instruction block. Returns "created" | "updated" |
    "unchanged" | "added" describing what happened."""
    repo = repo.resolve()
    if not repo.is_dir():
        raise NotADirectoryError(f"Not a directory: {repo}")
    target = repo / file_name

    if not target.exists():
        target.write_text(INSTRUCTIONS_BLOCK + "\n", encoding="utf-8")
        return "created"

    text = target.read_text(encoding="utf-8")
    begin = text.find(BEGIN_MARK)
    end = text.find(END_MARK)

    if begin != -1 and end != -1 and end > begin:
        current = text[begin : end + len(END_MARK)]
        if current == INSTRUCTIONS_BLOCK:
            return "unchanged"
        updated = text[:begin] + INSTRUCTIONS_BLOCK + text[end + len(END_MARK) :]
        target.write_text(updated, encoding="utf-8")
        return "updated"

    separator = "" if text.endswith("\n\n") else ("\n" if text.endswith("\n") else "\n\n")
    target.write_text(text + separator + INSTRUCTIONS_BLOCK + "\n", encoding="utf-8")
    return "added"
