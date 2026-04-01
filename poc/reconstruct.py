"""Deterministic topic document reconstruction from extracted facts."""
from __future__ import annotations

from schemas import ExtractedFact


def reconstruct_topic_document(facts: list[ExtractedFact]) -> str:
    """Concatenate extracted facts into a reconstruction string for critique."""
    lines: list[str] = []
    for fact in facts:
        lines.append(f"## {fact.title}")
        lines.append("")
        lines.append(fact.content)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def topic_document_text(records: list[dict]) -> str:
    """Assemble a topic document from Pass 3 records.

    Each record is a dict with 'source_path' and 'span_text'.
    """
    lines: list[str] = []
    for record in records:
        lines.append(f"### {record['source_path']}")
        lines.append("")
        lines.append(record["span_text"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
