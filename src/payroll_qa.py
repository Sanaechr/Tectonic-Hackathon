#!/usr/bin/env python3
"""
Synthèse fiable de documents pour répondre à une question d'un employé.

Pipeline
--------
1. Chargement   : test_cases.json, owners.json, PDF (data/pdf/*.pdf)
2. Garde-fou    : si le meilleur trust_score < MIN_SCORE -> on REFUSE (aucune génération)
3. Filtrage     : pays applicable + pertinence par rapport à la question
4. Contradictions : comparaison des phrases entre documents (chiffres / négations),
                   résolution par trust_score puis par date
5. Agrégation   : phrases les plus pertinentes des documents retenus, dédupliquées,
                   chacune TRACÉE vers sa source (doc, date, owner, score)
6. Confiance    : high / medium / low / insufficient
7. Traçabilité  : --explain DOC-001 ou mode --interactive ("source 2")

Sans clé API, l'agrégation est extractive (aucune invention possible).
Avec --llm (ANTHROPIC_API_KEY + pip install anthropic), un LLM reformule
UNIQUEMENT les passages sélectionnés, en gardant les citations [DOC-xxx].

Usage
-----
  python payroll_qa.py --data data                       # tous les cas + évaluation
  python payroll_qa.py --data data --case clear_case
  python payroll_qa.py --data data --case clear_case --interactive
  python payroll_qa.py --data data --question "..." --case clear_case   # question libre
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import unicodedata
from dataclasses import dataclass, field
from math import log
from pathlib import Path

# --------------------------------------------------------------------------- #
# Paramètres
# --------------------------------------------------------------------------- #
MIN_SCORE = 50            # en dessous : document inutilisable ; meilleur score < seuil -> refus
STRONG_SCORE = 70         # document considéré "solide"
CONTRADICTION_GAP = 15    # écart de score minimal pour trancher une contradiction
MIN_DOC_COVERAGE = 0.25   # part des mots-clés de la question couverts par le document
SENT_MIN_RATIO = 0.20     # pertinence minimale d'une phrase (ou >= 2 mots-clés communs)
DEDUP_JACCARD = 0.70
CONTRA_JACCARD = 0.25

STOPWORDS = set("""
a an the of to in on at for from by with and or but if then than that this these those is are was were be been
can could should would will shall may might do does did it its as into about which what when where who whom how
until before after during through their there here they them he she his her you your we our us i me my not no
until when send sent via per all any some more most other such only own same so too very just also
le la les un une des du de d l et ou mais si que qui quoi dont où quand comment pour par avec sans sur sous dans
en au aux ce cet cette ces son sa ses leur leurs est sont etre été peut peuvent doit doivent il elle ils elles
je tu nous vous ne pas plus jusqu quel quelle quels quelles
""".split())

COUNTRIES = {
    "Belgium": ["belgium", "belgian", "belgique", "belge", "belges", "belgie", "belgisch"],
    "Germany": ["germany", "german", "allemagne", "allemand", "deutschland"],
    "France": ["france", "french", "francais", "française"],
    "Netherlands": ["netherlands", "dutch", "pays-bas", "nederland"],
}
COUNTRY_WORDS = {w for ws in COUNTRIES.values() for w in ws}
NEGATIONS = {"no", "not", "never", "without", "cannot", "pas", "sans", "jamais", "aucun", "non"}


# --------------------------------------------------------------------------- #
# Texte
# --------------------------------------------------------------------------- #
def norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def stems(text: str, drop_country: bool = True) -> set[str]:
    out = set()
    for tok in re.findall(r"[a-z0-9]+", norm(text)):
        if tok in STOPWORDS or len(tok) < 3:
            continue
        if drop_country and tok in COUNTRY_WORDS:
            continue
        if tok.isdigit():
            continue
        out.add(tok[:5])  # racinisation grossière (change/changes/changing -> chang)
    return out


def numbers(text: str) -> set[str]:
    return set(re.findall(r"\b\d+(?::\d+)?\b", text))


def has_negation(text: str) -> bool:
    return bool(set(re.findall(r"[a-z]+", norm(text))) & NEGATIONS)


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s*\n\s*", " ", text.strip())
    parts = re.split(r"(?<=[.!?;])\s+(?=[A-Z0-9À-Ý\"(])", text)
    return [p.strip() for p in parts if len(p.strip()) > 15]


def detect_country(question: str) -> str | None:
    q = norm(question)
    for country, words in COUNTRIES.items():
        if any(re.search(rf"\b{re.escape(w)}\b", q) for w in words):
            return country
    return None


# --------------------------------------------------------------------------- #
# PDF
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
    raise RuntimeError("Installez pypdf : pip install pypdf")


def clean_body(text: str, title: str) -> str:
    """Retire l'en-tête (titre + ligne 'Type: ... | Owner: ...') répété dans le PDF."""
    lines = [l for l in text.splitlines()
             if l.strip() and l.strip() != title and not re.match(r"^\s*Type:", l)]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Modèles
