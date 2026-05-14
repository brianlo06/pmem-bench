"""Scoring tests — no API calls, mock the judge."""

from __future__ import annotations

from unittest.mock import MagicMock

from pmem_bench.api import Claim, EvalExample, ExpectedClaim, ForbiddenClaim
from pmem_bench.judge import JudgeVerdict
from pmem_bench.score import score_example


def _ex(expected, forbidden=()):
    return EvalExample(
        id="t", category="test", difficulty="easy",
        user_message="...",
        expected_claims=tuple(expected),
        must_not_extract=tuple(forbidden),
    )


def _claim(subject="user", predicate="works_at", obj="X", omega=0.85):
    return Claim(
        subject=subject, predicate=predicate, object=obj,
        valid_from="now", omega=omega, source_phrase="",
    )


def _judge_perfect():
    j = MagicMock()
    j.compare.return_value = JudgeVerdict(
        overall=1.0, subject_match=1.0, predicate_match=1.0, object_match=1.0,
        reason="exact",
    )
    return j


def _judge_no_match():
    j = MagicMock()
    j.compare.return_value = JudgeVerdict(
        overall=0.1, subject_match=0.1, predicate_match=0.1, object_match=0.1,
        reason="no",
    )
    return j


def test_perfect_match_full_score():
    expected = ExpectedClaim(
        subject="user", predicate="works_at", object_pattern="Anthropic",
        omega_range=(0.7, 1.0), supersedes_hint="works_at", required=True,
    )
    ex = _ex([expected])
    s = score_example(ex, [_claim(predicate="works_at", obj="Anthropic", omega=0.85)], _judge_perfect())
    assert s.composite >= 0.99
    assert s.recall == 1.0


def test_fabrication_destroys_precision():
    expected = ExpectedClaim(
        subject="user", predicate="works_at", object_pattern="Anthropic",
        omega_range=(0.7, 1.0), supersedes_hint=None, required=True,
    )
    ex = _ex([expected])
    extracted = [
        _claim(predicate="works_at", obj="Anthropic"),
        _claim(predicate="loves", obj="purple"),
    ]
    s = score_example(ex, extracted, _judge_perfect())
    assert abs(s.precision - 0.5) < 0.01
    assert len(s.fabricated) == 1


def test_forbidden_claim_is_hard_floor():
    forbidden = ForbiddenClaim(predicate_pattern="^works_at$", object_pattern="Google")
    ex = _ex([], forbidden=[forbidden])
    s = score_example(ex, [_claim(predicate="works_at", obj="Google")], _judge_perfect())
    assert s.composite == 0.0
    assert s.forbidden_hit


def test_empty_extraction_against_chitchat_is_perfect():
    ex = _ex([])
    s = score_example(ex, [], _judge_perfect())
    assert s.recall == 1.0
    assert s.precision == 1.0


def test_chitchat_with_fabrication_caught():
    ex = _ex([])
    s = score_example(ex, [_claim(predicate="likes", obj="X")], _judge_no_match())
    assert s.precision == 0.0


def test_omega_out_of_range_hurts_calibration():
    expected = ExpectedClaim(
        subject="user", predicate="works_at", object_pattern="Anthropic",
        omega_range=(0.85, 1.0), supersedes_hint=None, required=True,
    )
    ex = _ex([expected])
    s = score_example(ex, [_claim(predicate="works_at", obj="Anthropic", omega=0.25)], _judge_perfect())
    assert s.omega_calibration == 0.0
    assert s.recall == 1.0


def test_missed_required_kills_recall():
    expected = ExpectedClaim(
        subject="user", predicate="works_at", object_pattern="Anthropic",
        omega_range=(0.7, 1.0), supersedes_hint=None, required=True,
    )
    ex = _ex([expected])
    s = score_example(ex, [], _judge_no_match())
    assert s.recall == 0.0
    assert s.composite < 0.5
