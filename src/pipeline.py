"""Orchestration of one case: guardrail -> filter -> contradictions -> passages -> confidence -> answer.
Each step is delegated to a dedicated module; this file only chains them."""
from __future__ import annotations

from pathlib import Path

from answer_builder import build_answer
from confidence import compute_confidence
from config import MIN_DOC_COVERAGE, MIN_SCORE
from contradictions import find_contradictions
from experts import suggest_experts
from loader import load_docs
from models import Contradiction, Doc, Result
from passages import doc_matches, select_passages
from text_utils import detect_country, proper_names, question_topic


def guardrail_refusal(case: dict, question: str, country: str | None, best: int,
                      data_dir: Path, owners: dict) -> Result:
    """Refuse to answer (no PDF read, no AI call) and suggest an expert."""
    docs = load_docs(case["input"], data_dir, read_text=False)
    excluded = {}
    for d in docs:
        why = [f"score {d.score} < {MIN_SCORE}"]
        if country and d.meta.get("country") != country:
            why.append(f"country {d.meta['country']} != {country}")
        excluded[d.id] = ", ".join(why)
    experts = suggest_experts(question, docs, owners, country)
    msg = (f"Insufficient information: the best trust score is {best} (threshold {MIN_SCORE}) and no reliable, "
           "relevant document was found. No answer is generated. Please contact a manager or an expert"
           + (f" (suggestion: {experts[0]['name']}, {experts[0]['job_title']}, {experts[0]['email']})."
              if experts else "."))
    return Result(case["id"], question, "insufficient", msg, [], [], [], excluded,
                  ["Generation blocked by the guardrail"], experts)


def filter_candidates(docs: list[Doc], topic: set[str], country: str | None) -> tuple[list[Doc], dict[str, str]]:
    """Drop documents from another country, without content, or unrelated to the question."""
    candidates, excluded = [], {}
    for d in docs:
        if country and d.meta.get("country") != country:
            excluded[d.id] = f"country {d.meta['country']} != {country}"
        elif not d.text:
            excluded[d.id] = "content unavailable"
        elif not doc_matches(d, topic) or len(doc_matches(d, topic)) / len(topic) < MIN_DOC_COVERAGE:
            excluded[d.id] = "not relevant to the question"
        else:
            candidates.append(d)
    return candidates, excluded


def keep_reliable(candidates: list[Doc], contradictions: list[Contradiction],
                  excluded: dict[str, str]) -> tuple[list[Doc], set[str]]:
    """Split candidates into usable documents and those under MIN_SCORE (recorded in `excluded`)."""
    rejected_docs = {c.between[0] if c.winner == c.between[1] else c.between[1]
                     for c in contradictions if c.winner}
    usable = []
    for d in candidates:
        if d.score < MIN_SCORE:
            excluded[d.id] = f"score {d.score} < {MIN_SCORE}" + (
                "; contradicts a more reliable document" if d.id in rejected_docs else "")
        else:
            usable.append(d)
    return usable, rejected_docs


def answer_case(case: dict, data_dir: Path, owners: dict, question: str | None = None,
                use_llm: bool = False) -> Result:
    question = question or case["input"]["question"]
    country = detect_country(question)

    best = max(m["trust_score"] for m in case["input"]["documents"])
    if best < MIN_SCORE:
        return guardrail_refusal(case, question, country, best, data_dir, owners)

    docs = load_docs(case["input"], data_dir, read_text=True)
    warnings = [f"PDF missing or empty for {d.id} ({Path(d.meta['file']).name})" for d in docs if not d.text]

    topic = question_topic(question)
    qnames = proper_names(question)

    candidates, excluded = filter_candidates(docs, topic, country)
    # weak documents are kept here: they explain why something is rejected
    contradictions, losing = find_contradictions(candidates, topic, qnames)
    usable, rejected_docs = keep_reliable(candidates, contradictions, excluded)

    passages = select_passages(usable, topic, qnames, losing)
    used_ids = sorted({p.doc_id for p in passages} | {i for p in passages for i in p.also_in})
    used = [d for d in usable if d.id in used_ids]
    for d in usable:
        if d.id not in used_ids:
            excluded[d.id] = ("all relevant statements contradicted by a more reliable document"
                              if d.id in rejected_docs else "no relevant passage")

    confidence = compute_confidence(used, contradictions, len(passages))
    if confidence == "insufficient":
        return Result(case["id"], question, confidence,
                      "Insufficient information in the available documents. Please contact an expert.",
                      [], [], contradictions, excluded, warnings, suggest_experts(question, docs, owners, country))

    answer = build_answer(question, passages, contradictions, use_llm)
    return Result(case["id"], question, confidence, answer, used_ids, passages, contradictions,
                  excluded, warnings, [])
