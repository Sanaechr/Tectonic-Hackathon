"""Contradiction detection between documents and resolution by trust score + recency."""
from __future__ import annotations

import re

from config import (CONTRA_JACCARD, CONTRADICTION_GAP, NEGATION_JACCARD, OVERLAP_NAMES, OVERLAP_VALUES,
                    QUALIFIER_WORDS, RECENCY_DAYS, TRUSTED_NEWER)
from models import Contradiction, Doc
from text_utils import has_negation, jaccard, proper_names, split_sentences, stems, value_tokens


def conflict_reason(sa: str, sb: str, topic: set[str], qnames: set[str]) -> str | None:
    """Do two sentences talk about the same thing but disagree?"""
    sta, stb = stems(sa), stems(sb)
    shared = sta & stb
    if len(shared) < 2 or not (shared & topic):
        return None
    qualifiers = stems(QUALIFIER_WORDS)
    if (sta - stb) & qualifiers and (stb - sta) & qualifiers:
        return None                       # e.g. "Remaining: 207,000" vs "Total invoiced: 273,000"
    sim = jaccard(sta, stb)
    overlap = len(shared) / min(len(sta), len(stb))
    na, nb = value_tokens(sa), value_tokens(sb)
    da, db = na - nb, nb - na
    kind = lambda v: "date" if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) else "num"
    if da and db and not (na <= nb or nb <= na) and {kind(v) for v in da} & {kind(v) for v in db} \
            and (sim >= CONTRA_JACCARD or overlap >= OVERLAP_VALUES):
        return f"different values ({', '.join(sorted(da))} vs {', '.join(sorted(db))})"
    pa, pb = proper_names(sa) - qnames, proper_names(sb) - qnames
    if pa - pb and pb - pa and overlap >= OVERLAP_NAMES:
        return f"different names/places ({', '.join(sorted(pa - pb))} vs {', '.join(sorted(pb - pa))})"
    if has_negation(sa) != has_negation(sb) and sim >= NEGATION_JACCARD:
        return "statement vs negation"
    return None


def corroborated(sentence: str, other: Doc) -> bool:
    """Is this sentence backed by a sentence of the other document (same values, same subject)?"""
    vals, st = value_tokens(sentence), stems(sentence)
    return bool(vals) and any(vals <= value_tokens(o) and len(st & stems(o)) >= 2
                              for o in split_sentences(other.text))


def resolve(a: Doc, b: Doc) -> tuple[Doc | None, str]:
    hi, lo = (a, b) if a.score >= b.score else (b, a)
    gap = hi.score - lo.score
    lo_newer_by = (lo.day - hi.day).days
    if gap >= CONTRADICTION_GAP:
        if lo_newer_by >= RECENCY_DAYS and lo.score >= TRUSTED_NEWER:
            return None, (f"UNRESOLVED: {lo.id} is more recent ({lo.meta['last_modified_date']}) but less trusted "
                          f"({lo.score} vs {hi.score}); both versions are shown, please verify")
        return hi, f"{hi.id} retained (score {hi.score} vs {lo.score})"
    if -lo_newer_by >= RECENCY_DAYS:
        return hi, f"{hi.id} retained (score {hi.score} vs {lo.score} and more recent)"
    return None, f"UNRESOLVED: scores too close ({hi.score} vs {lo.score}), please verify"


def find_contradictions(docs: list[Doc], topic: set[str], qnames: set[str]):
    """Returns (contradictions, losing) where losing is a set of (doc_id, sentence) that lost a
    contradiction and must not appear in the answer."""
    sentences = {d.id: split_sentences(d.text) for d in docs}
    pairs = []
    for i, a in enumerate(docs):
        for b in docs[i + 1:]:
            hits = []
            for sa in sentences[a.id]:
                for sb in sentences[b.id]:
                    reason = conflict_reason(sa, sb, topic, qnames)
                    # two templated lines (e.g. 'ISO 9001 ... 2027' vs 'ISO 14001 ... 2026') that are each
                    # confirmed elsewhere in the other document are different facts, not a conflict
                    if reason and not (corroborated(sa, b) and corroborated(sb, a)):
                        hits.append((sa, sb, reason))
            if hits:
                winner, text = resolve(a, b)
                pairs.append([a, b, hits, winner, text])

    losing: set[tuple[str, str]] = set()
    for a, b, hits, winner, _ in pairs:
        if winner:
            losing |= {(b.id, sb) if winner is a else (a.id, sa) for sa, sb, _ in hits}

    found = []
    for a, b, hits, winner, text in pairs:
        if winner is None:   # already overruled elsewhere? then this disagreement is moot
            if all((a.id, sa) in losing or (b.id, sb) in losing for sa, sb, _ in hits):
                winner = b if any((a.id, sa) in losing for sa, _, _ in hits) else a
                text = f"settled: a conflicting statement of {(a if winner is b else b).id} was already overruled"
        details = [f"{r}: \"{sa[:70]}\" vs \"{sb[:70]}\"" for sa, sb, r in hits]
        found.append(Contradiction((a.id, b.id), details, winner.id if winner else None, text))
    return found, losing

