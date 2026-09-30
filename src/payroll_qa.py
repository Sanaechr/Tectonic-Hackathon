#!/usr/bin/env python3
"""
Trust-aware document summarizer.

An employee asks a question about a client company / project. The program receives every
document found in the database (PDF content + metadata + trust score) and returns an
aggregated answer made only of text extracted from those documents. Every sentence of the
answer can be traced back to its source document(s).

Pipeline
--------
1. Load        : test_cases.json, owners.json, PDFs (data/pdf/<file name>)
2. Guardrail   : if the best trust score is below MIN_SCORE -> refuse to answer
                 (no PDF is read, no AI is called) and suggest an expert
3. Filter      : drop documents from another country and documents unrelated to the question
4. Contradictions : compare sentences across documents (numbers, dates, names, negations)
                 and resolve them with trust score + recency; unclear cases are flagged
5. Aggregate   : keep the most relevant sentences of the reliable documents, merge duplicates
                 (redundant sources are listed together), drop sentences that lose a contradiction
   Passage trust: each statement gets its own trust score (source score + corroboration bonus
                 - staleness penalty); the answer is sorted by it and weak statements are flagged
6. Confidence  : high / medium / low / insufficient
7. Traceability: --explain DOC-001, or --interactive ("source 2", "doc DOC-001")

Without an API key the aggregation is purely extractive (nothing can be invented).
With --llm (ANTHROPIC_API_KEY + `pip install anthropic`) a model rewrites ONLY the selected
passages and must keep the [DOC-xxx] citations.

Usage
-----
  python trusted_doc_qa.py --data data                     # all cases + automatic evaluation
  python trusted_doc_qa.py --data data --case project_budget
  python trusted_doc_qa.py --data data --case project_budget --interactive
  python trusted_doc_qa.py --data data --case project_budget --question "..."   # free question
  python trusted_doc_qa.py --data data --json
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import date
from math import log
from pathlib import Path

# --------------------------------------------------------------------------- #
# Parameters
# --------------------------------------------------------------------------- #
MIN_SCORE = 50            # below: document unusable; best score below: refuse to answer
STRONG_SCORE = 70         # a "solid" document
CONTRADICTION_GAP = 15    # minimal score gap to settle a contradiction by score alone
RECENCY_DAYS = 30         # "noticeably more recent"
TRUSTED_NEWER = 60        # a newer document with at least this score is never silently overruled
MIN_DOC_COVERAGE = 0.12   # share of the question keywords a document must cover (and >= 1 keyword)
SENT_MIN_RATIO = 0.20     # sentence relevance threshold (or >= 2 shared keywords)
FACT_MIN_RATIO = 0.08     # lower threshold for sentences carrying a value or a name
OVERLAP_VALUES = 0.30     # overlap coefficient needed to compare two sentences on values
OVERLAP_NAMES = 0.50      # stricter for name/place conflicts
DEDUP_JACCARD = 0.70      # sentences at least this similar are the same information
CONTRA_JACCARD = 0.25     # topic similarity needed to compare two sentences
NEGATION_JACCARD = 0.30   # similarity needed for negation-only conflicts
MAX_PASSAGES = 12
CORROBORATION_BONUS = 5   # trust bonus per additional document stating the same thing
STALE_DAYS = 365          # a source not modified for longer than this (vs the newest source) is "stale"
STALE_PENALTY = 10        # trust penalty applied to a stale source

STOPWORDS = set("""
a an the of to in on at for from by with and or but if then than that this these those is are was were be been being
can could should would will shall may might do does did it its as into about which what when where who whom how
until before after during through their there here they them he she his her you your we our us i me my not no
all any some more most other such only own same so too very just also each many much whose via per between within whether
""".split())

COUNTRIES = {
    "Belgium": ["belgium", "belgian"],
    "France": ["france", "french"],
    "Germany": ["germany", "german"],
    "Netherlands": ["netherlands", "dutch"],
    "Luxembourg": ["luxembourg"],
}
COUNTRY_WORDS = {w for ws in COUNTRIES.values() for w in ws}
NEGATIONS = {"no", "not", "never", "without", "cannot", "neither", "nor"}
MONTHS = {m: i for i, names in enumerate(
    ["january jan", "february feb", "march mar", "april apr", "may", "june jun", "july jul",
     "august aug", "september sep sept", "october oct", "november nov", "december dec"], 1)
    for m in names.split()}

# Words that turn a number into a *different quantity* ("remaining" vs "total", "planned" vs "actual")
QUALIFIER_WORDS = "remaining total planned estimated original previous initial interim draft"


# --------------------------------------------------------------------------- #
# Text utilities
# --------------------------------------------------------------------------- #
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


# --------------------------------------------------------------------------- #
# PDF reading
# --------------------------------------------------------------------------- #
def read_pdf(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        from pypdf import PdfReader
        return "\n".join((p.extract_text() or "") for p in PdfReader(str(path)).pages)
    except ImportError:
        pass
    try:
        import pdfplumber
        with pdfplumber.open(str(path)) as pdf:
            return "\n".join((p.extract_text() or "") for p in pdf.pages)
    except ImportError:
        pass
    if shutil.which("pdftotext"):
        return subprocess.run(["pdftotext", "-layout", str(path), "-"],
                              capture_output=True, text=True).stdout
    raise RuntimeError("No PDF reader found: pip install pypdf")


def strip_header(text: str) -> str:
    """Remove the repeated header (title + 'Type: ... | Owner: ...' line)."""
    lines = [l for l in text.splitlines() if l.strip()]
    for i, line in enumerate(lines[:4]):
        if re.match(r"\s*Type:", line):
            return "\n".join(lines[i + 1:])
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #
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


# --------------------------------------------------------------------------- #
# Pipeline steps
# --------------------------------------------------------------------------- #
def load_docs(case_input: dict, data_dir: Path, read_text: bool) -> list[Doc]:
    docs = []
    for meta in case_input["documents"]:
        doc = Doc(meta)
        if read_text:
            doc.text = strip_header(read_pdf(data_dir / "pdf" / Path(meta["file"]).name))
        docs.append(doc)
    return docs


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


def suggest_experts(question: str, docs: list[Doc], owners: dict, country: str | None, k: int = 2) -> list[dict]:
    """Rank owners by expertise overlap with the question + the titles of the documents found."""
    query = stems(question + " " + " ".join(d.meta["title"] for d in docs))
    domains = {oid: stems(" ".join(o["expertise_domains"]), False) for oid, o in owners.items()}
    df: dict[str, int] = {}
    for ds in domains.values():
        for s in ds:
            df[s] = df.get(s, 0) + 1
    seniority = {"junior": 0, "mid": 0.1, "senior": 0.2, "expert": 0.3}
    ranked = []
    for oid, o in owners.items():
        common = query & domains[oid]
        sc = sum(log(1 + len(owners) / df[s]) for s in common)
        if sc > 0:
            sc += seniority.get(o["seniority_level"], 0) + (0.3 if o["country"] == country else 0)
            ranked.append((sc, o, sorted(common)))
    ranked.sort(key=lambda x: -x[0])
    return [{"owner_id": o["owner_id"], "name": o["name"], "job_title": o["job_title"],
             "email": o["email"], "matching_keywords": c} for _, o, c in ranked[:k]]


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


def passage_trust(p: Passage, docs_by_id: dict[str, Doc], ref_day: date) -> int:
    """Trust of ONE statement, not just of its document:
    source score + bonus for each independent document that corroborates it
    - penalty if the source is stale compared with the newest usable document."""
    src = docs_by_id[p.doc_id]
    trust = src.score + CORROBORATION_BONUS * len(set(p.also_in) - {p.doc_id})
    if (ref_day - src.day).days > STALE_DAYS:
        trust -= STALE_PENALTY
    return max(0, min(100, trust))


def llm_synthesis(question: str, passages: list[Passage]) -> str | None:
    try:
        import anthropic
        client = anthropic.Anthropic()
    except Exception:
        return None
    src = "\n".join(f"[{', '.join([p.doc_id] + p.also_in)}] {p.text}" for p in passages)
    prompt = (f"Question: {question}\n\nPassages (the only allowed source):\n{src}\n\n"
              "Write a concise answer in the language of the question. Use ONLY these passages, invent nothing, "
              "and cite the source [DOC-xxx] after each statement.")
    msg = client.messages.create(model="claude-sonnet-4-6", max_tokens=1000,
                                 messages=[{"role": "user", "content": prompt}])
    return msg.content[0].text


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def answer_case(case: dict, data_dir: Path, owners: dict, question: str | None = None,
                use_llm: bool = False) -> Result:
    question = question or case["input"]["question"]
    country = detect_country(question)
    warnings: list[str] = []

    # --- Guardrail: runs BEFORE any PDF is read or any AI is called ----------
    best = max(m["trust_score"] for m in case["input"]["documents"])
    if best < MIN_SCORE:
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

    docs = load_docs(case["input"], data_dir, read_text=True)
    for d in docs:
        if not d.text:
            warnings.append(f"PDF missing or empty for {d.id} ({Path(d.meta['file']).name})")

    topic = question_topic(question)
    qnames = proper_names(question)
    excluded: dict[str, str] = {}

    # --- Filter: country + relevance ------------------------------------------
    candidates = []
    for d in docs:
        if country and d.meta.get("country") != country:
            excluded[d.id] = f"country {d.meta['country']} != {country}"
        elif not d.text:
            excluded[d.id] = "content unavailable"
        elif not doc_matches(d, topic) or len(doc_matches(d, topic)) / len(topic) < MIN_DOC_COVERAGE:
            excluded[d.id] = "not relevant to the question"
        else:
            candidates.append(d)

    # --- Contradictions (weak documents included: they explain why something is rejected)
    contradictions, losing = find_contradictions(candidates, topic, qnames)
    rejected_docs = {c.between[0] if c.winner == c.between[1] else c.between[1]
                     for c in contradictions if c.winner}

    usable = []
    for d in candidates:
        if d.score < MIN_SCORE:
            excluded[d.id] = f"score {d.score} < {MIN_SCORE}" + (
                "; contradicts a more reliable document" if d.id in rejected_docs else "")
        else:
            usable.append(d)

    # --- Passage selection -----------------------------------------------------
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
    # Passage-level trust: the most reliable statements come first
    if passages:
        docs_by_id = {d.id: d for d in usable}
        ref_day = max(d.day for d in usable)
        for p in passages:
            p.trust = passage_trust(p, docs_by_id, ref_day)
        passages.sort(key=lambda p: (-p.trust, -p.relevance))
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

    # --- Answer ------------------------------------------------------------------
    answer = llm_synthesis(question, passages) if use_llm else None
    if not answer:
        answer = "\n".join(
            f"- {p.text} [{', '.join([p.doc_id] + p.also_in)}] (trust {p.trust}"
            + ("" if p.trust >= STRONG_SCORE else ", to verify") + ")"
            for p in passages)
    if contradictions:
        answer += "\n\nDisagreements between sources:"
        for c in contradictions:
            answer += f"\n- {c.between[0]} vs {c.between[1]}: {c.resolution}."
    return Result(case["id"], question, confidence, answer, used_ids, passages, contradictions,
                  excluded, warnings, [])


# --------------------------------------------------------------------------- #
# Traceability and reporting
# --------------------------------------------------------------------------- #
def explain(doc_id: str, case: dict, owners: dict, result: Result | None = None) -> str:
    meta = next((m for m in case["input"]["documents"] if m["id"] == doc_id), None)
    if not meta:
        return f"Unknown document {doc_id}."
    o = owners.get(meta.get("owner_id"))
    owner = f"{o['name']} ({o['job_title']}, {o['email']})" if o else "not identified"
    lines = [f"{doc_id} - {meta['title']}",
             f"  Type / country : {meta['type']} / {meta['country']}",
             f"  Created        : {meta['created_date']}   Last modified: {meta['last_modified_date']}",
             f"  Owner          : {owner}",
             f"  Trust score    : {meta['trust_score']}",
             "  Trust reasons  : " + "; ".join(meta["trust_reasons"]),
             f"  File           : {meta['file']}"]
    if result:
        used = [p for p in result.passages if doc_id == p.doc_id or doc_id in p.also_in]
        if used:
            lines.append("  Passages used  :")
            lines += [f"    * {p.text}" for p in used]
        elif doc_id in result.excluded:
            lines.append(f"  Not used       : {result.excluded[doc_id]}")
    return "\n".join(lines)


def print_result(r: Result, case: dict):
    print(f"\n{'=' * 80}\n[{r.case_id}] {case['name']}\nQuestion  : {r.question}\nConfidence: {r.confidence.upper()}\n{'-' * 80}")
    print(r.answer)
    if r.passages:
        print("\nSources:")
        for i, p in enumerate(r.passages, 1):
            ids = ", ".join([p.doc_id] + p.also_in)
            print(f"  [{i}] {ids}  (passage trust {p.trust})")
    if r.contradictions:
        print("\nContradictions detected:")
        for c in r.contradictions:
            print(f"  - {c.between[0]} vs {c.between[1]} -> {c.resolution}")
            for d in c.details[:3]:
                print(f"      {d}")
    if r.excluded:
        print("\nDocuments not used:")
        for k, v in r.excluded.items():
            print(f"  - {k}: {v}")
    if r.suggested_experts:
        print("\nSuggested experts:")
        for e in r.suggested_experts:
            print(f"  - {e['name']} ({e['owner_id']}), {e['job_title']} - {e['email']}")
    for w in r.warnings:
        print(f"WARNING: {w}")


def evaluate(r: Result, case: dict, llm: bool = False) -> list[str]:
    exp, issues = case["expected"], []
    if r.confidence not in exp["confidence_level"]:
        issues.append(f"confidence {r.confidence} != expected '{exp['confidence_level']}'")
    used = set(r.used_docs)
    if set(exp["documents_that_must_be_used"]) - used:
        issues.append(f"required documents not used: {sorted(set(exp['documents_that_must_be_used']) - used)}")
    if used & set(exp.get("documents_that_must_not_be_used", [])):
        issues.append(f"forbidden documents used: {sorted(used & set(exp['documents_that_must_not_be_used']))}")
    flagged = [set(c.between) for c in r.contradictions]
    for c in exp["expected_contradictions"]:
        if set(c["between"]) not in flagged:
            issues.append(f"contradiction not detected: {c['between']}")
    if exp["confidence_level"] == "insufficient" and r.passages:
        issues.append("an answer was generated although it should have been refused")
    if exp.get("suggested_expert_id") and (
            not r.suggested_experts or r.suggested_experts[0]["owner_id"] != exp["suggested_expert_id"]):
        issues.append(f"expert {exp['suggested_expert_id']} not suggested first")
    if not llm:
        body = norm("\n".join(p.text for p in r.passages))
        for item in exp.get("must_contain", []):
            if not any(norm(alt) in body for alt in item.split("|")):
                issues.append(f"missing in answer: '{item}'")
        for item in exp.get("must_not_contain", []):
            if norm(item) in body:
                issues.append(f"forbidden content in answer: '{item}'")
    return issues


def interactive(r: Result, case: dict, owners: dict):
    print("\nType 'source N', 'doc DOC-001' or 'q' to quit.")
    while True:
        cmd = input("> ").strip()
        if cmd in ("q", "quit", ""):
            break
        m = re.match(r"source\s+(\d+)$", cmd)
        if m and 0 < int(m.group(1)) <= len(r.passages):
            p = r.passages[int(m.group(1)) - 1]
            print(f"Passage: {p.text}")
            for d in [p.doc_id] + p.also_in:
                print(explain(d, case, owners, r))
        elif cmd.lower().startswith("doc "):
            print(explain(cmd.split()[1].upper(), case, owners, r))
        else:
            print("Unknown command.")


def main():
    ap = argparse.ArgumentParser(description="Trust-aware document summarizer")
    ap.add_argument("--data", default="data", help="folder with owners.json, test_cases.json and pdf/")
    ap.add_argument("--case", help="run a single case id")
    ap.add_argument("--question", help="ask a free question on the documents of --case")
    ap.add_argument("--llm", action="store_true", help="rewrite the selected passages with an LLM")
    ap.add_argument("--explain", help="show the metadata and passages of a document (e.g. DOC-001)")
    ap.add_argument("--interactive", action="store_true", help="ask for the source of each answer element")
    ap.add_argument("--json", action="store_true", help="print results as JSON")
    a = ap.parse_args()

    data = Path(a.data)
    owners = {o["owner_id"]: o for o in json.loads((data / "owners.json").read_text("utf-8"))["owners"]}
    cases = json.loads((data / "test_cases.json").read_text("utf-8"))["cases"]
    if a.case:
        cases = [c for c in cases if c["id"] == a.case]
    if a.question and not a.case:
        raise SystemExit("--question requires --case (to choose the document set)")

    passed = 0
    for case in cases:
        r = answer_case(case, data, owners, a.question, a.llm)
        if a.json:
            print(json.dumps(asdict(r), indent=2, ensure_ascii=False))
            continue
        print_result(r, case)
        if a.explain:
            print("\n" + explain(a.explain, case, owners, r))
        if not a.question:
            issues = evaluate(r, case, a.llm)
            passed += not issues
            print("\nEvaluation:", "PASS - matches expectations" if not issues else "FAIL - " + " | ".join(issues))
        if a.interactive:
            interactive(r, case, owners)
    if len(cases) > 1 and not a.json and not a.question:
        print(f"\n{'=' * 80}\nSummary: {passed}/{len(cases)} cases match the expectations")


if __name__ == "__main__":
    main()