# --------------------------------------------------------------------------- #
@dataclass
class Doc:
    meta: dict
    text: str = ""
    owner: dict | None = None

    @property
    def id(self): return self.meta["id"]
    @property
    def score(self): return self.meta["trust_score"]
    @property
    def date(self): return self.meta["last_modified_date"]


@dataclass
class Passage:
    doc_id: str
    text: str
    relevance: float
    also_in: list[str] = field(default_factory=list)


@dataclass
class Contradiction:
    between: tuple[str, str]
    subject: str
    winner: str | None
    resolution: str
    losing_sentence: str = ""


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
# Étapes du pipeline
# --------------------------------------------------------------------------- #
def load_docs(case_input: dict, data_dir: Path, owners: dict, read_text: bool) -> list[Doc]:
    docs = []
    for meta in case_input["documents"]:
        d = Doc(meta=meta, owner=owners.get(meta.get("owner_id")))
        if read_text:
            pdf = data_dir / "pdf" / Path(meta["file"]).name
            raw = read_pdf(pdf)
            d.text = clean_body(raw, meta["title"])
        docs.append(d)
    return docs


def doc_coverage(doc: Doc, qstems: set[str]) -> float:
    dstems = stems(doc.meta["title"] + " " + doc.text)
    return len(qstems & dstems) / len(qstems) if qstems else 0.0


def score_sentences(doc: Doc, qstems: set[str]) -> list[Passage]:
    out = []
    for s in split_sentences(doc.text):
        common = qstems & stems(s)
        ratio = len(common) / len(qstems) if qstems else 0
        if ratio >= SENT_MIN_RATIO or len(common) >= 2:
            out.append(Passage(doc.id, s, ratio))
    return out


def find_contradictions(docs: list[Doc], qstems: set[str]) -> list[Contradiction]:
    """Deux phrases de documents différents qui parlent du même sujet mais divergent
    sur les chiffres ou sur une négation -> contradiction."""
    found, seen = [], set()
    sents = {d.id: [(s, stems(s), numbers(s)) for s in split_sentences(d.text)] for d in docs}
    by_id = {d.id: d for d in docs}
    ids = list(sents)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            for sa, sta, na in sents[a]:
                for sb, stb, nb in sents[b]:
                    shared = (sta & stb) - set()  # sujet commun
                    if len(shared) < 2 or jaccard(sta, stb) < CONTRA_JACCARD:
                        continue
                    num_diff = (na or nb) and na != nb
                    neg_diff = has_negation(sa) != has_negation(sb)
                    if not (num_diff or neg_diff):
                        continue
                    key = (a, b, sa, sb)
                    if key in seen:
                        continue
                    seen.add(key)
                    da, db = by_id[a], by_id[b]
                    gap = da.score - db.score
                    if abs(gap) >= CONTRADICTION_GAP:
                        win, lose = (da, db) if gap > 0 else (db, da)
                        loser_s = sb if win is da else sa
                        res = (f"{win.id} retenu (score {win.score} vs {lose.score}"
                               f"{', plus récent' if win.date >= lose.date else ''}"
                               f"{', propriétaire identifié' if win.meta.get('owner_id') and not lose.meta.get('owner_id') else ''})")
                        found.append(Contradiction((a, b), _subject(num_diff, neg_diff, na, nb),
                                                   win.id, res, loser_s))
                    else:
                        found.append(Contradiction((a, b), _subject(num_diff, neg_diff, na, nb),
                                                   None, "Non résolue : scores trop proches, à faire valider"))
    return found


