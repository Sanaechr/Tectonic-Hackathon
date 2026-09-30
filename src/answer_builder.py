"""Answer text: LLM rewrite when requested, otherwise purely extractive with citations and trust."""
from __future__ import annotations

from config import STRONG_SCORE
from llm import llm_synthesis
from models import Contradiction, Passage


def extractive_answer(passages: list[Passage]) -> str:
    return "\n".join(
        f"- {p.text} [{', '.join([p.doc_id] + p.also_in)}] (trust {p.trust}"
        + ("" if p.trust >= STRONG_SCORE else ", to verify") + ")"
        for p in passages)


def build_answer(question: str, passages: list[Passage], contradictions: list[Contradiction],
                 use_llm: bool) -> str:
    answer = llm_synthesis(question, passages) if use_llm else None
    if not answer:
        answer = extractive_answer(passages)
    if contradictions:
        answer += "\n\nDisagreements between sources:"
        for c in contradictions:
            answer += f"\n- {c.between[0]} vs {c.between[1]}: {c.resolution}."
    return answer
