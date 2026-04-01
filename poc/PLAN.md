# FactSquid POC — Plan

## Goal

Prove the two LLM-heavy flows work before building infrastructure.

**Chain A — Document → Facts** (4-pass extraction per `docs/design/fact-definition.md`)
**Chain B — Change Request → Proposal** (D15 calls #1 → #2 → #3)

Not in scope: auth, git, Postgres, Temporal, rendering, deduplication (calls #12, #13), production reliability.

---

## Corpus

**Development corpus**: `poc/test_docs/` — four synthetic excerpts from Imagine Montessori School Valencia, small enough to run cheaply during iteration.

| File | Content | Audience |
|---|---|---|
| `test_doc_1_school_hours.md` | Hours, punctuality, fees, absence procedure | Parents |
| `test_doc_2_terminology.md` | Outings definitions + policy principles + objectives | Staff |
| `test_doc_3_emergency_procedure.md` | Accident and emergency procedure on outings | Staff |
| `test_doc_4_dress_code.md` | §2.4 Student dress code + §2.5 Staff dress code | Students, Staff, Parents |

**Key test properties built into these docs**:
- `test_doc_4` has two distinct scoped sub-topics in one document (`dress-code/students` and `dress-code/staff`) — the primary same-topic-different-scope test case.
- `test_doc_2` mixes definitions, principles, and objectives — tests `kind` assignment and skip-candidate behaviour.
- `test_doc_1` has fees and contact-details embedded in procedure text — tests type variety and whether fee/contact-detail facts are separated cleanly.
- `test_doc_3` is a single deep-nested procedure — tests whether Pass 4 produces stand-alone facts from complex nested content.

**Graduation**: once the pipeline produces good results on the development corpus, run once against `data/test_corpus/` as a scale check. Do not iterate on the full corpus — token cost is prohibitive.

---

## Chain A — 4-Pass Extraction

Core principle from `fact-definition.md`: **concentrate all content about a topic before generating facts from it.** Per-section extraction produces fragments; grouping first produces whole facts.

### Pre-processing (deterministic, no LLM)

Before any LLM call per document:
1. Strip code fence wrapper if present
2. If document exceeds ~6k tokens: split on H1 headings into chunks; prefix each chunk with `Document: <name>\n` for context. The development corpus is all well under this threshold — chunking is not exercised at this stage.
3. Call #11 (scope inference) runs **once per document**, not per chunk

### Pass 1 — Topic Scanning (LLM, per section)

**Input**: one section (heading + body text, with document context prefix if chunked)

**Output**: one record per paragraph or logical block:
```
{ topic_slug, scope_qualifier, span_text, source_path }
```

- `topic_slug` — hierarchical, normalised: `dress-code/general`, `medication/procedures`. Must be stable across documents — two records with the same slug will be merged mechanically in Pass 2.
- `scope_qualifier` — what makes this instance distinct from others with the same slug: `students`, `staff`, `2024-2025`. Omit if none applies.
- `span_text` — verbatim paragraph(s). **No summarisation. No rewriting.** The source text is ground truth.
- `source_path` — provenance heading: `Family Manual > 12. Dress Code`

The model does **structural inference only**: where does each topic appear, and what scope applies. It does not write or summarise content. Asking for summaries here is wasteful — they are paid for once and discarded, and a bad summary silently corrupts the grouping step.

Orphan preamble (pure rationale, aspirational framing, no policy content) → slug `<topic>/principles` or mark `skip-candidate`.

### Pass 2 — Grouping (deterministic, no LLM)

Group all Pass 1 records by `(topic_slug, scope_qualifier)`. Pure key equality — the slug normalisation in Pass 1 did the semantic work.

### Pass 3 — Topic Document Assembly (deterministic, no LLM)

For each group, build a **topic document**:
1. Concatenate verbatim `span_text` for all records in the group
2. Prefix each span with its `source_path` as a heading
3. Contradiction flag: if two spans contain conflicting numeric values or opposing obligations on the same subject, mark for human review before Pass 4

Result: a compact document of all source text for one topic, in original wording, with provenance headings.

### Pass 4 — Fact Extraction (LLM, per topic document)

**Input**: one topic document + the document's `audience_scope` and `channel_scope` (from #11)

**Output**: final facts for this topic:
```
{ title, content, kind (optional), topic_tags }
```

This is the **only pass that writes content**. The model applies all Five Tests from `fact-definition.md`:

1. **Stand-Alone** — a reader with no other facts must fully understand the policy. No implied "who does this apply to?", "when?", "except what?"
2. **One Topic** — a single noun phrase names the subject. If "and" is needed, split.
3. **Reconstruction** — concatenating all facts from this topic document must be informationally equivalent to the topic document: same obligations, permissions, exceptions, values.
4. **Canonical Form** — active voice, no document-navigation language ("as mentioned in", "refer to"), no redundant preamble ("it is important to note that").
5. **Template-Slot Ready** — no audience-specific framing baked in ("as a parent, you should…"), no channel-specific framing ("as you read this handbook…").

`kind` is assigned only when content clearly separates into a non-policy category and separating it adds value: `rationale`, `principle`, `context`. Default: no `kind`. Most facts are policy facts.

### Chain A output per assembled fact

```python
ExtractedFact(
    id: str,                    # doc_slug__topic_slug__index
    title: str,
    content: str,
    kind: str | None,           # only rationale/principle/context when warranted
    topic_tags: list[str],      # from Pass 4, consistent with D3
    topic_slug: str,            # from Pass 1 grouping key
    scope_qualifier: str | None,
    audience_scope: list[str],  # from #11
    channel_scope: list[str],   # from #11
    source_document: str,
    source_spans: list[str],    # source_path values for provenance
)
```

---

## Reconstruction Verification (POC evaluation tool, not a D15 call)

Primary quality criterion for Chain A (Test 3 from `fact-definition.md`).

For each topic document: concatenate `title + content` of all facts extracted from it. Compare to the topic document. Must be informationally equivalent: same obligations, permissions, exceptions, numerical values. Different words are fine. Missing or added information is a failure.

Run with an LLM critique call (`reconstruction_critique.j2`) per topic document. Used in `run_iteration.py` for development-loop feedback.

---

## Chain B — Change Request → Proposal

Uses Chain A output as corpus. Structure is unchanged.

### Retrieval (two stages)

**Stage 1** — Embedding similarity: embed each fact's `content` at index time using `all-MiniLM-L6-v2` (local, no API). At query time embed the request, return top-K by cosine similarity (test K = 5, 10, 20). In-memory numpy. What we measure: minimum K for 100% recall on the three test requests.

**Stage 2** — D15 call #1 (affected fact identification): LLM receives top-K candidates and reasons about which are actually affected. Corrects "similar but not affected" false positives.

### Calls #2 and #3 (per affected fact)

**Call #2** — fact content drafting: `{revised_content, change_summary}`
**Call #3** — topic tag recommendation: `{topic_tags, tag_changes: [{action, tag, reason}]}`

### The three change requests

1. **Dress code** — "Update the student dress code: students may now wear trainers on any day, not just PE days."
   Expected: `dress-code/students` facts from `test_doc_4`. Must not affect `dress-code/staff` facts. Tests scope isolation.

2. **Late arrival fee** — "Update the late arrival fee threshold: the €5 fee now applies from the third late arrival in the year, not the fifth."
   Expected: fee facts in `test_doc_1`. Tests whether embedded fee facts are cleanly separated from procedure text.

3. **Missing child procedure** — "When a child goes missing on a trip abroad, staff must also contact the local consulate in addition to calling the police."
   Expected: missing-child procedure facts in `test_doc_3`. Tests whether a targeted change to one sub-procedure leaves the rest of the emergency procedure facts unchanged.

---

## Archive

Old scripts and prompts replaced by the 4-pass pipeline are preserved in `poc/archive/`:

| Archived file | Reason |
|---|---|
| `archive/run_onboarding.py` | Replaced: old 3-call pipeline (#8/#9/#10 per section) |
| `archive/run_iteration.py` | Replaced: per-section critique loop |
| `archive/reconstruct.py` | Replaced: `render_as` logic no longer applies |
| `archive/prompts/heading_hierarchy_extraction.j2` | Deleted: Call #8 not used in 4-pass pipeline |
| `archive/prompts/topic_tag_inference.j2` | Deleted: Call #9 not used in 4-pass pipeline |
| `archive/prompts/fact_decomposition.j2` | Deleted: Call #10 not used in 4-pass pipeline |

---

## What can be salvaged from the current POC

| File | Status | Notes |
|---|---|---|
| `corpus.py` | Keep as-is | Stripping, chunking, `DocumentChunk` all unchanged |
| `embed.py` | Keep as-is | Works on any facts with a `content` field; Chain B retrieval unchanged |
| `llm.py` | Keep, 1 touch | `_result_summary()` only: remove 3 old cases, add `TopicScanOutput` + `FactExtractionOutput` |
| `run_change.py` | Keep, 1 touch | One prompt render line: pass `fact.topic_slug` instead of `fact.source_section` |
| `prompts/scope_inference.j2` | Keep as-is | |
| `prompts/affected_fact_identification.j2` | Keep as-is | |
| `prompts/fact_content_drafting.j2` | Keep as-is | |
| `prompts/topic_tag_recommendation.j2` | Keep as-is | |
| `schemas.py` | Partial | Chain B schemas + `ScopeInferenceOutput` + `CritiqueOutput` keep intact; extraction side deleted and replaced |
| `prompts/reconstruction_critique.j2` | Partial | Reframe around Five Tests; variables change from `section_title`/`original_content` to `topic_document`/`reconstructed_content` |
| `run_iteration.py` | Rewrite | Loop structure survives; per-section iteration becomes per-topic-document; `_find_section_in_original()` gone |
| `reconstruct.py` | Rewrite | `render_as` logic gone; new version: concatenate `## {title}\n\n{content}` per fact |
| `run_onboarding.py` | Rewrite | `_make_fact_id()` and `main()` survive; `process_document()` is a full rewrite for the 4-pass pipeline |
| `prompts/topic_scanning.j2` | New | Pass 1 |
| `prompts/fact_extraction.j2` | New | Pass 4 |

---

## Implementation steps — all complete ✓

Steps 1–10 implemented. Run the POC next session:

```bash
# Chain A — run all 4 test docs
python3 run_onboarding.py --model anthropic/claude-sonnet-4-6 --save output/corpus.json

# Chain A — iteration loop (one doc at a time)
python3 run_iteration.py --model anthropic/claude-sonnet-4-6 --doc 4 --save iterations/iter_001

# Chain B — change proposals
python3 run_change.py --model anthropic/claude-sonnet-4-6 --corpus output/corpus.json --save output/proposals.json
```

---

Each step is a single bounded change. Read only the files listed for that step.

### Step 1 — Update `schemas.py`

Remove: `SectionNode`, `HeadingHierarchyOutput`, `SectionTags`, `TopicTagInferenceOutput`, old `ExtractedFactRaw`, `FactDecompositionOutput`, `RenderAs`, `FactType`.

Add:
- `TopicScanRecord(topic_slug, scope_qualifier, span_text, source_path)` + `TopicScanOutput`
- `ExtractedFactRaw(title, content, kind: Literal["rationale","principle","context"] | None, topic_tags)` + `FactExtractionOutput`

Update `ExtractedFact`: replace `source_section`, `render_as`, `audience_hint` with `title`, `kind`, `topic_slug`, `scope_qualifier`, `source_spans: list[str]`.

Update `CritiqueProblem.problem_type`: replace `wrong-render`, `wrong-audience` with `not-standalone` (fails Test 1), `not-canonical` (fails Test 4), `not-template-ready` (fails Test 5).

Keep unchanged: `ScopeInferenceOutput`, `AffectedFact*`, `FactContentDrafting*`, `TagChange`, `TopicTagRecommendation*`, `CritiqueOutput`.

### Step 2 — Write `prompts/topic_scanning.j2`

Pass 1 prompt. Input variables: `section_title`, `source_path`, `content`.

Instructs the model to output one `TopicScanRecord` per paragraph or logical block. Key constraints to state:
- One record per paragraph, not per section
- `span_text` is verbatim — never summarise or rewrite
- `topic_slug` must be stable: same concept → same slug, even across documents
- Orphan preamble → `<topic>/principles` or `skip-candidate`

### Step 3 — Write `prompts/fact_extraction.j2`

Pass 4 prompt. Input variables: `topic_document` (assembled topic document with provenance headings), `audience_scope`, `channel_scope`.

State the Five Tests explicitly. Key instructions:
- Rewrite into canonical form (active voice, no navigation language)
- Eliminate redundancy across spans
- Split only at true topic boundaries
- `kind` only for clearly non-policy content worth separating
- Output must be informationally equivalent to the topic document

### Step 4 — Update `prompts/reconstruction_critique.j2`

Input variables: `topic_document`, `reconstructed_content`.

Frame the comparison against the Five Tests, not structural formatting issues. Key questions for the critique model:
- Is any obligation, permission, exception, or numerical value missing?
- Is any information added that wasn't in the topic document?
- Does any fact fail the Stand-Alone test?
- Does any fact contain document-navigation language?

### Step 5 — Update `reconstruct.py`

`reconstruct_document(facts, template)` becomes `reconstruct_topic_document(facts: list[ExtractedFact]) -> str`: concatenate `## {fact.title}\n\n{fact.content}` for each fact. Remove all `render_as` logic.

Add `topic_document_text(records: list[dict]) -> str`: assembles a topic document from Pass 3 records for use as critique input.

### Step 6 — Update `llm.py`

`_result_summary`: remove cases for `HeadingHierarchyOutput`, `TopicTagInferenceOutput`, `FactDecompositionOutput`. Add cases for `TopicScanOutput` and `FactExtractionOutput`.

### Step 7 — Rewrite `run_onboarding.py`

Implement the 4-pass pipeline:

```
for each document:
    call #11 → scope
    pre-process → chunks

for each chunk → for each section in chunk:
    Pass 1 LLM call → TopicScanRecord list
    append to all_records (with source_document on each record)

Pass 2: group all_records by (topic_slug, scope_qualifier)

Pass 3: for each group:
    assemble topic document (concatenate span_text with source_path headings)
    detect contradictions

Pass 4: for each topic document:
    LLM call → FactExtractionOutput
    attach audience_scope/channel_scope from #11 of originating document
    generate ExtractedFact per raw fact
```

Note on scope resolution in Pass 4: a topic document may contain spans from multiple documents (e.g., handbook + CoC dress code). Merge audience/channel scopes from all contributing documents.

### Step 8 — Update `run_iteration.py`

- Change `process_document` call to the new 4-pass pipeline (now runs per document, not separate)
- Replace per-section critique with per-topic-document critique
- Display: topic_slug | span count | fact count | critique result

### Step 9 — Update `run_change.py`

Minor: `affected_fact_identification` prompt receives `fact.topic_slug` instead of `fact.source_section`. Update the template variable reference in the prompt render call.

### Step 10 — Archive obsolete prompts ✓

Moved to `poc/archive/prompts/`: `heading_hierarchy_extraction.j2`, `topic_tag_inference.j2`, `fact_decomposition.j2`.

---

## Evaluation

### Chain A checklist

**Pass 1 (topic scanning)**
- [ ] `test_doc_4`: §2.4 and §2.5 get different `scope_qualifier` values — not collapsed to one slug
- [ ] `test_doc_2`: definition paragraphs (§2) get a distinct slug from policy principles (§3) and objectives (§4)
- [ ] `test_doc_2`: "Educational Enrichment / Cultural Awareness" objective bullets → `*/principles` or `skip-candidate`
- [ ] `test_doc_1`: late-arrival and late-pick-up fee paragraphs get a `fees` slug — not buried under `attendance`

**Pass 2/3 (grouping and assembly)**
- [ ] `dress-code/students` and `dress-code/staff` produce two separate topic documents
- [ ] All spans for each slug are concatenated in one topic document with provenance headings

**Pass 4 (fact extraction)**
- [ ] Facts pass the Stand-Alone test — no implied "who", "when", "except what"
- [ ] Facts pass the One-Topic test — single subject noun phrase, no "and"
- [ ] Reconstruction test: concatenated facts informationally equivalent to the topic document
- [ ] Canonical form: no "as mentioned in", "this policy states", "it is important to note"
- [ ] `test_doc_2` definitions → `kind: context`; policy principles → `kind: principle`
- [ ] `test_doc_1` fee facts extracted as their own facts, not merged into surrounding procedure text
- [ ] Scope: `test_doc_1` → `audience: parents`; `test_doc_3` → `audience: staff`; `test_doc_4` → `audience: students, staff, parents`

### Chain B checklist (per request)

- [ ] At K=10: correct facts in candidate set for all three requests
- [ ] Request 1 (trainers): only `dress-code/students` facts retrieved — not `dress-code/staff`
- [ ] Request 2 (late arrival fee): fee fact retrieved and revised value is correct; surrounding procedure facts untouched
- [ ] Request 3 (missing child abroad): only the missing-child sub-procedure facts are revised; minor injury and serious injury facts unchanged
- [ ] Stage 2 filters to truly affected facts only — no tangentially related noise
- [ ] Proposed content incorporates the change without hallucinating adjacent changes

---

## What a "pass" looks like

**Chain A** — an administrator looking at the output says: *"This looks like my school's structure. The facts make sense. Where the same policy appeared in multiple documents, it's been concentrated into one place."*

**Chain B** — an administrator says: *"Yes, these are the right facts to change — including the ones I forgot were duplicated — and the proposed wording captures what I asked for."*
