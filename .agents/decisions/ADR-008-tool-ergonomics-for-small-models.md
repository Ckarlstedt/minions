# ADR-008: Match tool ergonomics to what small models actually emit

Status: accepted (2026-07-10)

## Problem

A live trace (run `20260710T134018`, a structure question against an
external repo) showed the minion wasting most of its budget on failures the
tool layer itself induced:

- `search` with glob `**/*.{ts,js,py}` returned "No matches found" even
  though matching files existed — `fnmatch` treats `{a,b}` as literal, `*`
  crosses `/`, and `**/` demands at least one directory. A silent false
  negative is indistinguishable from a true absence to the model.
- 4 of 15 steps were byte-identical repeats of an earlier search: small
  models loop on the same query when stuck.
- `list_files` twice dumped 300 flat paths (thousands of tokens each) for a
  question asking for "the tree structure" — no tool could answer that
  compactly.
- The model never read the repo's README/AGENTS docs and worked blind.

## Alternatives considered

- **Shell out to `tree` / ripgrep** — violates ADR-005 (shell-free by
  construction); everything needed is expressible in-process.
- **Advertise available system executables in the prompt** — useless (the
  minion cannot execute anything outside the registry) and harmful: it
  invites a suggestible small model to call tools that do not exist, and a
  PATH inventory is thousands of tokens re-paid every step.
- **Document fnmatch semantics in the tool schema** — models pattern-match
  to ripgrep/gitignore conventions regardless; the silent-wrong-result
  failure mode would remain.
- **Larger step budgets** — pays for the waste instead of removing it.

## Decision

Four changes, all inside existing invariants (read-only, shell-free, small
tool roster):

1. **Gitignore-style glob matching** (`tools/globmatch.py`): `*` stays
   within one segment, `**/` spans zero or more directories, `{a,b}`
   alternation, `[...]` classes, patterns without `/` match file names at
   any depth. Malformed patterns raise `ToolError` — an explicit error
   instead of an empty result. Used by `list_files` and `search`.
2. **Tree rendering** (`tools/tree.py`): depth-limited tree with recursive
   per-directory file counts. Replaces the flat orientation listing in the
   task message, and replaces `list_files` output when results exceed
   `MAX_LIST_RESULTS` (entry-capped structure overview + "narrow with
   path/glob" hint instead of a truncated 300-path dump).
3. **Orientation docs in the task message** (`agent/prompts.py`): the head
   of `README.md` / `AGENTS.md` / `CLAUDE.md` (60 lines per doc, 4000 chars
   total) is injected so the minion starts from the map the repo authors
   wrote. Local prompt tokens are cheap; steps are scarce.
4. **Duplicate-call suppression** (`agent/loop.py`): a tool call identical
   to an earlier one (after canonicalizing argument order) is answered with
   a short pointer to the earlier step instead of being re-run. Sound
   because the tool layer is read-only — the repo cannot change mid-run.

## Drawbacks

- `globmatch` is ~100 lines of custom matching code to maintain; mitigated
  by focused unit tests and a deliberately small supported syntax.
- Doc heads add ~1k tokens to every step's prompt; bounded by the char cap
  and well inside the 24k context guard.
- Dedupe answers with a pointer, not the previous output — if a model
  cannot recover the earlier result from context it must re-derive the
  query with different arguments. Traces will show if this bites.
