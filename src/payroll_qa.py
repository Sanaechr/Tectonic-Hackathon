#!/usr/bin/env python3
"""
Trust-aware document summarizer - entry point.

An employee asks a question about a client company / project. The program receives every
document found in the database (PDF content + metadata + trust score) and returns an
aggregated answer made only of text extracted from those documents, each statement carrying
its own trust score and traceable to its source document(s).

Modules (one responsibility each)
---------------------------------
  config.py          parameters and static vocabularies
  text_utils.py      normalisation, stems, names, values, sentences, question analysis
  pdf_reader.py      PDF text extraction
  models.py          Doc, Passage, Contradiction, Result
  loader.py          owners, test cases, documents
  contradictions.py  contradiction detection and resolution (trust score + recency)
  passages.py        sentence relevance, selection, deduplication, passage-level trust
  experts.py         expert suggestion
  confidence.py      confidence level
  llm.py             optional LLM rewriting
  answer_builder.py  final answer text
  pipeline.py        chains the steps for one case (guardrail -> ... -> answer)
  report.py          explain / print / interactive traceability
  evaluation.py      evaluation against expected results
  cli.py             argument parsing and main loop

Usage (from the src/ folder)
----------------------------
  python payroll_qa.py --data ../data
  python payroll_qa.py --data ../data --case project_budget
  python payroll_qa.py --data ../data --case project_budget --interactive
  python payroll_qa.py --data ../data --case project_budget --question "..."
  python payroll_qa.py --data ../data --json
"""
from cli import main

if __name__ == "__main__":
    main()
