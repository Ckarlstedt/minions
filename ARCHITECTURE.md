# Architecture

Full decision records live in [.agents/decisions/](.agents/decisions/); this
document is the map.

## The problem shape

The expensive resource is **frontier-model context**. The cheap resources are
local-model tokens and local CPU. The design therefore pushes every byte of
raw repository content into the local loop and lets only a compact, verified
report cross back into GRU's context. Trustworthiness beats compression: a
report GRU has to double-check saves nothing.

## Components

```
          CLI (cli.py)                     ← adapter; MCP/HTTP would slot in beside it
              │
     InvestigationService (service.py)    ← transport-agnostic core
              │
   ┌──────────┼─────────────┬──────────────┐
   │          │             │              │
agent loop  tool layer   provider       verifier
(agent/)    (tools/)     (providers/)   (verification.py)
   │          │             │
 trace      Workspace    OpenAI-compat HTTP
(trace.py)  (containment)  (omlx, vLLM, Ollama, …)
```

- **`InvestigationService`** wires everything; nothing in it knows how it was
  invoked (ADR-002: CLI first, not MCP — a CLI reaches every agent that has a
  shell, and the expensive state lives in the model server anyway).
- **Agent loop** (`agent/loop.py`): one bounded tool-calling loop per
  question (ADR-003 — no DAG/planner until evidence demands one). Budgets:
  max tool calls, plus a context guard driven by the server-reported
  `prompt_tokens` so the run finishes before omlx's 32k wall. The loop ends
  when the model calls `submit_report`; invalid submissions are bounced back
  as tool errors for self-correction.
- **Tool layer** (`tools/`): `list_files`, `read_file`, `search`, and (in git
  repos only) `git_log`, `git_diff`, `git_blame`. Read-only *by construction*
  (ADR-005): in-process implementations, no shell, `Workspace.resolve()`
  containment on every path, git invoked with fixed argv and validated refs.
  The roster is deliberately small — small models pick tools better from
  short menus.
- **Provider layer** (`providers/`): a `ChatProvider` protocol with neutral
  message/usage types (ADR-006). The single OpenAI-compatible adapter covers
  omlx, vLLM, Ollama, LM Studio and OpenAI. Tests use a scripted
  `FakeProvider`.
- **Verifier** (`verification.py`): after the run, re-reads every cited line
  range and checks the verbatim excerpt appears (whitespace-normalized,
  ±10-line tolerance). Findings with no surviving evidence are downgraded
  (ADR-004). This converts "trust the model" into "check the excerpt exists";
  interpretation stays GRU's job — that split *is* the product.
- **Trace** (`trace.py`): JSONL audit log per run, written outside the
  investigated repo (`~/.local/state/minions/runs/`), so every report line
  can be traced to the tool output the minion actually saw.

## Data flow of one investigation

1. CLI parses args, loads `Settings` (env → defaults; omlx key auto-discovery).
2. Service resolves the `Workspace`, builds the tool registry, opens a trace.
3. Loop: system prompt + task message (question, budget, shallow file listing
   for orientation) → model ↔ tools until `submit_report`.
4. Submission is Pydantic-validated into a `ReportSubmission`.
5. Verifier stamps each `Evidence.verified` and the aggregate rate.
6. Report renders as compact markdown (default) or full JSON (`--json`).
   Exit code: 0 report delivered, 2 investigation failed, 1 infra/config error.

## Evolution paths (deliberately kept cheap)

- **New transport**: implement another thin adapter over
  `InvestigationService` (MCP server, HTTP daemon).
- **New provider**: implement `ChatProvider`; translation quirks live inside
  the adapter.
- **New tool**: add a `Tool` in `tools/` and register it — but it must be
  read-only and shell-free; that invariant is not negotiable (ADR-005).
- **Planner / parallel minions**: would sit between service and loop; the
  omlx scheduler already allows 3 concurrent requests.
- **Deterministic extraction** (AST outlines, symbol indexes): add as tools
  once traces show where grep+read investigations fail
  (see [.agents/open-questions.md](.agents/open-questions.md)).