def _subject(num_diff, neg_diff, na, nb) -> str:
    bits = []
    if num_diff:
        bits.append(f"valeurs différentes ({', '.join(sorted(na))} vs {', '.join(sorted(nb))})")
    if neg_diff:
        bits.append("affirmation vs négation")
    return " ; ".join(bits)


def suggest_experts(question: str, docs: list[Doc], owners: dict, country: str | None, k: int = 2):
    """Classe les owners par recouvrement d'expertise (question + titres des documents trouvés)."""
    query = stems(question + " " + " ".join(d.meta["title"] for d in docs))
    domains = {oid: stems(" ".join(o["expertise_domains"]), False) for oid, o in owners.items()}
    df = {}
    for ds in domains.values():
        for s in ds:
            df[s] = df.get(s, 0) + 1
    n = len(owners)
    seniority = {"junior": 0, "mid": 0.1, "senior": 0.2, "expert": 0.3}
    ranked = []
    for oid, o in owners.items():
        common = query & domains[oid]
        sc = sum(log(1 + n / df[s]) for s in common)
        if sc > 0:
            sc += seniority.get(o["seniority_level"], 0) + (0.3 if o["country"] == country else 0)
            ranked.append((sc, o, sorted(common)))
    ranked.sort(key=lambda x: -x[0])
    return [{"owner_id": o["owner_id"], "name": o["name"], "job_title": o["job_title"],
             "email": o["email"], "match": c} for _, o, c in ranked[:k]]


def compute_confidence(used: list[Doc], contradictions: list[Contradiction], n_passages: int) -> str:
    if not used or n_passages == 0:
        return "insufficient"
    best = max(d.score for d in used)
    unresolved = any(c.winner is None for c in contradictions)
    strong = [d for d in used if d.score >= STRONG_SCORE]
    if best >= 75 and len(used) >= 2 and len(strong) >= 2 and not unresolved:
        return "high"
    if best >= 60 and not unresolved:
        return "medium"
    return "low"


