#!/usr/bin/env python3
"""
One iteration of the extraction quality loop.

Randomly picks one of the 4 test documents, runs extraction, reconstructs
deterministically, then uses an LLM to critique each section.

Usage:
    python run_iteration.py --model openai/gpt-5.4-mini
    python run_iteration.py --model openai/gpt-5.4-mini --doc 2
    python run_iteration.py --model openai/gpt-5.4-mini --save iterations/iter_001

Output (always to stdout + optionally saved):
    - Per-section: original | reconstructed | critique
    - Summary: total problems by type
"""
from __future__ import annotations

import argparse
import json
import pathlib
import random
import re
import sys
from collections import defaultdict

from reconstruct import reconstruct_document, section_text
from run_onboarding import process_document
from llm import LLMProvider, call as llm_call, make_provider, render_prompt
from schemas import CritiqueOutput, ExtractedFact

TEST_DOCS_DIR = pathlib.Path(__file__).parent / "test_docs"


def _find_section_in_original(original: str, section_title: str) -> str:
    """Extract a section's original text by finding the title and reading until the next heading."""
    # Try to find the title after any heading markers
    clean = re.sub(r'[*`_#]', '', section_title).strip()
    idx = original.find(clean)
    if idx == -1:
        return "(section not found in original)"
    # Find next markdown heading after this one
    next_heading = re.search(r'\n#{1,4} ', original[idx + len(clean):])
    end = idx + len(clean) + (next_heading.start() if next_heading else len(original))
    return original[idx:end].strip()


def critique_section(
    provider: LLMProvider,
    model: str,
    section_title: str,
    original_content: str,
    reconstructed_content: str,
) -> CritiqueOutput:
    return llm_call(
        provider, model, 99, "reconstruction_critique",
        f"critique: {section_title[:50]}",
        render_prompt(
            "reconstruction_critique",
            section_title=section_title,
            original_content=original_content[:800],
            reconstructed_content=reconstructed_content[:800],
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
    original_text = doc_path.read_text(encoding="utf-8")

    print(divider("═"))
    print(f"  Test document : {doc_path.name}")
    print(f"  Model         : {args.model}")
    print(divider("═"))

    if args.save:
        import os
        os.environ["FACTSQUID_TRACE_DIR"] = str(pathlib.Path(args.save) / "traces")

    provider = make_provider(args.model)

    # ── Chain A: extract ────────────────────────────────────────────────────
    facts, template = process_document(doc_path, provider, args.model)
    print(f"\n  → {len(facts)} facts from {len(template['sections'])} sections\n")

    # ── Reconstruction ──────────────────────────────────────────────────────
    reconstructed_md = reconstruct_document(facts, template)

    facts_by_section: dict[str, list[ExtractedFact]] = defaultdict(list)
    for f in facts:
        facts_by_section[f.source_section].append(f)

    # ── Per-section critique ────────────────────────────────────────────────
    all_critiques: list[dict] = []
    problem_counts: dict[str, int] = defaultdict(int)

    for section_info in template["sections"]:
        title = section_info["section_title"]
        section_facts = facts_by_section.get(title, [])

        original_section = _find_section_in_original(original_text, title)
        reconstructed_section = section_text(section_facts) if section_facts else "(empty)"

        print(divider())
        print(f"  SECTION: {title}")
        print(divider())

        print("\n  ORIGINAL:")
        for line in original_section.splitlines()[:15]:
            print(f"    {line}")
        if len(original_section.splitlines()) > 15:
            print(f"    ... ({len(original_section.splitlines()) - 15} more lines)")

        print("\n  RECONSTRUCTED:")
        for line in reconstructed_section.splitlines()[:15]:
            print(f"    {line}")

        print(f"\n  FACTS ({len(section_facts)}):")
        for f in section_facts:
            audience = f"/aud:{','.join(f.audience_scope)}" if f.audience_scope else ""
            print(f"    [{f.type}/{f.render_as}{audience}] {f.content[:90]}")

        critique = critique_section(
            provider, args.model, title, original_section, reconstructed_section
        )

        print(f"\n  CRITIQUE: {critique.overall}")
        for p in critique.problems:
            print(f"    [{p.problem_type}] {p.description}")
            problem_counts[p.problem_type] += 1

        all_critiques.append({
            "section": title,
            "fact_count": len(section_facts),
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
        (out / "original.md").write_text(original_text)
        (out / "reconstructed.md").write_text(reconstructed_md)
        (out / "facts.json").write_text(
            json.dumps([f.model_dump() for f in facts], indent=2, ensure_ascii=False)
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
