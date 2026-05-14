"""pmem-bench runner — programmatic entrypoint + CLI.

Programmatic:

    from pmem_bench import run_eval

    def my_extractor(msg: str):
        ...  # return list[Claim]

    result = run_eval(extractor=my_extractor, holistic=True)
    print(f"Composite: {result['composite']:.2f}")

CLI:

    pmem-bench --extractor mymodule:my_extractor
    pmem-bench --extractor mymodule:fn --holistic
    pmem-bench --extractor mymodule:fn --category direct_claim --verbose
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from importlib import resources
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from pmem_bench.api import EvalExample, ExtractionResult
from pmem_bench.holistic import HolisticJudge, HolisticVerdict
from pmem_bench.judge import Judge
from pmem_bench.plugins import Extractor, load_extractor, normalize_extraction
from pmem_bench.score import ExampleScore, aggregate, score_example


def _data_dir() -> Path:
    # Bundled data; resources.files gives us a Path-like backed by the wheel
    return Path(str(resources.files("pmem_bench") / "data"))


def load_examples(category: str | None = None) -> list[EvalExample]:
    data_dir = _data_dir()
    files = sorted(Path(data_dir).glob("*.jsonl"))
    if category:
        files = [f for f in files if f.stem == category]
        if not files:
            available = sorted(p.stem for p in Path(data_dir).glob("*.jsonl"))
            sys.exit(f"category {category!r} not found. available: {', '.join(available)}")

    examples = []
    for f in files:
        for line_no, line in enumerate(f.read_text().splitlines(), start=1):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            try:
                examples.append(EvalExample.from_json(json.loads(line)))
            except (json.JSONDecodeError, KeyError) as e:
                print(f"warning: skipping {f.name}:{line_no}: {e}", file=sys.stderr)
    return examples


def _print_score(score: ExampleScore, example: EvalExample, verbose: bool) -> None:
    pass_fail = "PASS" if score.composite >= 0.8 and not score.forbidden_hit else "FAIL"
    print(f"  [{pass_fail}] {score.example_id:36s} composite={score.composite:.2f}  "
          f"P={score.precision:.2f} R={score.recall:.2f} ω={score.omega_calibration:.2f}")
    if verbose:
        print(f"       user: {example.user_message!r}")
        for failure in score.failures:
            print(f"       fail: {failure}")
        for m in score.matches:
            if m.extracted is None:
                print(f"       miss: expected {m.expected.subject} {m.expected.predicate} {m.expected.object_pattern!r}")
            elif m.verdict and m.verdict.overall < 1.0:
                print(f"       partial: {m.expected.predicate} -> {m.extracted.predicate} ({m.verdict.overall:.2f})")


def run_eval(
    extractor: Extractor,
    category: str | None = None,
    limit: int | None = None,
    holistic: bool = False,
    verbose: bool = False,
    client: anthropic.Anthropic | None = None,
) -> dict:
    """Run the benchmark against `extractor` and return aggregate scores.

    extractor: callable taking (str) and returning list[Claim] or ExtractionResult.
    category:  if set, restrict to one category (e.g. "direct_claim").
    limit:     if set, run at most N examples per category.
    holistic:  if True, also run the LLM-as-judge holistic evaluator.
    verbose:   if True, print per-example detail.
    client:    optional pre-built Anthropic client (otherwise constructed).

    Returns a dict with keys:
      composite, precision, recall, omega_calibration, predicate_correctness,
      forbidden_hits, n, by_category, [holistic if requested]
    """
    load_dotenv()
    client = client or anthropic.Anthropic()
    judge = Judge(client=client)
    holistic_judge = HolisticJudge(client=client) if holistic else None

    examples = load_examples(category)
    if not examples:
        return {"error": "no examples found"}

    if limit:
        by_cat: dict[str, list[EvalExample]] = defaultdict(list)
        for ex in examples:
            by_cat[ex.category].append(ex)
        examples = [ex for cat in by_cat.values() for ex in cat[:limit]]

    if verbose:
        print(f"running {len(examples)} example(s)...\n")

    scores_by_cat: dict[str, list[ExampleScore]] = defaultdict(list)
    holistic_by_cat: dict[str, list[HolisticVerdict]] = defaultdict(list)
    current_cat = None

    for ex in examples:
        if ex.category != current_cat:
            current_cat = ex.category
            if verbose:
                print(f"\n=== {ex.category} ===")

        try:
            result_raw = extractor(ex.user_message)
            result: ExtractionResult = normalize_extraction(result_raw)
        except Exception as e:
            if verbose:
                print(f"  [FAIL] {ex.id:36s} extractor raised: {type(e).__name__}: {e}")
            scores_by_cat[ex.category].append(ExampleScore(
                example_id=ex.id, category=ex.category,
                recall=0.0, precision=0.0, omega_calibration=0.0,
                predicate_correctness=0.0, composite=0.0, forbidden_hit=False,
                failures=[f"extractor raised: {type(e).__name__}: {e}"],
            ))
            continue

        if result.extraction_failed:
            if verbose:
                print(f"  [FAIL] {ex.id:36s} extraction_failed: {result.failure_reason}")
            scores_by_cat[ex.category].append(ExampleScore(
                example_id=ex.id, category=ex.category,
                recall=0.0, precision=0.0, omega_calibration=0.0,
                predicate_correctness=0.0, composite=0.0, forbidden_hit=False,
                failures=[f"extraction failed: {result.failure_reason}"],
            ))
            continue

        score = score_example(ex, result.claims, judge)
        scores_by_cat[ex.category].append(score)
        if verbose:
            _print_score(score, ex, verbose)

        if holistic_judge is not None:
            verdict = holistic_judge.judge(ex, result.claims)
            holistic_by_cat[ex.category].append(verdict)

    all_scores: list[ExampleScore] = []
    by_category: dict[str, dict] = {}
    for cat, scores in scores_by_cat.items():
        agg = aggregate(scores)
        by_category[cat] = agg
        all_scores.extend(scores)
    total = aggregate(all_scores)

    out: dict = {
        **total,
        "by_category": by_category,
    }

    if holistic_judge is not None:
        all_holistic: list[HolisticVerdict] = []
        holistic_by_cat_agg: dict[str, dict] = {}
        for cat, vs in holistic_by_cat.items():
            n = len(vs)
            holistic_by_cat_agg[cat] = {
                "n": n,
                "overall": sum(v.overall for v in vs) / max(1, n),
                "coverage": sum(v.coverage for v in vs) / max(1, n),
                "precision": sum(v.precision for v in vs) / max(1, n),
                "omega": sum(v.omega for v in vs) / max(1, n),
                "usefulness": sum(v.usefulness for v in vs) / max(1, n),
            }
            all_holistic.extend(vs)
        n = max(1, len(all_holistic))
        out["holistic"] = {
            "overall": sum(v.overall for v in all_holistic) / n,
            "coverage": sum(v.coverage for v in all_holistic) / n,
            "precision": sum(v.precision for v in all_holistic) / n,
            "omega": sum(v.omega for v in all_holistic) / n,
            "usefulness": sum(v.usefulness for v in all_holistic) / n,
            "by_category": holistic_by_cat_agg,
        }

    return out


def _print_summary(result: dict) -> None:
    print("\n\n=== SUMMARY ===")
    print(f"{'category':<28s} {'n':>4s} {'composite':>10s} {'precision':>10s} {'recall':>8s} {'ω-cal':>8s}")
    for cat, agg in sorted(result["by_category"].items()):
        print(f"{cat:<28s} {int(agg['n']):>4d} {agg['composite']:>10.2f} "
              f"{agg['precision']:>10.2f} {agg['recall']:>8.2f} {agg['omega_calibration']:>8.2f}")
    print("-" * 76)
    print(f"{'TOTAL':<28s} {int(result['n']):>4d} {result['composite']:>10.2f} "
          f"{result['precision']:>10.2f} {result['recall']:>8.2f} {result['omega_calibration']:>8.2f}")
    if result.get("forbidden_hits"):
        print(f"\n*** {int(result['forbidden_hits'])} example(s) emitted FORBIDDEN claims ***")

    if "holistic" in result:
        h = result["holistic"]
        print(f"\n=== HOLISTIC (LLM-as-judge) ===")
        print(f"{'category':<28s} {'n':>4s} {'overall':>8s} {'cov':>6s} {'prec':>6s} {'omega':>6s} {'use':>6s}")
        for cat, agg in sorted(h["by_category"].items()):
            print(f"{cat:<28s} {int(agg['n']):>4d} {agg['overall']:>8.2f} {agg['coverage']:>6.2f} "
                  f"{agg['precision']:>6.2f} {agg['omega']:>6.2f} {agg['usefulness']:>6.2f}")
        print("-" * 76)
        print(f"{'TOTAL':<28s} {'':>4s} {h['overall']:>8.2f} {h['coverage']:>6.2f} {h['precision']:>6.2f} "
              f"{h['omega']:>6.2f} {h['usefulness']:>6.2f}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="pmem-bench — personal-memory extraction benchmark"
    )
    parser.add_argument(
        "--extractor", required=True,
        help="extractor reference, e.g. 'mymodule:my_extract'",
    )
    parser.add_argument("--category", help="run only one category")
    parser.add_argument("--limit", type=int, help="max examples per category")
    parser.add_argument("--holistic", action="store_true",
                        help="also run holistic LLM-as-judge evaluator")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="print per-example detail")
    parser.add_argument("--json", action="store_true",
                        help="emit results as JSON to stdout (overrides verbose printing)")
    args = parser.parse_args()

    try:
        extractor = load_extractor(args.extractor)
    except (ValueError, ImportError, AttributeError, TypeError) as e:
        sys.exit(f"failed to load extractor: {e}")

    result = run_eval(
        extractor=extractor,
        category=args.category,
        limit=args.limit,
        holistic=args.holistic,
        verbose=args.verbose and not args.json,
    )

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        _print_summary(result)

    return 0 if result.get("composite", 0) >= 0.7 else 1


if __name__ == "__main__":
    sys.exit(main())
