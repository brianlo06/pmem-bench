"""Plugin loader + extraction normalization tests."""

from __future__ import annotations

import pytest

from pmem_bench import Claim, ExtractionResult, load_extractor
from pmem_bench.plugins import normalize_extraction


def test_load_extractor_returns_callable():
    fn = load_extractor("examples.stub_extractor:extract")
    assert callable(fn)
    assert fn("anything") == []


def test_load_extractor_bad_spec_raises():
    with pytest.raises(ValueError):
        load_extractor("no_colon_here")


def test_load_extractor_missing_module_raises():
    with pytest.raises(ImportError):
        load_extractor("definitely_not_a_real_module:fn")


def test_load_extractor_missing_attr_raises():
    with pytest.raises(AttributeError):
        load_extractor("pmem_bench:nonexistent_function")


def test_normalize_extraction_accepts_list_of_claims():
    claims = [Claim(
        subject="user", predicate="works_at", object="X",
        valid_from="now", omega=0.85, source_phrase="",
    )]
    result = normalize_extraction(claims)
    assert isinstance(result, ExtractionResult)
    assert result.claims == claims


def test_normalize_extraction_passes_through_result():
    er = ExtractionResult(claims=[], extraction_failed=True, failure_reason="x")
    out = normalize_extraction(er)
    assert out is er


def test_normalize_extraction_rejects_garbage():
    with pytest.raises(TypeError):
        normalize_extraction("not a list")
