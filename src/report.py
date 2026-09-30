"""Traceability and console reporting: explain a document, print a result, interactive sources."""
from __future__ import annotations

import re

from models import Result


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

