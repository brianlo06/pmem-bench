# pmem-bench

A benchmark for **personal-memory claim extractors** — the layer that turns
natural-language conversation into structured facts about a user. Includes
35 hand-labeled examples across 7 categories, an LLM-as-judge for semantic
matching, a holistic LLM evaluator, and a plug-in API so you can score
*your* extractor in a few lines.

```bash
pip install pmem-bench
pmem-bench --extractor mymodule:my_extract
```

## Why this exists

Building a personal memory system means an extractor: a function that reads
a user message and outputs structured claims (who, predicate, value,
provenance). Get it wrong and you pollute the memory forever. Get it right
and the memory layer above gets very interesting.

There's no public benchmark for this layer specifically — most "memory"
evals score retrieval against QA pairs (LongMemEval and friends), not the
extraction step that produces the things being retrieved. pmem-bench fills
that gap.

The 35 examples are deliberately small and dense: each one tests a specific
failure mode (negation flips, ending-of-state events, third-party
recommendations, inference-from-context, etc.). They came out of iterating
on a real personal-memory project.

## Claim schema

```python
@dataclass
class Claim:
    subject: str            # "user", "user.mom", "Sam", ...
    predicate: str          # "works_at", "is_not", "had_pet", ...
    object: str             # "Anthropic" / "vegetarian" / "Penny (corgi)"
    valid_from: str         # "now" | ISO date | "unknown"
    omega: float            # provenance scalar in [0, 1]
    source_phrase: str      # verbatim substring of the user's message
    supersedes_hint: str    # predicate to look up if this updates a prior
```

The ω scalar is the load-bearing part. Lived > stated identity > reported >
inferred > speculation. The benchmark scores whether your extractor places
claims in the right ω band, not just whether it produces them at all.

## Plug your extractor in

Write a function that takes a string and returns claims:

```python
from pmem_bench import Claim

def my_extract(message: str) -> list[Claim]:
    # parse message however you want
    return [
        Claim(
            subject="user", predicate="works_at", object="Anthropic",
            valid_from="now", omega=0.85, source_phrase="work at Anthropic",
            supersedes_hint="works_at",
        ),
    ]
```

Run the benchmark:

```bash
pmem-bench --extractor mymodule:my_extract             # ~$0.30 with default judge
pmem-bench --extractor mymodule:my_extract --holistic  # adds ~$0.10
pmem-bench --extractor mymodule:my_extract --json      # machine-readable
```

Or call it from code:

```python
from pmem_bench import run_eval

result = run_eval(extractor=my_extract, holistic=True)
print(result["composite"], result["holistic"]["overall"])
```

## What the benchmark measures

**Structured (per-claim):** for each EXPECTED claim, the LLM judge finds the
best EXTRACTED match (≥0.70 similarity). Unmatched required = recall miss.
Unmatched extracted = precision miss. ω outside expected range = calibration
miss. Composite = `0.30·recall + 0.50·precision + 0.10·ω-cal + 0.10·predicate`.
Any `must_not_extract` hit floors the composite to 0.

**Holistic (whole-extraction):** a fresh Claude rates the extraction on a
1-10 scale across coverage / precision / ω / usefulness, ignoring the
expected-claims rubric. Catches extractions that have the right shape but
wrong feel — non-idiomatic predicates, missed nuance, etc.

## Categories

- **direct_claim** — "I work at Anthropic." Baseline.
- **supersession** — "I left Google for Anthropic." Past vs current.
- **negation** — "I'm not religious." Easy to flip the wrong way.
- **inference** — "Hangover from hell." Context-implied claims at low ω.
- **non_user_subject** — "My mom retired." Third-party claims at low ω.
- **chit_chat_negative** — "Nice weather!" The right answer is `[]`.
- **regression** — Concrete failure modes from prior iteration. Never delete.

## Reference results

The reference Claude Opus 4.7 extractor (see `examples/claude_extractor.py`):

|  | composite | precision | recall | ω-cal |
|---|---:|---:|---:|---:|
| Structured | ~0.93 | ~0.91 | ~0.93 | ~0.96 |
| Holistic   | ~0.95 (overall); precision ~0.99, usefulness ~0.89 | — | — | — |

These are running-average numbers — there's ~2-3% variance between runs due
to the LLM-judged scoring. Average 3-5 runs for stable comparisons.

## Why ω matters

If your extractor emits everything at ω=0.5, recall scores look fine but
you've destroyed the substrate. Personal memory needs to distinguish lived
experience from reported facts from inference — that's what makes selective
forgetting safe, contradictions resolvable, and speech-act hedging possible
downstream.

The benchmark explicitly scores ω calibration. If your system doesn't have
the concept, you can set ω=1.0 everywhere — you'll score well on recall and
poorly on calibration, and that's correct feedback about what's missing.

## Status

v0.1 — extraction eval only. Read-path eval (memory queries → composed
responses) is on the roadmap. Pin to `pmem-bench==0.1.*` for stable behavior.

## License

MIT.
