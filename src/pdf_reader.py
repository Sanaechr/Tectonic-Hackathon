"""PDF reading: extract the raw text of a file and strip its repeated header."""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path


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
