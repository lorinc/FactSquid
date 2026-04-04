#!/usr/bin/env python3
"""Chain B: Change Request → Proposal

Usage:
    python run_change.py --model anthropic/claude-sonnet-4-6 --corpus output/corpus.json
    python run_change.py --model anthropic/claude-sonnet-4-6 --corpus output/corpus.json --request 3 --save output/proposals.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

from embed import build_index
from llm import LLMProvider, call as llm_call, make_provider, render_prompt
from schemas import (
    AffectedFactIdentificationOutput,
    ExtractedFact,
    FactContentDraftingOutput,
    TopicTagRecommendationOutput,
)

CHANGE_REQUESTS = [
    "Update the student dress code: students may now wear trainers on any day, not just PE days.",
    "Update the late arrival fee threshold: the €5 fee now applies from the third late arrival "
    "in the year, not the fifth.",
    "When a child goes missing on a trip abroad, staff must also contact the local consulate "
    "in addition to calling the police.",
]

K = 10  # candidate retrieval count


def process_change_request(
    change_request: str,
    facts: list[ExtractedFact],
    provider: LLMProvider,
    model: str,
    request_num: int,
) -> dict:
    print(f"\n{'='*60}")
    print(f"Change Request #{request_num}:")
    print(f"  {change_request}")
    print('='*60)

    # Stage 1: embedding similarity retrieval
    from embed import build_index
    index = build_index(facts)
    candidates = index.search(change_request, k=K)

    print(f"\nStage 1 — Embedding retrieval (K={K}):")
    for fact, score in candidates:
        print(f"  {score:.3f} | {fact.source_document}/{fact.topic_slug}: {fact.content[:80]}...")

    candidate_facts = [f for f, _ in candidates]
    candidate_by_id = {f.id: f for f in candidate_facts}

    # Stage 2: LLM relevance filtering — call #1
    id_output: AffectedFactIdentificationOutput = llm_call(
        provider, model, 1, "affected_fact_identification",
        f"Request #{request_num}",
        render_prompt("affected_fact_identification",
            change_request=change_request,
            facts=candidate_facts,
        ),
        AffectedFactIdentificationOutput,
    )

    affected = sorted(
        [af for af in id_output.affected_facts if af.relevance >= 3],
        key=lambda x: x.relevance,
        reverse=True,
    )

    print(f"\nStage 2 — Affected facts ({len(affected)} identified):")

    proposals = []
    for af in affected:
        fact = candidate_by_id.get(af.fact_id)
        if fact is None:
            print(f"  Warning: fact_id {af.fact_id!r} not found in candidates — skipping")
            continue

        print(f"\n  [{af.relevance}/5] {fact.source_document}/{fact.topic_slug}")
        print(f"    Reason: {af.reason}")
        print(f"    Current: {fact.content[:100]}...")

        # Call #2 — fact content drafting
        draft_output: FactContentDraftingOutput = llm_call(
            provider, model, 2, "fact_content_drafting",
            f"{fact.source_document}/{fact.topic_slug}",
            render_prompt("fact_content_drafting",
                change_request=change_request,
                current_content=fact.content,
            ),
            FactContentDraftingOutput,
        )
        print(f"    Revised: {draft_output.revised_content[:100]}...")
        print(f"    Summary: {draft_output.change_summary}")

        # Call #3 — topic tag recommendation
        tag_output: TopicTagRecommendationOutput = llm_call(
            provider, model, 3, "topic_tag_recommendation",
            f"{fact.source_document}/{fact.topic_slug}",
            render_prompt("topic_tag_recommendation",
                revised_content=draft_output.revised_content,
                existing_tags=fact.topic_tags,
            ),
            TopicTagRecommendationOutput,
        )

        proposals.append({
            "fact_id": af.fact_id,
            "source": f"{fact.source_document}/{fact.topic_slug}",
            "relevance": af.relevance,
            "reason": af.reason,
            "original_content": fact.content,
            "revised_content": draft_output.revised_content,
            "change_summary": draft_output.change_summary,
            "original_tags": fact.topic_tags,
            "revised_tags": tag_output.topic_tags,
            "tag_changes": [tc.model_dump() for tc in tag_output.tag_changes],
        })

    return {
        "change_request": change_request,
        "k": K,
        "affected_count": len(affected),
        "proposals": proposals,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Chain B: Change Request → Proposal")
    parser.add_argument("--model", required=True,
                        help="Provider/model string, e.g. anthropic/claude-sonnet-4-6")
    parser.add_argument("--corpus", required=True,
                        help="Path to corpus.json produced by run_onboarding.py")
    parser.add_argument("--save", metavar="PATH",
                        help="Save proposals to JSON file")
    parser.add_argument("--request", type=int, choices=[1, 2, 3],
                        help="Run only this change request (1–3); omit to run all")
    args = parser.parse_args()

    corpus_path = pathlib.Path(args.corpus)
    if not corpus_path.exists():
        print(f"Corpus not found: {corpus_path}", file=sys.stderr)
        print("Run run_onboarding.py --save first.", file=sys.stderr)
        sys.exit(1)

    corpus = json.loads(corpus_path.read_text())
    facts = [ExtractedFact(**d) for d in corpus["facts"]]
    print(f"Loaded {len(facts)} facts from {corpus_path}")

    provider = make_provider(args.model)

    requests = CHANGE_REQUESTS if not args.request else [CHANGE_REQUESTS[args.request - 1]]
    start_num = args.request or 1

    results = []
    for i, req in enumerate(requests, start=start_num):
        result = process_change_request(req, facts, provider, args.model, i)
        results.append(result)

    if args.save:
        out = pathlib.Path(args.save)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(results, indent=2))
        print(f"\nProposals saved to {out}")


if __name__ == "__main__":
    main()
