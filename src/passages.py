"""Passage handling: relevance of documents/sentences, selection, deduplication and passage-level trust."""
from __future__ import annotations

from datetime import date

from config import (CORROBORATION_BONUS, DEDUP_JACCARD, FACT_MIN_RATIO, MAX_PASSAGES, SENT_MIN_RATIO,
                    STALE_DAYS, STALE_PENALTY)
from models import Doc, Passage
from text_utils import jaccard, proper_names, split_sentences, stems, value_tokens


def doc_matches(doc: Doc, topic: set[str]) -> set[str]:
    return topic & stems(doc.meta["title"] + " " + doc.text)


def score_sentences(doc: Doc, topic: set[str], qnames: set[str]) -> list[Passage]:
    """Keep sentences that share keywords with the question. A single shared keyword is enough
    when the sentence carries a fact (a number/date or a name)."""
    out = []
    for s in split_sentences(doc.text):
        common = topic & stems(s)
        ratio = len(common) / len(topic) if topic else 0.0
        has_fact = bool(value_tokens(s)) or bool(proper_names(s) - qnames)
        if len(common) >= 2 or (common and (ratio >= SENT_MIN_RATIO or (has_fact and ratio >= FACT_MIN_RATIO))):
            out.append(Passage(doc.id, s, ratio))
    return out


def passage_trust(p: Passage, docs_by_id: dict[str, Doc], ref_day: date) -> int:
    """Trust of ONE statement, not just of its document:
    source score + bonus for each independent document that corroborates it
    - penalty if the source is stale compared with the newest usable document."""
    src = docs_by_id[p.doc_id]
    trust = src.score + CORROBORATION_BONUS * len(set(p.also_in) - {p.doc_id})
    if (ref_day - src.day).days > STALE_DAYS:
        trust -= STALE_PENALTY
    return max(0, min(100, trust))



def select_passages(usable: list[Doc], topic: set[str], qnames: set[str],
                    losing: set[tuple[str, str]]) -> list[Passage]:
    """Most relevant sentences of the reliable documents: duplicates merged, losing statements
    dropped, capped to MAX_PASSAGES, then sorted by passage-level trust."""
    passages: list[Passage] = []
    for d in sorted(usable, key=lambda x: -x.score):
        for p in score_sentences(d, topic, qnames):
            if (d.id, p.text) in losing:
                continue
            dup = next((q for q in passages if jaccard(stems(q.text), stems(p.text)) >= DEDUP_JACCARD), None)
            if dup:
                dup.also_in.append(p.doc_id)
            else:
                passages.append(p)
    if len(passages) > MAX_PASSAGES:
        keep = sorted(passages, key=lambda p: -p.relevance)[:MAX_PASSAGES]
        passages = [p for p in passages if p in keep]
    if passages:
        docs_by_id = {d.id: d for d in usable}
        ref_day = max(d.day for d in usable)
        for p in passages:
            p.trust = passage_trust(p, docs_by_id, ref_day)
        passages.sort(key=lambda p: (-p.trust, -p.relevance))
    return passages
