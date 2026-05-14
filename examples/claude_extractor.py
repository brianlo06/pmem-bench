"""Reference extractor using the Anthropic API + Claude Opus 4.7.

Run with:
    pmem-bench --extractor examples.claude_extractor:extract

Requires ANTHROPIC_API_KEY in env. Each call is ~$0.001-0.005 depending
on the message; with prompt caching the system prompt is cached after
the first call.

This is the same prompt that scored ~0.93 composite and ~0.95 holistic on
its own benchmark — included here as a reference, not as a target. Other
systems should aim to beat it.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import anthropic

from pmem_bench import Claim, ExtractionResult

EXTRACTION_MODEL = "claude-opus-4-7"

_PROMPT_PATH = Path(__file__).parent / "extract_prompt.md"
_PROMPT_TEMPLATE = _PROMPT_PATH.read_text()

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    match = re.match(r"^```(?:json)?\s*\n(.*?)\n```$", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text


def _split_prompt(template: str) -> tuple[str, str]:
    parts = template.rsplit("---", 1)
    if len(parts) != 2:
        raise ValueError("Prompt template missing final '---' separator")
    return parts[0].strip(), parts[1].strip()


def extract(message: str) -> ExtractionResult:
    """Run the reference extractor on a user message."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return ExtractionResult(
            claims=[],
            extraction_failed=True,
            failure_reason="ANTHROPIC_API_KEY not set",
        )

    system, user_template = _split_prompt(_PROMPT_TEMPLATE)
    rendered_user = user_template.replace("{user_message}", message)

    response = _get_client().messages.create(
        model=EXTRACTION_MODEL,
        max_tokens=2048,
        thinking={"type": "adaptive"},
        system=[
            {
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": rendered_user}],
    )

    text = next(
        (block.text for block in response.content if block.type == "text"),
        "",
    )

    try:
        payload = json.loads(_strip_code_fences(text))
        claims = [Claim.from_json(c) for c in payload.get("claims", [])]
        return ExtractionResult(claims=claims, raw_response=text)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        return ExtractionResult(
            claims=[],
            raw_response=text,
            extraction_failed=True,
            failure_reason=f"{type(e).__name__}: {e}",
        )
