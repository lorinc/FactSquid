# FactSquid POC — Pipeline Specification

This document describes how the pipeline works and why each design decision was made. It is the reference for anyone modifying prompts, schemas, or pipeline logic.

---

## Core principle

**Concentrate all content about a topic before generating facts from it.**

Per-section extraction produces fragments: a policy that appears across three headings becomes three incomplete facts, each missing context from the others. The 4-pass pipeline solves this by separating *structural inference* (which pass is each paragraph part of?) from *content writing* (what does the fact say?). The LLM writes facts exactly once, from a complete view of the topic.

---

## Chain A — Document → Facts

### Pre-processing (deterministic)

`corpus.py` and `extract_sections()` in `run_onboarding.py`.

Before any LLM call:
- Strip code-fence wrappers if present
- If the document exceeds ~6k tokens: split on H1 headings into chunks; prefix each with `Document: <name>` for context
- Split into sections by heading level (H1–H4); each section carries its `source_path` (full heading ancestry, e.g. `Family Manual > 12. Dress Code > 2.4 Student Dress Code`)

**Why deterministic:** document structure is unambiguous; using an LLM here would add cost, latency, and a failure mode for something a regex handles correctly.

---

### Call #11 — Scope inference (`scope_inference.j2`)

Runs once per document. Infers `audience_scope` (parents, staff, students, visitors, applicants, governors) and `channel_scope` (parent-handbook, staff-handbook, policy-documents, newsletter, website, chatbot) from the filename, title, and a short preview.

**Why once per document, not per fact:** audience and channel are properties of the document, not of individual paragraphs. Inferring them centrally avoids inconsistency and is cheap.

**Why separated from Pass 1:** scope metadata is used in Pass 4 to inform the extraction context, but it should not influence the structural slug/scope_qualifier assignments in Pass 1. Keeping them separate prevents the scope model from contaminating the grouping logic.

---

### Pass 1 — Topic Scanning (`topic_scanning.j2`, call #01)

Runs once per section. The LLM performs **structural inference only** — it does not summarise or rewrite.

Output per paragraph or logical block: a `TopicScanRecord`:
- `topic_slug` — hierarchical kebab-case identifier. Derived from the heading path by `_heading_to_base_slug()` (deterministic), then optionally extended with a `/subtopic` suffix if the paragraph introduces a distinct sub-topic. The same concept across documents must produce the same slug.
- `scope_qualifier` — what makes this instance distinct: `students`, `staff`, `2024-2025`. Often already in the heading. Null if no scope applies.
- `span_text` — **verbatim** paragraph text. Never summarised, never rewritten. The source text is ground truth.
- `source_path` — provenance heading path, carried forward as-is.

