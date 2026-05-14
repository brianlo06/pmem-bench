# Reference results — pmem-bench v0.1

A snapshot of the reference Claude Opus 4.7 extractor running against the
full v0.1 benchmark. Treat these as a baseline to beat, not a target.

## Methodology

- **Extractor:** `examples/claude_extractor.py` — Claude Opus 4.7 with adaptive
  thinking and prompt caching. The full prompt is in `examples/extract_prompt.md`.
- **Judge:** `examples/judge.py` (Claude Opus 4.7 LLM-as-judge), per-claim
  semantic similarity match.
- **Holistic judge:** `examples/holistic.py` (also Opus 4.7), one extra call
  per example scoring coverage / precision / ω / usefulness on 1-10.
- **Runs averaged:** **1** (single snapshot). See "Variance" section below.
- **Total cost of this run:** ~$0.50 in API calls.
- **Date:** 2026-05-13.

## Headline scores

| Metric | Structured | Holistic |
|---|---:|---:|
| **Composite / Overall** | **0.89** | **0.93** |
| Precision | 0.90 | 0.98 |
| Recall / Coverage | 0.90 | 0.93 |
| ω-calibration | 0.93 | 0.94 |
| Predicate / Usefulness | 0.97 | 0.87 |
| Forbidden hits | 1 / 35 | — |

Interpretation: the reference extractor catches most claims correctly,
calibrates ω accurately, picks idiomatic predicates, and emitted one
forbidden claim out of 35 examples (somewhere in the regression suite — see
findings below). The holistic judge gives lower marks on `usefulness` —
the LLM-judge thinks some object phrasings could be cleaner ("retired from
teaching after 30 years" → maybe `current_status: retired (former teacher)`).

## Per-category, structured

| Category | n | composite | P | R | ω-cal | predicate | forbidden |
|---|---:|---:|---:|---:|---:|---:|---:|
| chit_chat_negative | 5 | **1.00** | 1.00 | 1.00 | 1.00 | 1.00 | 0 |
| direct_claim | 5 | **0.99** | 1.00 | 1.00 | 0.93 | 0.97 | 0 |
| negation | 5 | **1.00** | 1.00 | 1.00 | 1.00 | 1.00 | 0 |
| supersession | 5 | **1.00** | 1.00 | 1.00 | 1.00 | 0.99 | 0 |
| non_user_subject | 5 | 0.80 | 0.80 | 0.70 | 1.00 | 0.94 | 0 |
| regression | 5 | 0.76 | 0.90 | 1.00 | 0.60 | 0.94 | **1** |
| inference | 5 | **0.67** | 0.60 | 0.60 | 1.00 | 0.94 | 0 |

## Per-category, holistic

| Category | n | overall | coverage | precision | ω | usefulness |
|---|---:|---:|---:|---:|---:|---:|
| chit_chat_negative | 5 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| negation | 5 | 0.99 | 1.00 | 1.00 | 1.00 | 0.98 |
| direct_claim | 5 | 0.98 | 1.00 | 1.00 | 0.96 | 0.96 |
| supersession | 5 | 0.97 | 1.00 | 0.98 | 0.98 | 0.92 |
| inference | 5 | 0.87 | 0.80 | 0.96 | 0.98 | 0.72 |
| regression | 5 | 0.86 | 0.92 | 0.96 | 0.72 | 0.82 |
| non_user_subject | 5 | 0.84 | 0.76 | 0.96 | 0.94 | 0.70 |

## Notable findings

- **Negation, supersession, and chit_chat are perfect.** The hardest failure
  modes from prior iteration (emitting `identifies_as: religious` on a
  negation, missing breakup events, fabricating claims for chit-chat)
  are fully fixed.

- **Inference is the weakest category at 0.67.** The reference prompt
  sometimes under-extracts when the claim is implied by context rather
  than stated directly ("Hangover from hell" → user drank heavily,
  "Three failed startups later" → user has founded businesses). Both
  structured and holistic agree on this — coverage is the limiter, not
  fabrication.

- **One regression test failed via a forbidden hit.** The regression suite
  is designed to lock in fixes for known bugs. A 1-in-5 hit rate suggests
  the underlying patterns aren't fully extinguished — likely the
  `regression-001-negation-over-positive` ("Honestly, I've never been
  religious") slipping back to `identifies_as`. Worth a prompt revisit
  before declaring those bugs closed.

- **`non_user_subject` underperforms at 0.80.** Holistic agrees (0.84).
  Coverage = 0.70 means the model sometimes refuses to extract third-party
  claims even when the user clearly reported them. Reverse failure mode
  from inference — same root cause (over-conservative extraction).

- **ω-calibration is 0.93 structured / 0.94 holistic.** The reference
  extractor places claims in the right ω band consistently, which is
  the load-bearing property of pmem-bench's scoring philosophy.

## Variance

**This is a single run.** Expected variance is ~2-3% on the composite from
the stochastic LLM-judge alone, plus more from the extractor's adaptive
thinking. To compare your extractor's score meaningfully to this baseline:

1. Run the reference extractor 3-5 times on your machine, compute mean ± std
2. Run your extractor 3-5 times the same way
3. Compare distributions, not point estimates

We'll update this file with averaged scores in a future run.

## Reproducing

```bash
git clone https://github.com/brianlo06/pmem-bench
cd pmem-bench
echo 'ANTHROPIC_API_KEY=sk-ant-...' > .env
uv sync --extra dev
uv run pmem-bench --extractor examples.claude_extractor:extract --holistic --json > results.json
```

Total cost per run: ~$0.50.

## Versioning

These results are for **pmem-bench v0.1** specifically. If the eval data
changes (new examples, schema migration, scoring formula update), prior
scores aren't comparable to new ones. Pin the version when reporting:

> "Scored 0.93 composite on pmem-bench v0.1 (Claude Opus 4.7, n=5)."
