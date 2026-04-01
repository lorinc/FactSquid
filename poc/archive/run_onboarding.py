#!/usr/bin/env python3
"""Chain A: Document → Facts + Template Trees

Usage:
    python run_onboarding.py --model anthropic/claude-sonnet-4-6 --save output/corpus.json
    python run_onboarding.py --model openai/gpt-4o --doc en_family_manual_24_25.md --save output/corpus.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

from corpus import count_tokens, load_document, prepare_chunks
from llm import LLMProvider, call as llm_call, make_provider, render_prompt
from schemas import (
    ExtractedFact,
    FactDecompositionOutput,
    HeadingHierarchyOutput,
    ScopeInferenceOutput,
    TopicTagInferenceOutput,
)

CORPUS_DIR = pathlib.Path(__file__).parent.parent / "data" / "test_corpus"


def _extract_title(text: str) -> str:
    match = re.search(r'^# (.+)$', text, re.MULTILINE)
    return match.group(1).strip() if match else "Unknown"


def _make_fact_id(doc_name: str, section_title: str, index: int) -> str:
    slug = re.sub(r'[^a-z0-9]+', '_', section_title.lower()).strip('_')
    return f"{doc_name}__{slug}__{index}"


def process_document(
    path: pathlib.Path,
    provider: LLMProvider,
    model: str,
) -> tuple[list[ExtractedFact], dict]:
    """Process one document through calls #11, #8 (per chunk), #9 (aggregated), #10 (per section)."""
    text, doc_name = load_document(path)

    # Call #11 — scope inference (document level, not per chunk)
    scope_output: ScopeInferenceOutput = llm_call(
        provider, model, 11, "scope_inference", doc_name,
        render_prompt("scope_inference",
            filename=path.name,
            title=_extract_title(text),
            preview=text[:400],
        ),
        ScopeInferenceOutput,
    )

    # Pre-processing: split into chunks if large
    chunks = prepare_chunks(text, doc_name)

    # Call #8 per chunk — collect all sections
    all_sections = []
    for chunk in chunks:
        hier_output: HeadingHierarchyOutput = llm_call(
            provider, model, 8, "heading_hierarchy_extraction",
            f"{doc_name} / {chunk.source_section or 'full'}",
            render_prompt("heading_hierarchy_extraction", document_text=chunk.text),
            HeadingHierarchyOutput,
        )
        all_sections.extend(hier_output.sections)

    if not all_sections:
        print(f"  Warning: no sections extracted from {doc_name}")
        return [], {"document": doc_name, "audience_scope": scope_output.audience_scope,
                    "channel_scope": scope_output.channel_scope, "sections": []}

    # Call #9 once on all sections — consistent tag vocabulary across the whole document
    tags_output: TopicTagInferenceOutput = llm_call(
        provider, model, 9, "topic_tag_inference",
        f"{doc_name} ({len(all_sections)} sections)",
        render_prompt("topic_tag_inference", sections=all_sections),
        TopicTagInferenceOutput,
    )
    tag_map = {st.section_title: st.topic_tags for st in tags_output.section_tags}

    # Call #10 per section — fact decomposition
    all_facts: list[ExtractedFact] = []
    template_sections = []

    for section in all_sections:
        tags = tag_map.get(section.title, [])
        decomp_output: FactDecompositionOutput = llm_call(
            provider, model, 10, "fact_decomposition",
            f"{doc_name} / {section.title}",
            render_prompt("fact_decomposition",
                document_name=doc_name,
                section_title=section.title,
                topic_tags=tags,
                content=section.content,
            ),
            FactDecompositionOutput,
        )
        for i, raw_fact in enumerate(decomp_output.facts):
            # Narrow audience to hint if provided, otherwise use document-level scope
            resolved_audience = (
                raw_fact.audience_hint
                if raw_fact.audience_hint
                else scope_output.audience_scope
            )
            all_facts.append(ExtractedFact(
                id=_make_fact_id(doc_name, section.title, i),
                content=raw_fact.content,
                type=raw_fact.type,
                topic_tags=raw_fact.topic_tags,
                render_as=raw_fact.render_as,
                audience_scope=resolved_audience,
                channel_scope=scope_output.channel_scope,
                source_document=doc_name,
                source_section=section.title,
            ))
        template_sections.append({
            "section_title": section.title,
            "level": section.level,
            "topic_tags": tags,
            "fact_count": len(decomp_output.facts),
        })

    return all_facts, {
        "document": doc_name,
        "audience_scope": scope_output.audience_scope,
        "channel_scope": scope_output.channel_scope,
        "sections": template_sections,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Chain A: Document → Facts + Template Trees")
    parser.add_argument("--model", required=True,
                        help="Provider/model string, e.g. anthropic/claude-sonnet-4-6")
    parser.add_argument("--save", metavar="PATH",
                        help="Save corpus to JSON, e.g. output/corpus.json")
    parser.add_argument("--doc", metavar="FILENAME",
                        help="Process only this document (filename within test_corpus/)")
    args = parser.parse_args()

    provider = make_provider(args.model)

    docs = sorted(CORPUS_DIR.glob("*.md"))
    if args.doc:
        docs = [d for d in docs if d.name == args.doc]
        if not docs:
            print(f"Document not found: {args.doc}", file=sys.stderr)
            sys.exit(1)

    all_facts: list[ExtractedFact] = []
    all_templates: list[dict] = []

    for doc_path in docs:
        print(f"\n{'='*60}")
        print(f"Processing: {doc_path.name}  ({count_tokens(doc_path.read_text())} tokens est.)")
        print('='*60)
        facts, template = process_document(doc_path, provider, args.model)
        all_facts.extend(facts)
        all_templates.append(template)
        print(f"  → {len(facts)} facts from {doc_path.name}")

    print(f"\n{'='*60}")
    print(f"Total: {len(all_facts)} facts from {len(docs)} document(s)")

    if args.save:
        out = pathlib.Path(args.save)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "facts": [f.model_dump() for f in all_facts],
            "templates": all_templates,
        }, indent=2))
        print(f"Corpus saved to {out}")


if __name__ == "__main__":
    main()
