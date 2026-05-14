"""Public types for pmem-bench.

The three structures plugin authors care about:

  - Claim         : what their extractor returns per turn
  - ExpectedClaim : what each eval example expects
  - EvalExample   : one (user_message, expected) pair

Plus EvalResult / ExampleScore which the runner returns.

The Claim schema deliberately mirrors a personal-memory extractor's natural
output: who/predicate/value plus a provenance scalar ω ∈ [0,1] and an
optional supersession hint. If your system stores facts differently, write
a thin adapter that maps your representation to this schema.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class Claim:
    """A structured fact extracted from one turn of conversation.

    subject:         "user" for facts about the user; "user.<role>" for
                     related people (e.g. "user.mom"); proper-name strings
                     for third parties.
    predicate:       snake_case relation name (works_at, lives_in, ...).
    object:          the value — free text or an entity reference.
    valid_from:      ISO date | "now" | "unknown" — when the fact became true.
    omega:           provenance scalar in [0, 1].
                       1.00  lived ("I went to Tokyo")
                       0.85  stated identity ("I'm a data scientist")
                       0.50  reported about other ("My sister married")
                       0.25  inferred from context
                       0.10  speculation
    source_phrase:   verbatim substring of the user's message.
    supersedes_hint: if this claim updates a prior claim with the same
                     (subject, predicate), the predicate name to look up.
    """
    subject: str
    predicate: str
    object: str
    valid_from: str
    omega: float
    source_phrase: str
    supersedes_hint: str | None = None

    @classmethod
    def from_json(cls, d: dict) -> Claim:
        return cls(
            subject=d["subject"],
            predicate=d["predicate"],
            object=d["object"],
            valid_from=d.get("valid_from", "unknown"),
            omega=float(d["omega"]),
            source_phrase=d.get("source_phrase", ""),
            supersedes_hint=d.get("supersedes_hint"),
        )

    def to_json(self) -> dict:
        return {
            "subject": self.subject,
            "predicate": self.predicate,
            "object": self.object,
            "valid_from": self.valid_from,
            "omega": self.omega,
            "source_phrase": self.source_phrase,
            "supersedes_hint": self.supersedes_hint,
        }


@dataclass(frozen=True)
class ExpectedClaim:
    """An expected claim in an eval example. Uses ranges and patterns rather
    than exact matches to give extractors latitude for synonyms and rounding.
    """
    subject: str
    predicate: str
    object_pattern: str
    omega_range: tuple[float, float]
    valid_from_window: str = "any"
    supersedes_hint: str | None = None
    required: bool = True

    @classmethod
    def from_json(cls, d: dict) -> ExpectedClaim:
        return cls(
            subject=d["subject"],
            predicate=d["predicate"],
            object_pattern=d["object"],
            omega_range=tuple(d["omega_range"]),
            valid_from_window=d.get("valid_from_window", "any"),
            supersedes_hint=d.get("supersedes_hint"),
            required=d.get("required", True),
        )


@dataclass(frozen=True)
class ForbiddenClaim:
    """A pattern an extractor must NOT emit. Hitting any forbidden claim
    drops composite to 0 for that example."""
    predicate_pattern: str
    object_pattern: str | None = None

    @classmethod
    def from_json(cls, d: dict) -> ForbiddenClaim:
        return cls(
            predicate_pattern=d["predicate_pattern"],
            object_pattern=d.get("object_pattern"),
        )


@dataclass(frozen=True)
class EvalExample:
    id: str
    category: str
    difficulty: Literal["easy", "medium", "hard", "adversarial"]
    user_message: str
    expected_claims: tuple[ExpectedClaim, ...]
    must_not_extract: tuple[ForbiddenClaim, ...] = ()
    context: tuple[dict, ...] = ()
    memory_state: tuple[dict, ...] = ()
    notes: str = ""

    @classmethod
    def from_json(cls, d: dict) -> EvalExample:
        exp = d.get("expected", {})
        return cls(
            id=d["id"],
            category=d["category"],
            difficulty=d.get("difficulty", "easy"),
            user_message=d["user_message"],
            expected_claims=tuple(
                ExpectedClaim.from_json(c) for c in exp.get("claims", [])
            ),
            must_not_extract=tuple(
                ForbiddenClaim.from_json(c) for c in exp.get("must_not_extract", [])
            ),
            context=tuple(d.get("context", [])),
            memory_state=tuple(d.get("memory_state", [])),
            notes=d.get("notes", ""),
        )


@dataclass
class ExtractionResult:
    """What an extractor returns. The runner converts raw extractor output
    (a list of Claim) into this structure; extractor authors only need to
    return the list of claims.
    """
    claims: list[Claim] = field(default_factory=list)
    raw_response: str = ""
    extraction_failed: bool = False
    failure_reason: str | None = None
