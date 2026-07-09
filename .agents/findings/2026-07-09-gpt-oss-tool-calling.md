# gpt-oss-20b tool-calling behavior on omlx (2026-07-09)

Observed live while debugging the first end-to-end run (trace:
`~/.local/state/minions/runs/20260709T203453-*.jsonl`). All confirmed by
direct API probes, not guessed.

1. **Nested JSON schemas are ignored.** With the Pydantic-generated
   `submit_report` schema (`$defs` + nested `findings[].evidence[]`), the
   model invented its own flat field names (`file`, `lines`, `description`).
   With a flat hand-written schema *plus the exact argument shape repeated in
   the system prompt*, compliance was 2/3 on first attempt — good enough
   because invalid submissions bounce back as validation errors and get
   retried. → `FlatSubmission` wire format in `report.py`, converted to the
   rich model service-side.

2. **`tool_choice` is silently ignored** by omlx (forced
   `{"type":"function",...}` still returned plain content). Forcing the final
   report therefore stays message-based (FORCE_REPORT_MESSAGE), not
   API-based.

3. **Empty assistant turns happen.** The model sometimes spends its entire
   turn on `reasoning_content` and emits neither content nor tool calls
   (steps 2/16/17 of the failed run; NOT length-truncation — completion was
   ~500 of 4096 tokens). Mitigations: a dedicated EMPTY_MESSAGE_NUDGE, nudge
   allowance raised to 3, `reasoning` captured into traces so these turns are
   diagnosable, and empty content sent as `""` (not `null`) in the wire
   history.

4. **Excerpts arrive with `NN| ` prefixes.** The model copies read_file
   output verbatim *including* line-number prefixes, whatever the prompt
   says (run 2: correct findings, 0% verification). → prefixes are stripped
   deterministically at submission intake (`strip_line_number_prefixes`).

5. **The report sometimes arrives as plain text.** Run 3 failed because the
   model wrote a *fully valid* report JSON into chat content twice instead of
   calling submit_report. → `_salvage_submission` in the loop: plain text
   that validates as a FlatSubmission is accepted (identical validation, and
   the citation verifier still runs — the channel grants no extra trust).

6. **Verifier strictness observed working as intended.** Run 4 (complete,
   75% verified): the one ✗ citation quoted a docstring but attached the
   closing `"""` from the following line — near-verbatim, not verbatim,
   correctly refused and downgraded. Whether a "partial match" tier is worth
   adding is tracked in open-questions.md.

Lesson recorded as a principle: for small models, the tool *schema* is
documentation, not enforcement — enforcement lives in Pydantic validation +
the retry loop + the deterministic verifier.
