"""Stub extractor — always returns an empty list.

Useful for testing the pmem-bench infrastructure without API calls. It's
also a baseline: anything that doesn't beat this is doing real work wrong.
"""

from __future__ import annotations

from pmem_bench import Claim


def extract(message: str) -> list[Claim]:
    return []
