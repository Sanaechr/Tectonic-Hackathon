"""Optional LLM rewriting of the selected passages (never the source of facts)."""
from __future__ import annotations

from models import Passage


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

