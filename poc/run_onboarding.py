#!/usr/bin/env python3
"""Chain A: Document → Facts (4-pass extraction)

Usage:
    python run_onboarding.py --model anthropic/claude-sonnet-4-6 --save output/corpus.json
    python run_onboarding.py --model anthropic/claude-sonnet-4-6 --doc test_doc_4_dress_code.md --save output/corpus.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from collections import defaultdict

from corpus import count_tokens, load_document, prepare_chunks
from llm import LLMProvider, call as llm_call, make_provider, render_prompt
from schemas import (
    ExtractedFact,
    FactExtractionOutput,
    ScopeInferenceOutput,
    TopicScanOutput,
)

TEST_DOCS_DIR = pathlib.Path(__file__).parent / "test_docs"


def _extract_title(text: str) -> str:
    match = re.search(r'^# (.+)$', text, re.MULTILINE)
    return match.group(1).strip() if match else "Unknown"


def _clean_heading(raw: str) -> str:
    t = raw.strip().lstrip('#').strip()
    t = re.sub(r'\{#[^}]*\}', '', t)
    t = re.sub(r'\*\*([^*]+)\*\*', r'\1', t)
    t = re.sub(r'\*([^*]+)\*', r'\1', t)
    return t.strip()


def extract_sections(text: str) -> list[dict]:
    """Deterministically split document text into sections with hierarchical source_path."""
    heading_re = re.compile(r'^(#{1,4})\s+(.+)$', re.MULTILINE)
    matches = list(heading_re.finditer(text))

    if not matches:
        return []

    sections = []
    heading_stack: list[tuple[int, str]] = []

    for i, m in enumerate(matches):
        level = len(m.group(1))
        title = _clean_heading(m.group(2))

        heading_stack = [(l, t) for l, t in heading_stack if l < level]
        heading_stack.append((level, title))
        source_path = " > ".join(t for _, t in heading_stack)

        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()

        if content:
            sections.append({
                "section_title": title,
                "source_path": source_path,
                "content": content,
            })

    return sections


def _heading_to_base_slug(section_title: str) -> str:
    """Derive a deterministic base slug from a section heading.

    Strips leading number prefixes (e.g. '2.4 ', '12. ') then converts to
    lowercase kebab-case.  The result is passed to the topic_scanning prompt
    so the LLM extends it with a suffix rather than inventing slugs wholesale.
    """
    title = re.sub(r'^[\d.]+\s+', '', section_title).strip()
    return re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')


def _make_fact_id(topic_slug: str, scope_qualifier: str | None, index: int) -> str:
    slug = re.sub(r'[^a-z0-9]+', '_', topic_slug.lower()).strip('_')
    scope = re.sub(r'[^a-z0-9]+', '_', (scope_qualifier or 'all').lower()).strip('_')
    return f"{slug}__{scope}__{index}"


def process_documents(
    paths: list[pathlib.Path],
    provider: LLMProvider,
    model: str,
) -> tuple[list[ExtractedFact], dict[tuple[str, str | None], str], dict[tuple[str, str | None], list[dict]]]:
    """Run the 4-pass extraction pipeline across all documents.

    Returns:
        facts: all extracted facts
        topic_docs: assembled topic documents keyed by (topic_slug, scope_qualifier)
        topic_groups: Pass 1 scan records grouped by (topic_slug, scope_qualifier)
    """

    # ── Per-document: scope inference + Pass 1 ───────────────────────────────
    all_records: list[dict] = []
    doc_scopes: dict[str, ScopeInferenceOutput] = {}

    for path in paths:
        text, doc_name = load_document(path)
        print(f"\n{'='*60}")
        print(f"Processing: {path.name}  ({count_tokens(text)} tokens est.)")
        print('='*60)

        # Call #11 — scope inference (once per document)
        scope: ScopeInferenceOutput = llm_call(
            provider, model, 11, "scope_inference", doc_name,
            render_prompt("scope_inference",
                filename=path.name,
                title=_extract_title(text),
                preview=text[:400],
            ),
            ScopeInferenceOutput,
        )
        doc_scopes[doc_name] = scope

        # Pre-processing: chunk if large, then extract sections deterministically
        chunks = prepare_chunks(text, doc_name)
        sections = []
        for chunk in chunks:
            sections.extend(extract_sections(chunk.text))

        if not sections:
            print(f"  Warning: no sections extracted from {doc_name}")
            continue

        # Pass 1: topic scanning per section
        doc_record_count = 0
        for section in sections:
            scan_output: TopicScanOutput = llm_call(
                provider, model, 1, "topic_scanning",
                f"{doc_name} / {section['section_title']}",
                render_prompt("topic_scanning",
                    section_title=section["section_title"],
                    source_path=section["source_path"],
                    base_slug=_heading_to_base_slug(section["section_title"]),
                    content=section["content"],
                ),
                TopicScanOutput,
            )
            for record in scan_output.records:
                all_records.append({
                    **record.model_dump(),
                    "source_document": doc_name,
                })
            doc_record_count += len(scan_output.records)

        print(f"  → {doc_record_count} scan records from {doc_name}")

    print(f"\n  Total scan records: {len(all_records)}")

    # ── Pass 2: group by (topic_slug, scope_qualifier) ────────────────────────
    groups: dict[tuple[str, str | None], list[dict]] = defaultdict(list)
    for record in all_records:
        if record["topic_slug"] == "skip-candidate":
            continue
        key = (record["topic_slug"], record["scope_qualifier"])
        groups[key].append(record)

    print(f"  Topic groups: {len(groups)}")

    # ── Pass 3 + 4: assemble topic docs and extract facts ────────────────────
    all_facts: list[ExtractedFact] = []
    topic_docs: dict[tuple[str, str | None], str] = {}

    for (topic_slug, scope_qualifier), records in sorted(groups.items(), key=lambda x: (x[0][0], x[0][1] or "")):
        # Pass 3: assemble topic document
        topic_doc_lines: list[str] = []
        for r in records:
            topic_doc_lines.append(f"### {r['source_path']}")
            topic_doc_lines.append("")
            topic_doc_lines.append(r["span_text"])
            topic_doc_lines.append("")
        topic_document = "\n".join(topic_doc_lines).rstrip()
        topic_docs[(topic_slug, scope_qualifier)] = topic_document

        # Merge scopes from all contributing documents
        contributing_docs = list(dict.fromkeys(r["source_document"] for r in records))
        merged_audience: list[str] = []
        merged_channels: list[str] = []
        for doc in contributing_docs:
            scope = doc_scopes.get(doc)
            if scope:
                for a in scope.audience_scope:
                    if a not in merged_audience:
                        merged_audience.append(a)
                for c in scope.channel_scope:
                    if c not in merged_channels:
                        merged_channels.append(c)

        label = topic_slug + (f"/{scope_qualifier}" if scope_qualifier else "")
        print(f"\n  Topic: {label}  ({len(records)} spans)")

        # Pass 4: fact extraction
        extraction_output: FactExtractionOutput = llm_call(
            provider, model, 4, "fact_extraction",
            label,
            render_prompt("fact_extraction",
                topic_document=topic_document,
                audience_scope=merged_audience,
                channel_scope=merged_channels,
            ),
            FactExtractionOutput,
        )

        source_spans = [r["source_path"] for r in records]
        primary_doc = contributing_docs[0]

        for i, raw_fact in enumerate(extraction_output.facts):
            all_facts.append(ExtractedFact(
                id=_make_fact_id(topic_slug, scope_qualifier, i),
                title=raw_fact.title,
                content=raw_fact.content,
                kind=raw_fact.kind,
                topic_tags=raw_fact.topic_tags,
                topic_slug=topic_slug,
                scope_qualifier=scope_qualifier,
                audience_scope=merged_audience,
                channel_scope=merged_channels,
                source_document=primary_doc,
                source_spans=source_spans,
            ))

        print(f"    → {len(extraction_output.facts)} facts")

    return all_facts, topic_docs, dict(groups)


def main() -> None:
    parser = argparse.ArgumentParser(description="Chain A: Document → Facts (4-pass extraction)")
    parser.add_argument("--model", required=True,
                        help="Provider/model string, e.g. anthropic/claude-sonnet-4-6")
    parser.add_argument("--save", metavar="PATH",
                        help="Save corpus to JSON, e.g. output/corpus.json")
    parser.add_argument("--doc", metavar="FILENAME",
                        help="Process only this document (filename within test_docs/)")
    args = parser.parse_args()

    provider = make_provider(args.model)

    docs = sorted(TEST_DOCS_DIR.glob("*.md"))
    if args.doc:
        docs = [d for d in docs if d.name == args.doc]
        if not docs:
            print(f"Document not found: {args.doc}", file=sys.stderr)
            sys.exit(1)

    all_facts, _, _ = process_documents(docs, provider, args.model)

    print(f"\n{'='*60}")
    print(f"Total: {len(all_facts)} facts from {len(docs)} document(s)")

    if args.save:
        out = pathlib.Path(args.save)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "facts": [f.model_dump() for f in all_facts],
        }, indent=2))
        print(f"Corpus saved to {out}")


if __name__ == "__main__":
    main()
