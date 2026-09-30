"""Data model shared by every step of the pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class Doc:
    meta: dict
    text: str = ""

    @property
    def id(self): return self.meta["id"]
    @property
    def score(self): return self.meta["trust_score"]
    @property
    def day(self): return date.fromisoformat(self.meta["last_modified_date"])


@dataclass
class Passage:
    doc_id: str
    text: str
    relevance: float
    also_in: list[str] = field(default_factory=list)   # other documents stating the same thing
    trust: int = 0                                      # passage-level trust (0-100), see passage_trust()


@dataclass
class Contradiction:
    between: tuple[str, str]
    details: list[str]
    winner: str | None
    resolution: str


@dataclass
class Result:
    case_id: str
    question: str
    confidence: str
    answer: str
    used_docs: list[str]
    passages: list[Passage]
    contradictions: list[Contradiction]
    excluded: dict[str, str]
    warnings: list[str]
    suggested_experts: list[dict]
