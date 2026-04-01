#!/usr/bin/env python3
"""
One iteration of the extraction quality loop.

Runs the 4-pass extraction on one test document, then critiques each topic document
against its extracted facts.

Usage:
    python run_iteration.py --model anthropic/claude-sonnet-4-6
    python run_iteration.py --model anthropic/claude-sonnet-4-6 --doc 2
    python run_iteration.py --model anthropic/claude-sonnet-4-6 --save iterations/iter_001

Output (stdout + optionally saved):
    - Per topic: topic_slug | span count | fact count | critique result
    - Summary: total problems by type
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import random
import sys
from collections import defaultdict

from reconstruct import reconstruct_topic_document
from run_onboarding import process_documents
from llm import LLMProvider, call as llm_call, make_provider, render_prompt
from schemas import CritiqueOutput, ExtractedFact

TEST_DOCS_DIR = pathlib.Path(__file__).parent / "test_docs"


def critique_topic(
    provider: LLMProvider,
    model: str,
    topic_slug: str,
    topic_document: str,
    reconstructed_content: str,
) -> CritiqueOutput:
    return llm_call(
        provider, model, 99, "reconstruction_critique",
        f"critique: {topic_slug[:50]}",
        render_prompt(
            "reconstruction_critique",
            topic_document=topic_document[:1500],
            reconstructed_content=reconstructed_content[:1500],
        ),
        CritiqueOutput,
    )


def divider(char: str = "─", width: int = 60) -> str:
    return char * width


def main() -> None:
    parser = argparse.ArgumentParser(description="One extraction quality iteration")
    parser.add_argument("--model", required=True)
    parser.add_argument("--doc", type=int, choices=[1, 2, 3, 4],
                        help="Force a specific test doc (1–4); omit to pick randomly")
    parser.add_argument("--save", metavar="DIR",
                        help="Save all outputs to this directory")
    args = parser.parse_args()

    test_docs = sorted(TEST_DOCS_DIR.glob("test_doc_*.md"))
    if not test_docs:
        print(f"No test docs found in {TEST_DOCS_DIR}", file=sys.stderr)
        sys.exit(1)

    doc_path = test_docs[args.doc - 1] if args.doc else random.choice(test_docs)

    print(divider("═"))
    print(f"  Test document : {doc_path.name}")
    print(f"  Model         : {args.model}")
    print(divider("═"))

    if args.save:
        os.environ["FACTSQUID_TRACE_DIR"] = str(pathlib.Path(args.save) / "traces")

    provider = make_provider(args.model)

    # ── Chain A: 4-pass extraction ──────────────────────────────────────────
    facts, topic_docs = process_documents([doc_path], provider, args.model)
    print(f"\n  → {len(facts)} facts across {len(topic_docs)} topic groups\n")

    # ── Group facts by (topic_slug, scope_qualifier) ────────────────────────
    facts_by_topic: dict[tuple[str, str | None], list[ExtractedFact]] = defaultdict(list)
    for f in facts:
        facts_by_topic[(f.topic_slug, f.scope_qualifier)].append(f)

    # ── Per-topic critique ──────────────────────────────────────────────────
    all_critiques: list[dict] = []
    problem_counts: dict[str, int] = defaultdict(int)

    for (topic_slug, scope_qualifier), topic_facts in sorted(facts_by_topic.items()):
        label = topic_slug + (f"/{scope_qualifier}" if scope_qualifier else "")
        topic_document = topic_docs.get((topic_slug, scope_qualifier), "(topic document not found)")
        reconstructed = reconstruct_topic_document(topic_facts)
        span_count = len(topic_facts[0].source_spans)

        print(divider())
        print(f"  TOPIC: {label}  ({span_count} spans → {len(topic_facts)} facts)")
        print(divider())

        print(f"\n  FACTS:")
        for f in topic_facts:
            kind_tag = f"/{f.kind}" if f.kind else ""
            print(f"    [{f.topic_slug}{kind_tag}] {f.title}")
            print(f"      {f.content[:100]}")

        critique = critique_topic(
            provider, args.model, label, topic_document, reconstructed
        )

        print(f"\n  CRITIQUE: {critique.overall}")
        for p in critique.problems:
            print(f"    [{p.problem_type}] {p.description}")
            problem_counts[p.problem_type] += 1

        all_critiques.append({
            "topic": label,
            "span_count": span_count,
            "fact_count": len(topic_facts),
            "overall": critique.overall,
            "problems": [p.model_dump() for p in critique.problems],
        })

    # ── Summary ─────────────────────────────────────────────────────────────
    print("\n" + divider("═"))
    print("  SUMMARY")
    print(divider("═"))
    total = sum(problem_counts.values())
    print(f"  Total problems: {total}")
    for ptype, count in sorted(problem_counts.items(), key=lambda x: -x[1]):
        print(f"    {ptype}: {count}")

    # ── Save ─────────────────────────────────────────────────────────────────
    if args.save:
        out = pathlib.Path(args.save)
        out.mkdir(parents=True, exist_ok=True)
        (out / "facts.json").write_text(
            json.dumps([f.model_dump() for f in facts], indent=2, ensure_ascii=False)
        )
        (out / "topic_docs.json").write_text(
            json.dumps(
                {f"{k[0]}/{k[1] or 'all'}": v for k, v in topic_docs.items()},
                indent=2, ensure_ascii=False,
            )
        )
        (out / "critiques.json").write_text(
            json.dumps(all_critiques, indent=2, ensure_ascii=False)
        )
        (out / "problem_summary.json").write_text(
            json.dumps(dict(problem_counts), indent=2)
        )
        print(f"\n  Results saved to {out}/")


if __name__ == "__main__":
    main()
