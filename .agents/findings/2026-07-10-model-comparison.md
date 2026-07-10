# Minion model comparison (2026-07-10, in progress)

Standard question (against this repo): *"How does this codebase prevent the
investigation tools from writing to or escaping the repository?"* All runs on
the same omlx server; traces referenced by timestamp in the state dir.

| Model | Outcome | Notes |
| --- | --- | --- |
| gpt-oss-20b-MXFP4-Q8 (baseline) | **complete, 75% verified**, 17 steps, 107s, ~76k local tokens | Reliable-ish after flat-schema/salvage fixes; run-to-run variance remains a watch item |
| GLM-4.7-Flash-6bit | did not load | omlx prefill memory guard: predicted ~26.3–26.7 GB peak vs ~26.1 GB cap while another model resident (3 attempts) |
| Devstral-Small-2-24B-Instruct-2512-4bit | **failed**, 4 steps, 1052s (!) | Never emitted structured tool_calls: output contained raw `[/INST]` template artifacts and pseudo-tool-call text, then degenerate repetition to the 4096-token cap. Tool calling non-functional via omlx for this model; also far too slow to be a minion |
| Qwen3.5-27B-Claude-4.6-Opus-Distilled-MLX-4bit | **failed** (pre-fix code), ~4 min/step | Dense 27B decodes at ~8 tok/s on this hardware — unusable regardless of quality. Emitted `<tool_call>` text omlx didn't parse; this shape is now salvageable, but the speed alone disqualifies it |
| LFM2.5-8B-A1B-MLX-8bit | **failed**, 5 steps, 55s | Blazing fast (~10s/step) and structured tool calling *works*, but after one tool call it stops investigating and emits premature report-JSON with fabricated evidence (cited a nonexistent line of .env.example.toml) and speculative claims ("may enforce"). 1.5B active params can't sustain investigate-then-report discipline. Fast-but-wrong is worthless under verified citations |
| Ornith-1.0-35B-5bit-XL-mlx | untested | ~22GB+ weights, exceeds memory |

**Verdict: gpt-oss-20b-MXFP4-Q8 stays the minion.** It is the only tested
model that (a) fits the memory budget, (b) has functional tool calling
through omlx, and (c) actually investigates before reporting. The
speed/accuracy frontier on this machine is: gpt-oss for real reports; nothing
currently beats it. Revisit when a ~10-20B-class MoE with strong agentic
training ships in MLX (that's the profile that wins here).

## Benchmark research (omlx.ai/benchmarks, M3 Pro 18-core GPU / 36 GB)

Machine constraint: ~12 GB of memory is not reclaimable for models, and the
omlx memory guard caps predicted peak at ~26 GB → **model weights must stay
≲ 12 GB** (with KV headroom). Confirmed by three failed GLM loads.

Speed data (4-8k context, pp = prefill tok/s, tg = generation tok/s):

| Model | Quant | pp | tg | Weights | Fits? |
| --- | --- | --- | --- | --- | --- |
| gpt-oss-20b (MoE A3.6B) | MXFP4 | ~615-635 | ~40-45 | ~11.3 GB | ✓ (proven) |
| LFM2.5-8B-A1B (MoE A1.5B) | 4bit | ~1210 (14c!) | ~87-97 | ~4.6 GB | ✓ |
| LFM2.5-8B-A1B | 8bit | ~1180 (14c) | ~60 | ~8.8 GB | ✓ |
| Nemotron-3-Nano-30B (MoE) | 4-5bit | ~490-510 | ~30-47 | ~16-20 GB | ✗ |
| GLM-4.7-Flash | 4-6bit | ~330-390 | ~28-38 | ≥15 GB | ✗ |
| Qwen3.5-9B (dense) | 4bit | ~350 | ~27 | ~5 GB | ✓ but slower than gpt-oss on both axes |
| Qwen3.5-27B (dense) | 4bit | ~300 | **~7.8** | ~15 GB | ✗ and unusably slow |

Structural insight: on M3 Pro memory bandwidth, **dense models are the trap**
(Qwen3.5-27B decodes at 8 tok/s); MoE architectures dominate the
speed/quality frontier. Every viable candidate is MoE.

Accuracy side (HF open-llm-leaderboard is frozen/stale — used model cards +
function-calling benchmarks instead): LFM2.5-8B-A1B reports IFEval 91.8,
BFCLv3 64.8 (function calling), solid for a 1.5B-active model but below the
20B class. gemma has weak native tool calling; Mistral-family templates are
proven broken via omlx (Devstral above); Llama-3.x-8B is a generation behind
on agentic metrics.

Takeaways so far:

- "OpenAI-compatible" endpoints do not guarantee functional tool calling per
  model — the server's template/parser support for each model family matters
  as much as the model itself. A preflight tool-calling probe in
  `minions doctor` would catch this in seconds instead of an 18-minute
  failed run (added to open-questions).
- The loop's failure handling held up in every case: memory rejection →
  clean ProviderError (exit 1); non-tool-calling model → nudges, then clean
  failed report (exit 2). No hangs, no garbage reports.
