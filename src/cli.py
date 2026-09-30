"""Command-line interface: parse arguments, run the cases, print / evaluate."""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from evaluation import evaluate
from loader import load_cases, load_owners
from pipeline import answer_case
from report import explain, interactive, print_result


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Trust-aware document summarizer")
    ap.add_argument("--data", default="data", help="folder with owners.json, test_cases.json and pdf/")
    ap.add_argument("--case", help="run a single case id")
    ap.add_argument("--question", help="ask a free question on the documents of --case")
    ap.add_argument("--llm", action="store_true", help="rewrite the selected passages with an LLM")
    ap.add_argument("--explain", help="show the metadata and passages of a document (e.g. DOC-001)")
    ap.add_argument("--interactive", action="store_true", help="ask for the source of each answer element")
    ap.add_argument("--json", action="store_true", help="print results as JSON")
    return ap


def main():
    a = build_parser().parse_args()

    data = Path(a.data)
    owners = load_owners(data)
    cases = load_cases(data)
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