def llm_synthesis(question: str, passages: list[Passage]) -> str | None:
    try:
        import anthropic
        client = anthropic.Anthropic()
    except Exception:
        return None
    src = "\n".join(f"[{p.doc_id}] {p.text}" for p in passages)
    prompt = (f"Question : {question}\n\nPassages (seule source autorisée) :\n{src}\n\n"
              "Rédige une réponse concise dans la langue de la question. N'utilise QUE ces passages, "
              "n'invente rien, et cite la source [DOC-xxx] après chaque affirmation.")
    msg = client.messages.create(model="claude-sonnet-4-6", max_tokens=1000,
                                 messages=[{"role": "user", "content": prompt}])
    return msg.content[0].text


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def answer_case(case: dict, data_dir: Path, owners: dict, question: str | None = None,
                use_llm: bool = False) -> Result:
    question = question or case["input"]["question"]
    metas = case["input"]["documents"]
    country = detect_country(question)
    warnings: list[str] = []

    # --- Garde-fou (AVANT toute lecture de PDF / appel IA) -------------------
    best = max(m["trust_score"] for m in metas)
    if best < MIN_SCORE:
        docs = load_docs(case["input"], data_dir, owners, read_text=False)
        excluded = {}
        for d in docs:
            why = [f"score {d.score} < {MIN_SCORE}"]
            if country and d.meta.get("country") != country:
                why.append(f"pays {d.meta['country']} ≠ {country}")
            excluded[d.id] = ", ".join(why)
        experts = suggest_experts(question, docs, owners, country)
        msg = (f"Information insuffisante : le meilleur trust_score est {best} (seuil {MIN_SCORE}), "
               "aucun document fiable et pertinent n'a été trouvé. Aucune procédure n'est proposée. "
               "Contactez un manager ou un expert"
               + (f" (suggestion : {experts[0]['name']}, {experts[0]['job_title']}, {experts[0]['email']})."
                  if experts else "."))
        return Result(case["id"], question, "insufficient", msg, [], [], [], excluded,
                      ["Génération bloquée par le garde-fou"], experts)

    docs = load_docs(case["input"], data_dir, owners, read_text=True)
    for d in docs:
        if not d.text:
            warnings.append(f"PDF introuvable ou vide pour {d.id} ({Path(d.meta['file']).name})")

    qstems = stems(question)
    excluded: dict[str, str] = {}

    # --- Filtre pays + pertinence ------------------------------------------
    candidates = []
    for d in docs:
        if country and d.meta.get("country") != country:
            excluded[d.id] = f"pays {d.meta['country']} ≠ {country}"
        elif not d.text:
            excluded[d.id] = "contenu indisponible"
        elif doc_coverage(d, qstems) < MIN_DOC_COVERAGE:
            excluded[d.id] = "hors sujet"
        else:
            candidates.append(d)

    # --- Contradictions (y compris avec les documents faibles) --------------
    contradictions = find_contradictions(candidates, qstems)
    losing = {c.losing_sentence for c in contradictions if c.winner}
    losing_docs = {c.between[0] if c.winner == c.between[1] else c.between[1]
                   for c in contradictions if c.winner}

    usable = []
    for d in candidates:
        if d.score < MIN_SCORE:
            excluded[d.id] = f"score {d.score} < {MIN_SCORE}" + (
                " ; contredit un document plus fiable" if d.id in losing_docs else "")
        else:
            usable.append(d)

    # --- Sélection des passages ---------------------------------------------
    passages: list[Passage] = []
    for d in sorted(usable, key=lambda x: -x.score):
        for p in score_sentences(d, qstems):
            if p.text in losing:
                continue
            dup = next((q for q in passages if jaccard(stems(q.text), stems(p.text)) >= DEDUP_JACCARD), None)
            if dup:
                dup.also_in.append(p.doc_id)   # même info confirmée par une autre source
            else:
                passages.append(p)
    used_ids = sorted({p.doc_id for p in passages} | {i for p in passages for i in p.also_in})
    used = [d for d in usable if d.id in used_ids]
    for d in usable:
        if d.id not in used_ids:
            excluded[d.id] = "aucun passage pertinent"

    confidence = compute_confidence(used, contradictions, len(passages))

    # --- Réponse -------------------------------------------------------------
    if confidence == "insufficient":
        experts = suggest_experts(question, docs, owners, country)
        answer = "Information insuffisante dans les documents disponibles. Contactez un expert."
        return Result(case["id"], question, confidence, answer, [], [], contradictions,
                      excluded, warnings, experts)

    answer = llm_synthesis(question, passages) if use_llm else None
    if not answer:
        answer = "\n".join(
            f"- {p.text} [{', '.join([p.doc_id] + p.also_in)}]" for p in passages)
    if contradictions:
        answer += "\n\n⚠ Désaccords entre sources :"
        for c in contradictions:
            answer += f"\n- {c.between[0]} vs {c.between[1]} : {c.subject}. {c.resolution}."
    return Result(case["id"], question, confidence, answer, used_ids, passages, contradictions,
                  excluded, warnings, [])


