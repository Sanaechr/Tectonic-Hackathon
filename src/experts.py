"""Expert suggestion: rank document owners by expertise overlap with the question."""
from __future__ import annotations

from math import log

from models import Doc
from text_utils import stems


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

