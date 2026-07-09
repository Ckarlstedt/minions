# ADR-003: The execution unit is one Investigation, run as one agentic loop

Status: accepted (2026-07-09)

## Problem

Choose the execution abstraction: commands, tasks, workflows, pipelines,
execution graphs, planners?

## Alternatives considered

- **Command-level RPC** ("run grep for me") — no token savings; GRU still does
  the synthesis, and the raw tool output goes back into GRU's context.
- **Workflow/DAG engine** — decomposing one question into pre-planned steps
  fragments semantic context (explicitly warned against in the brief), and we
  have zero evidence yet about *which* decompositions help.
- **Single agentic loop per question** — the minion holds all intermediate
  context locally, GRU pays only for the final report.

## Decision

The unit is an **Investigation**: one semantic question + optional scope +
budgets. One minion executes it as a bounded tool-calling loop (default
max-steps cap, per-tool output caps, 32k context guard) and must finish by
calling the `submit_report` tool. Parallelism is GRU's concern (it may launch
several CLI invocations; omlx handles 3 concurrent requests).

Evolution path, only if evidence demands it: a planner that splits a question
into sub-investigations and merges reports. The `InvestigationService`
interface already permits this without touching adapters.

## Drawbacks

- A single 20b minion may saturate on very broad questions ("audit this
  repo") — mitigated by scoping guidance in AGENTS.md, and the report schema
  has an `unanswered` field so the minion can say what it couldn't cover
  instead of hallucinating coverage.
