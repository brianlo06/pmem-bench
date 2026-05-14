"""pmem-bench — personal-memory extraction benchmark.

Public API:

  from pmem_bench import Claim, ExpectedClaim, ExtractionResult
  from pmem_bench import run_eval, load_extractor

  def my_extractor(msg: str) -> list[Claim]:
      ...

  result = run_eval(extractor=my_extractor, holistic=True)
"""

from pmem_bench.api import (
    Claim,
    EvalExample,
    ExpectedClaim,
    ExtractionResult,
    ForbiddenClaim,
)
from pmem_bench.plugins import Extractor, load_extractor, normalize_extraction
from pmem_bench.run import load_examples, run_eval

__version__ = "0.1.0"

__all__ = [
    "__version__",
    # types
    "Claim",
    "EvalExample",
    "ExpectedClaim",
    "ExtractionResult",
    "ForbiddenClaim",
    # plugin interface
    "Extractor",
    "load_extractor",
    "normalize_extraction",
    # runner
    "run_eval",
    "load_examples",
]
