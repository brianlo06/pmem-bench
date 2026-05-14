"""Plugin interface for pmem-bench extractors.

An extractor is any callable `(message: str) -> list[Claim]`. To plug yours
into the benchmark:

    1. Define a function or method matching that signature.
    2. Reference it on the command line as `module.path:function_name`
       or pass it directly to `run_eval(extractor=...)`.

For convenience, an extractor can also return a `pmem_bench.api.ExtractionResult`
(if you want to report extraction failures distinctly from empty results), or
raise an exception — both are handled.
"""

from __future__ import annotations

import importlib
import os
import sys
from typing import Callable, Protocol, Union

from pmem_bench.api import Claim, ExtractionResult


class ExtractorProtocol(Protocol):
    def __call__(self, message: str) -> list[Claim] | ExtractionResult: ...


Extractor = Union[Callable[[str], list[Claim]], Callable[[str], ExtractionResult]]


def load_extractor(spec: str) -> Extractor:
    """Load an extractor from a `module.path:function_name` string.

    The current working directory is added to sys.path so callers can
    reference their own modules without having to install them — typical
    CLI ergonomics. If your extractor is in an installed package, the cwd
    insertion is harmless.
    """
    if ":" not in spec:
        raise ValueError(
            f"extractor spec must be 'module.path:function', got {spec!r}"
        )
    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.insert(0, cwd)
    module_path, attr = spec.split(":", 1)
    module = importlib.import_module(module_path)
    if not hasattr(module, attr):
        raise AttributeError(
            f"module {module_path!r} has no attribute {attr!r}"
        )
    fn = getattr(module, attr)
    if not callable(fn):
        raise TypeError(f"{spec!r} is not callable")
    return fn


def normalize_extraction(value) -> ExtractionResult:
    """Accept either `list[Claim]` or `ExtractionResult` and return ExtractionResult."""
    if isinstance(value, ExtractionResult):
        return value
    if isinstance(value, list):
        return ExtractionResult(claims=list(value))
    raise TypeError(
        f"extractor must return list[Claim] or ExtractionResult, got {type(value).__name__}"
    )
