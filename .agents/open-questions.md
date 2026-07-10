# Open questions

- **Add a tool-calling preflight probe to `minions doctor`** (and possibly to
  `investigate` startup): one tiny completion with a dummy tool to verify the
  server+model combination actually emits structured tool_calls. Motivated by
  Devstral-24B burning 18 minutes before failing because its tool calling is
  non-functional via omlx (findings/2026-07-10-model-comparison.md).

- **Partial-match verification tier?** Run 4 produced a 99%-verbatim citation
  (docstring quoted with the closing `"""` pulled up from the next line) that
  strict verification rightly rejected. If near-misses turn out to be common,
  consider a distinct "partial" state (e.g. line-level match ratio) so GRU
  can triage without re-reading — but never soften what plain ✓ means.
- **Run-to-run variance is high** (same question: fail / 0%-verified /
  fail / 75%-verified before fixes landed). After the current fixes, gather a
  batch of runs to quantify reliability; consider temperature 0.1 or
  self-consistency (2 runs + merge) if needed.

- **Report quality of gpt-oss-20b**: does it follow the submit_report schema
  reliably, and how often do citations fail verification? Measure on real
  investigations before adding any retry/repair machinery.
- **Token accounting for the savings claim**: v1 records minion-side usage and
  report size. To *demonstrate* savings we eventually need a baseline: the
  same question answered by GRU directly (its token spend) vs. delegated.
  Design a small benchmark harness once v1 works.
- **Deterministic tooling depth**: brief suggests AST parsers / LSP / symbol
  indexes. Deferred until we see which questions the grep+read+git toolset
  fails on. Candidates: Python `ast` outline tool (cheap, stdlib), tree-sitter
  (multi-language, extra dep).
- **Context pressure at 32k**: is truncation of old tool results needed for
  long investigations, or do step budgets suffice? Watch traces.
- **Multi-repo / non-git directories**: search falls back to a Python scan,
  but git tools disable themselves. Is that degradation acceptable?
- **MCP adapter**: worth adding once someone actually wants an MCP host
  integration; the core is transport-agnostic by design (ADR-002).
- **omlx prompt caching**: usage reports `cached_tokens`; can we order
  messages to maximize cache hits across loop iterations? (System prompt +
  tool schemas are stable per run — likely already cached.)