# --------------------------------------------------------------------------- #
# Traçabilité
# --------------------------------------------------------------------------- #
def explain(doc_id: str, case: dict, owners: dict, result: Result | None = None) -> str:
    meta = next((m for m in case["input"]["documents"] if m["id"] == doc_id), None)
    if not meta:
        return f"Document {doc_id} inconnu."
    o = owners.get(meta.get("owner_id"))
    lines = [f"{doc_id} — {meta['title']}",
             f"  Type        : {meta['type']}   Pays : {meta['country']}",
             f"  Créé le     : {meta['created_date']}   Modifié le : {meta['last_modified_date']}",
             f"  Propriétaire: {o['name'] + ' (' + o['job_title'] + ', ' + o['email'] + ')' if o else 'non identifié'}",
             f"  Trust score : {meta['trust_score']}",
             "  Raisons     : " + "; ".join(meta["trust_reasons"]),
             f"  Fichier     : {meta['file']}"]
    if result:
        ps = [p for p in result.passages if doc_id == p.doc_id or doc_id in p.also_in]
        if ps:
            lines.append("  Passages utilisés :")
            lines += [f"    • {p.text}" for p in ps]
        elif doc_id in result.excluded:
            lines.append(f"  Non utilisé : {result.excluded[doc_id]}")
    return "\n".join(lines)


def print_result(r: Result, case: dict, owners: dict):
    print(f"\n{'=' * 78}\nQuestion : {r.question}\nConfiance : {r.confidence.upper()}\n{'-' * 78}")
    print(r.answer)
    if r.passages:
        print("\nSources :")
        for i, p in enumerate(r.passages, 1):
            m = next(x for x in case["input"]["documents"] if x["id"] == p.doc_id)
            print(f"  [{i}] {p.doc_id} (score {m['trust_score']}, modifié {m['last_modified_date']})")
    if r.excluded:
        print("\nDocuments écartés :")
        for k, v in r.excluded.items():
            print(f"  - {k} : {v}")
    if r.suggested_experts:
        print("\nExperts suggérés :")
        for e in r.suggested_experts:
            print(f"  - {e['name']} ({e['owner_id']}), {e['job_title']} — {e['email']}")
    for w in r.warnings:
        print(f"⚠ {w}")


def evaluate(r: Result, case: dict) -> list[str]:
    exp, issues = case["expected"], []
    if r.confidence not in exp["confidence_level"]:
        issues.append(f"confiance {r.confidence} ≠ attendue « {exp['confidence_level']} »")
    missing = set(exp["documents_that_must_be_used"]) - set(r.used_docs)
    if missing:
        issues.append(f"documents obligatoires non utilisés : {sorted(missing)}")
    for c in exp["expected_contradictions"]:
        if not any(set(c["between"]) == set(x.between) for x in r.contradictions):
            issues.append(f"contradiction non détectée : {c['between']}")
    if exp["confidence_level"] == "insufficient" and r.passages:
        issues.append("des passages ont été générés alors que la réponse devait être refusée")
    return issues


def interactive(r: Result, case: dict, owners: dict):
    print("\nTapez « source N », « doc DOC-001 » ou « q » pour quitter.")
    while True:
        cmd = input("> ").strip()
        if cmd in ("q", "quit", ""):
            break
        m = re.match(r"source\s+(\d+)", cmd)
        if m and 0 < int(m.group(1)) <= len(r.passages):
            p = r.passages[int(m.group(1)) - 1]
            print(f"Passage : {p.text}")
            for d in [p.doc_id] + p.also_in:
                print(explain(d, case, owners, r))
        elif cmd.lower().startswith("doc "):
            print(explain(cmd.split()[1].upper(), case, owners, r))
        else:
            print("Commande inconnue.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--case")
    ap.add_argument("--question")
    ap.add_argument("--llm", action="store_true")
    ap.add_argument("--explain")
    ap.add_argument("--interactive", action="store_true")
    a = ap.parse_args()

    data = Path(a.data)
    owners = {o["owner_id"]: o for o in json.loads((data / "owners.json").read_text("utf-8"))["owners"]}
    cases = json.loads((data / "test_cases.json").read_text("utf-8"))["cases"]
    if a.case:
        cases = [c for c in cases if c["id"] == a.case]

    for case in cases:
        r = answer_case(case, data, owners, a.question, a.llm)
        print_result(r, case, owners)
        if a.explain:
            print("\n" + explain(a.explain, case, owners, r))
        if not a.question:
            issues = evaluate(r, case)
            print("\nÉvaluation :", "✅ conforme aux attentes" if not issues else "❌ " + " | ".join(issues))
        if a.interactive:
            interactive(r, case, owners)


if __name__ == "__main__":
    main()