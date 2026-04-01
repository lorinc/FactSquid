"""Pydantic v2 output schemas for all POC LLM calls."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ── Pass 1: Topic scanning ────────────────────────────────────────────────────

class TopicScanRecord(BaseModel):
    topic_slug: str = Field(
        description=(
            "Hierarchical, normalised slug — same concept across documents gets the same slug. "
            "Lowercase kebab-case with '/' for hierarchy, e.g. 'dress-code/students', "
            "'fees/late-arrival', 'attendance/absence'. "
            "Use 'skip-candidate' for pure orphan preamble with no policy content."
        )
    )
    scope_qualifier: str | None = Field(
        default=None,
        description=(
            "What makes this instance distinct from others with the same slug: "
            "'students', 'staff', '2024-2025'. Null if no scope qualifier applies."
        )
    )
    span_text: str = Field(
        description="Verbatim paragraph(s) from the source. Never summarise or rewrite."
    )
    source_path: str = Field(
        description="Provenance heading path, e.g. 'Family Manual > 12. Dress Code'"
    )


class TopicScanOutput(BaseModel):
    records: list[TopicScanRecord]


# ── Pass 4: Fact extraction ───────────────────────────────────────────────────

class ExtractedFactRaw(BaseModel):
    title: str = Field(description="Short noun phrase naming the subject of this fact")
    content: str = Field(description="The fact in canonical markdown form, passing all Five Tests")
    kind: Literal["rationale", "principle", "context"] | None = Field(
        default=None,
        description=(
            "Assign ONLY for clearly non-policy content worth separating. "
            "Leave null for all policy facts (rules, procedures, fees, contact details)."
        )
    )
    topic_tags: list[str] = Field(description="Kebab-case topic tags consistent with the topic_slug")


class FactExtractionOutput(BaseModel):
    facts: list[ExtractedFactRaw]


# ── Call #11: Scope inference ─────────────────────────────────────────────────

class ScopeInferenceOutput(BaseModel):
    audience_scope: list[str]
    channel_scope: list[str]


# ── Call #1: Affected fact identification ─────────────────────────────────────

class AffectedFact(BaseModel):
    fact_id: str
    relevance: int = Field(ge=1, le=5)
    reason: str


class AffectedFactIdentificationOutput(BaseModel):
    affected_facts: list[AffectedFact]


# ── Call #2: Fact content drafting ────────────────────────────────────────────

class FactContentDraftingOutput(BaseModel):
    revised_content: str
    change_summary: str


# ── Call #3: Topic tag recommendation ────────────────────────────────────────

class TagChange(BaseModel):
    action: Literal["add", "remove", "keep"]
    tag: str
    reason: str


class TopicTagRecommendationOutput(BaseModel):
    topic_tags: list[str]
    tag_changes: list[TagChange]


# ── Reconstruction critique ───────────────────────────────────────────────────

class CritiqueProblem(BaseModel):
    problem_type: Literal[
        "over-atomized",        # one logical unit split into too many facts
        "under-atomized",       # multiple distinct topics merged into one fact
        "missing-content",      # obligation/permission/exception/value absent from reconstruction
        "not-standalone",       # fails Test 1: implied "who", "when", or "except what"
        "not-canonical",        # fails Test 4: navigation language, passive construction, preamble
        "not-template-ready",   # fails Test 5: audience/channel framing baked in
        "wrong-tags",           # topic tags missing or inconsistent
        "other",
    ]
    description: str = Field(description="Specific description with quoted text from topic document")


class CritiqueOutput(BaseModel):
    problems: list[CritiqueProblem] = Field(
        description="Up to 4 specific problems. Empty list if reconstruction is good."
    )
    overall: str = Field(description="One-sentence summary of reconstruction quality")


# ── Assembled fact (Chain A output) ──────────────────────────────────────────

class ExtractedFact(BaseModel):
    id: str                             # topic_slug__scope_qualifier__index
    title: str
    content: str
    kind: str | None                    # rationale/principle/context or None
    topic_tags: list[str]
    topic_slug: str                     # from Pass 1 grouping key
    scope_qualifier: str | None
    audience_scope: list[str]           # from #11, merged across contributing documents
    channel_scope: list[str]            # from #11, merged across contributing documents
    source_document: str                # primary source document
    source_spans: list[str]             # source_path values for provenance
