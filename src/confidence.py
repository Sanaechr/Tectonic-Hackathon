"""Confidence level of an answer."""
from __future__ import annotations

from config import STRONG_SCORE
from models import Contradiction, Doc


def compute_confidence(used: list[Doc], contradictions: list[Contradiction], n_passages: int) -> str:
    if not used or n_passages == 0:
        return "insufficient"
    best = max(d.score for d in used)
    unresolved = any(c.winner is None for c in contradictions)
    strong = [d for d in used if d.score >= STRONG_SCORE]
    if best >= 75 and len(strong) >= 2 and not unresolved:
        return "high"
    if best >= 60:
        return "medium"
    return "low"