**Why verbatim span_text:** the reconstruction critique (call #99) compares extracted facts against the source. If span_text were summarised, we would lose the ground truth needed to detect what the extraction LLM omitted or hallucinated.

**Why the LLM only does structural inference here:** slugs and scope qualifiers are identity decisions — they determine which paragraphs get grouped together in Pass 2. Getting this wrong means the wrong content is in scope for Pass 4. Keeping Pass 1 to structural decisions minimises the surface area of LLM error.

**Why `_heading_to_base_slug()` is deterministic:** the heading path is unambiguous. Giving the LLM the pre-computed base slug as a starting point (rather than asking it to invent slugs from scratch) makes slug consistency across documents much more reliable. The LLM only decides whether to extend it.

Orphan preamble (pure rationale, aspirational framing with no policy content) → `<base_slug>/principles` or `skip-candidate`. Skip-candidates are dropped in Pass 2.

---

### Pass 2 — Grouping (deterministic)

Group all Pass 1 records by `(topic_slug, scope_qualifier)`. Pure key equality — the semantic work was done in Pass 1.

**Why deterministic:** grouping is a mechanical consequence of the slug assignments. Any non-determinism here would make the pipeline unpredictable.

**Why `(topic_slug, scope_qualifier)` as the key:** two records with the same slug but different scopes represent the same policy for different audiences — they should remain separate topic documents. Two records with the same slug and same scope represent the same topic across different sections — they should be merged.

---

### Pass 3 — Topic Document Assembly (deterministic)

For each group, concatenate all `span_text` values with `### source_path` headers as provenance markers.

```markdown
### Family Manual > 12. Dress Code > 2.4 Student Dress Code

Students must wear flat, enclosed shoes outdoors...

### Family Manual > 12. Dress Code > 2.4 Student Dress Code

Hats will only be worn during playground time...
```

This document is what Pass 4 receives. It is also saved verbatim in `topic_docs.json` for inspection.

**Why save topic_docs.json:** it is the single most useful artifact for debugging. Any fact quality problem is either visible here (Pass 4 fault) or absent here (Pass 1 fault). Having it as a saved artifact means root cause analysis does not require re-running the pipeline.

**Why provenance headers:** Pass 4 needs to know where content came from to write the `source_spans` provenance on each fact. They also help a human reader verify that the right spans were assembled.

---

### Pass 4 — Fact Extraction (`fact_extraction.j2`, call #04)

**The only pass that writes content.** Receives the assembled topic document plus the merged `audience_scope` and `channel_scope` from all contributing documents.

Output per fact (`ExtractedFactRaw`):
- `title` — short noun phrase naming the subject
- `content` — the fact in canonical form, passing all Five Tests
- `kind` — `rationale`, `principle`, or `context` only for clearly non-policy content; null for all rules, procedures, fees, contact details
- `topic_tags` — kebab-case tags consistent with topic_slug

The prompt states the Five Tests explicitly and instructs the model to: eliminate redundancy across spans, split only at true topic boundaries, preserve all obligations/permissions/exceptions/values, and use active voice without navigation language.

**Why the Five Tests are stated in the prompt:** they are the formal specification of what a fact is. Stating them in the extraction prompt means the model is reasoning against the same criteria the critique will apply later.

**Why `kind` defaults to null:** most policy content is policy content. Forcing every fact to carry a kind label would create noise and prompt the model to over-classify. The null default is the correct base case.

**Why merge scopes from contributing documents:** a topic document may contain spans from multiple source documents (e.g. a dress code section appears in both the parent handbook and the staff handbook). The fact should carry all audience/channel scope metadata from all contributing sources.

---

### The `ExtractedFact` schema

The final assembled fact adds pipeline metadata to `ExtractedFactRaw`:

- `id` — `topic_slug__scope_qualifier__index` — deterministic, survives re-runs as long as the document and prompts are stable
- `topic_slug`, `scope_qualifier` — from Pass 1 grouping key
- `source_document` — primary contributing document
- `source_spans` — list of source_path values from all contributing records; full provenance chain
- `audience_scope`, `channel_scope` — merged from all contributing documents

**Why deterministic IDs:** facts need stable identifiers for Chain B (affected fact identification), for deduplication in production, and for diffing across iterations. A hash of content would change on any rewrite; an index would be unstable if ordering changed. The slug + qualifier + index combination is stable within a run and human-readable.

---

## Observability

### Trace files

Every LLM call writes a JSON trace file to `FACTSQUID_TRACE_DIR` if set:

```
{seq:04d}__{call_number:02d}_{call_name}__{slug}.json
```

Each trace contains: `prompt` (full rendered text), `raw_response` (model output before parsing), `parsed_output` (validated Pydantic model), `tokens_in`, `tokens_out`, `latency_s`, `validation` (PASS / RETRY-PASS / FAIL).

**Why full prompt in the trace:** the rendered prompt is what the model actually saw. Template changes, variable substitutions, and truncation all affect output. Saving the rendered prompt makes any output explainable without re-rendering.

**Why sequential numbering:** call order matters for debugging multi-pass runs. The sequence number lets you reconstruct execution order across trace files regardless of call name.

**Why call numbers in the filename:** call numbers are the stable D15 identifiers. They allow trace files from different runs to be compared by call type without string matching on call names.

### Schema validation

Every LLM call output is validated against a Pydantic v2 schema before being used downstream. On validation failure, the call is retried once with the error appended to the prompt. If the retry also fails, the call raises rather than passing invalid data forward.

**Why fail-fast on validation:** silent invalid data propagates through the pipeline and produces confusing downstream failures. A hard stop at the call boundary makes errors legible.

---

## Quality Evaluation — Reconstruction Critique (call #99)

`reconstruction_critique.j2` compares the reconstructed facts (title + content concatenated) against the original topic document. It identifies up to 4 specific problems per topic using the problem taxonomy (missing-content, not-standalone, not-canonical, not-template-ready, over-atomized, under-atomized, wrong-tags, other).

**Why reconstruction as the primary quality criterion:** Test 3 (Reconstruction) is the most objective and automatable of the Five Tests. If every fact from a topic document is reconstructible to that document, the facts are informationally complete. Tests 1, 2, 4, and 5 are checked secondarily by the critique prompt.

**Why limit to 4 problems per topic:** forces the model to identify the most significant issues rather than producing an exhaustive list. A long list of minor issues is less actionable than a short list of significant ones.

---

## Root Cause Attribution — Diagnosis (call #98)

`root_cause_analysis.j2` runs after critique for any topic with problems. It receives Pass 1 scan records, the Pass 3 topic document, the Pass 4 extracted facts, and the critique problems. It attributes each problem to the pass that introduced it.

Attribution logic:
1. Information present in topic document but absent from facts → **Pass 4 fault** (`fact_extraction.j2` dropped it)
2. Information in scan records but absent from topic document → **Pass 3 fault** (assembly gap; rare)
3. Information absent from all scan records → **Pass 1 fault** (`topic_scanning.j2` never captured it)
4. Wrong slug or scope_qualifier on a scan record → **Pass 1 fault** (wrong grouping)

Output per problem: `pass_attribution`, `component`, `explanation`, `recommended_fix` (a concrete prompt instruction to add or code change to make).

**Why attribution is a separate LLM call rather than embedded in the critique:** the critique compares reconstruction against source — it does not have access to the intermediate pipeline artifacts. Attribution requires seeing all three layers (Pass 1 records, Pass 3 document, Pass 4 facts) simultaneously, which is a different task with different inputs.

**Why the same external symptom can require different fixes:** a `missing-content` problem caused by Pass 1 never capturing a span requires a change to `topic_scanning.j2`. The same symptom caused by Pass 4 dropping a phrase from the topic document requires a change to `fact_extraction.j2`. Without attribution, prompt fixes are guesses.

---

## Chain B — Change Request → Proposal

Uses the Chain A corpus as input. Three calls per affected fact.

### Retrieval — two stages

**Stage 1 (embedding similarity):** each fact's `content` is embedded at index time using OpenAI `text-embedding-3-small`. At query time, embed the change request and return top-K by cosine similarity. In-memory numpy; no external vector DB needed at POC scale.

**Why embedding similarity first:** cheap and fast. Narrows a corpus of hundreds of facts to a manageable candidate set.

**Stage 2 — Call #1 (affected fact identification, `affected_fact_identification.j2`):** the LLM receives the top-K candidates and reasons about which are actually affected. Returns each affected fact with a relevance score (1–5) and reason; facts below relevance 3 are dropped.

**Why a second stage:** embedding similarity finds semantically similar facts, not necessarily affected ones. A fact about "student dress code" is similar to a query about "staff dress code" but not affected by it. The LLM corrects these false positives.

### Per-affected-fact calls

**Call #2 — Fact content drafting (`fact_content_drafting.j2`):** receives the change request and current fact content. Produces `revised_content` and `change_summary`. Instructions: incorporate the change precisely, preserve all unaffected content, do not hallucinate adjacent changes.

**Call #3 — Topic tag recommendation (`topic_tag_recommendation.j2`):** reviews the revised content and recommends tag additions or removals.

**Why split into two calls:** content revision and tag management are distinct reasoning tasks. Combining them in one prompt produces worse results on both.

---

## LLM Provider Abstraction

`LLMProvider` is an ABC with a single `complete(prompt, output_schema, model)` method. Three implementations: `AnthropicProvider` (tool_use), `OpenAIProvider` (JSON schema strict mode), `GeminiProvider` (response_mime_type JSON).

All calls route through `llm.call()`, which handles: prompt rendering, provider dispatch, schema validation, retry on validation failure, trace printing, and trace file writing.

**Why a custom ABC rather than LiteLLM or similar:** security boundary. A unified gateway library creates a dependency on a third party with access to all API keys and all prompt content. The ABC is ~50 lines and covers all three providers the POC needs.

**Why `model_string = "provider/model-name"`:** makes the provider explicit at the call site. There is no default provider. Every run requires a `--model` argument.

---

## Call Number Taxonomy

Call numbers are stable identifiers, not execution sequence numbers. They are used in trace filenames and in `_result_summary()` dispatch.

| # | Name | Chain | Pass |
|---|---|---|---|
| 11 | scope_inference | A | Pre-pass |
| 1 | topic_scanning | A | Pass 1 |
| 4 | fact_extraction | A | Pass 4 |
| 1 | affected_fact_identification | B | Retrieval stage 2 |
| 2 | fact_content_drafting | B | Per-fact |
| 3 | topic_tag_recommendation | B | Per-fact |
| 99 | reconstruction_critique | Eval | Post-extraction |
| 98 | root_cause_analysis | Eval | Post-critique |

Note: call #1 is reused for both `topic_scanning` (Chain A) and `affected_fact_identification` (Chain B). The call name disambiguates them in traces.
