"""Pre-processing: strip code fences, chunk large documents, context injection."""
from __future__ import annotations

import pathlib
import re
from dataclasses import dataclass

TOKEN_THRESHOLD = 6_000
CHARS_PER_TOKEN = 4  # rough estimate


@dataclass
class DocumentChunk:
    text: str
    source_document: str
    source_section: str | None = None   # H1 title this chunk belongs to


def strip_code_fence(text: str) -> str:
    """Strip leading/trailing ```markdown ... ``` wrapper if present."""
    stripped = text.strip()
    pattern = r'^```(?:markdown)?\s*\n([\s\S]*?)\n```\s*$'
    match = re.match(pattern, stripped)
    return match.group(1) if match else text


def count_tokens(text: str) -> int:
    """Rough token count: 4 chars ≈ 1 token."""
    return len(text) // CHARS_PER_TOKEN


def _clean_title(raw: str) -> str:
    """Strip markdown formatting and anchor IDs from a heading line."""
    t = raw.strip().lstrip('#').strip()
    t = re.sub(r'\{#[^}]*\}', '', t)          # {#anchor-id}
    t = re.sub(r'\*\*([^*]+)\*\*', r'\1', t)  # **bold**
    t = re.sub(r'\*([^*]+)\*', r'\1', t)       # *italic*
    return t.strip()


def split_on_h1(text: str, doc_name: str) -> list[DocumentChunk]:
    """Split document on H1 headings into one chunk per major section.

    Each chunk is prefixed with 'Document: <doc_name>' so the LLM always
    knows the document context when processing a chunk in isolation.
    """
    h1_re = re.compile(r'^# .+$', re.MULTILINE)
    h1_matches = list(h1_re.finditer(text))

    if not h1_matches:
        return [DocumentChunk(text=text, source_document=doc_name)]

    chunks: list[DocumentChunk] = []

    # Preamble before first H1 (rare but possible)
    pre = text[:h1_matches[0].start()].strip()
    if pre and count_tokens(pre) > 50:
        chunks.append(DocumentChunk(
            text=f"Document: {doc_name}\n{pre}",
            source_document=doc_name,
            source_section=None,
        ))

    for i, m in enumerate(h1_matches):
        end = h1_matches[i + 1].start() if i + 1 < len(h1_matches) else len(text)
        chunk_body = text[m.start():end].strip()
        h1_title = _clean_title(chunk_body.splitlines()[0])

        chunks.append(DocumentChunk(
            text=f"Document: {doc_name}\n{chunk_body}",
            source_document=doc_name,
            source_section=h1_title,
        ))

    return chunks


def prepare_chunks(text: str, doc_name: str) -> list[DocumentChunk]:
    """Return chunks ready for LLM processing. Splits on H1 if document is large."""
    if count_tokens(text) > TOKEN_THRESHOLD:
        return split_on_h1(text, doc_name)
    return [DocumentChunk(text=text, source_document=doc_name)]


def load_document(path: pathlib.Path) -> tuple[str, str]:
    """Load document, strip code fence, return (text, doc_name)."""
    text = path.read_text(encoding="utf-8")
    text = strip_code_fence(text)
    return text, path.stem
