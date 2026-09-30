"""Data loading: owners, test cases and the documents of a case (metadata + PDF text)."""
from __future__ import annotations

import json
from pathlib import Path

from models import Doc
from pdf_reader import read_pdf, strip_header


def load_owners(data_dir: Path) -> dict:
    return {o["owner_id"]: o for o in json.loads((data_dir / "owners.json").read_text("utf-8"))["owners"]}


def load_cases(data_dir: Path) -> list[dict]:
    return json.loads((data_dir / "test_cases.json").read_text("utf-8"))["cases"]


def load_docs(case_input: dict, data_dir: Path, read_text: bool) -> list[Doc]:
    docs = []
    for meta in case_input["documents"]:
        doc = Doc(meta)
        if read_text:
            doc.text = strip_header(read_pdf(data_dir / "pdf" / Path(meta["file"]).name))
        docs.append(doc)
    return docs
