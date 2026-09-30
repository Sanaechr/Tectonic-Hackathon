"""Pure text helpers: normalisation, stems, names, values, sentences, question analysis."""
from __future__ import annotations

import re
import unicodedata

from config import COUNTRIES, COUNTRY_WORDS, MONTHS, NEGATIONS, STOPWORDS


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def stems(text: str, drop_country: bool = True) -> set[str]:
    """Crude stems (first 5 letters): change/changes/changing -> 'chang'."""
    out = set()
    text = re.sub(r"\bgo[\s-]+live\b", "golive", norm(text))
    for tok in re.findall(r"[a-z0-9]+", text):
        if tok in STOPWORDS or tok in MONTHS or len(tok) < 3 or tok.isdigit():
            continue
        if drop_country and tok in COUNTRY_WORDS:
            continue
        if tok.endswith("ies"):
            tok = tok[:-3] + "y"
        elif tok.endswith("s") and not tok.endswith("ss") and len(tok) > 3:
            tok = tok[:-1]
        out.add(tok[:5])
    return out


def proper_names(text: str) -> set[str]:
    """Capitalised words that do not start a sentence (people, places, companies)."""
    out = set()
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        words = re.findall(r"[^\W\d_][\w'-]*", sentence)
        for w in words[1:]:
            n = norm(w)
            if w[0].isupper() and not w.isupper() and len(w) > 2 and n not in MONTHS and n not in STOPWORDS:
                out.add(n[:6])
    return out


def value_tokens(text: str) -> set[str]:
    """Numbers and dates in a canonical form, so that '23 November 2026', '23/11/2026'
    and '2026-11-23' are equal and '480,000' equals '480.000'."""
    t = norm(text)
    toks: set[str] = set()

    def add_date(y, m, d):
        toks.add(f"{int(y):04d}-{int(m):02d}-{int(d):02d}")

    def grab(pattern, fn):
        nonlocal t
        t = re.sub(pattern, lambda m: (fn(m), " ")[1], t)

    months = "|".join(sorted(MONTHS, key=len, reverse=True))
    t = re.sub(r"\b[a-z]{2,4}-[\d-]+\b", " ", t)                                   # ids: INV-2026-0145, CR-07
    t = re.sub(r"\biso\s*\d{3,5}\b", " ", t)                                        # standard names: ISO 27001
    t = re.sub(r"\b(risk|milestone|article|step|item|point|phase|week|section)s?\s+\d{1,2}\b", " ", t)  # list labels
    grab(r"\b(\d{4})-(\d{2})-(\d{2})\b", lambda m: add_date(m[1], m[2], m[3]))
    grab(r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{4})\b", lambda m: add_date(m[3], m[2], m[1]))
    grab(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({months})\b\.?,?\s+(\d{{4}})\b",
         lambda m: add_date(m[3], MONTHS[m[2]], m[1]))
    grab(rf"\b({months})\b\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})\b",
         lambda m: add_date(m[3], MONTHS[m[1]], m[2]))
    t = re.sub(rf"\b({months})\b\.?\s+\d{{4}}\b", " ", t)                          # 'October 2026' (too coarse)
    t = re.sub(r"\b(be|fr)\s?(?=\d)", "", t)                 # VAT prefixes
    t = re.sub(r"(?<=\d)[,.](?=\d{3}(?!\d))", "", t)        # thousands separators
    toks |= set(re.findall(r"(?<![a-z0-9])\d+(?:[.,]\d+)?(?::\d{2})?", t))
    return toks


def has_negation(text: str) -> bool:
    return bool(set(re.findall(r"[a-z]+", norm(text))) & NEGATIONS)


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


def split_sentences(text: str) -> list[str]:
    chunks = re.split(r"\n(?=\s*[-•*]\s)", text.strip())      # one chunk per bullet
    out = []
    for chunk in chunks:
        chunk = re.sub(r"^\s*[-•*]\s+", "", chunk)
        chunk = re.sub(r"\s*\n\s*", " ", chunk).strip()
        out += re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-Ý0-9\"(])", chunk)
    return [s.strip() for s in out if len(s.strip()) > 15 and not s.strip().endswith("?")]


def detect_country(question: str) -> str | None:
    q = norm(question)
    for country, words in COUNTRIES.items():
        if any(re.search(rf"\b{w}\b", q) for w in words):
            return country
    return None


def question_topic(question: str) -> set[str]:
    """Question keywords without the entity names (company, project) that appear in every document."""
    entity: set[str] = set()
    for name in proper_names(question):
        entity |= stems(name)
    topic = stems(question) - entity
    return topic or stems(question)
