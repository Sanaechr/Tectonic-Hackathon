"""Automatic evaluation of a result against the expectations of a test case."""
from __future__ import annotations

from models import Result
from text_utils import norm


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

