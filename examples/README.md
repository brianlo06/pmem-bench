# pmem-bench examples

Reference extractors you can run the benchmark against.

| Extractor | What it does | API key? | Cost |
|---|---|---|---|
| `stub_extractor.py` | Returns `[]` for every input. Floor baseline. | No | Free |
| `claude_extractor.py` | Uses Claude Opus 4.7 + adaptive thinking. The reference impl. | Yes | ~$0.30/run |

## Running

```bash
# stub
uv run pmem-bench --extractor examples.stub_extractor:extract

# reference Claude extractor
uv run pmem-bench --extractor examples.claude_extractor:extract --holistic
```

## Writing your own

Define a function `(message: str) -> list[Claim]` and reference it by module
path. You can return either a plain `list[Claim]` or an `ExtractionResult`
(if you want to report extraction failures distinctly from empty results).

```python
from pmem_bench import Claim

def extract(message: str) -> list[Claim]:
    # parse message, return claims
    return [
        Claim(
            subject="user",
            predicate="works_at",
            object="Anthropic",
            valid_from="now",
            omega=0.85,
            source_phrase="work at Anthropic",
            supersedes_hint="works_at",
        ),
    ]
```

The benchmark imports your function dynamically — make sure your module is
on the Python path (i.e. you're running from a directory where `python -c
"import yourmodule"` works).
