# FactSquid — What Is a Fact?

This document defines what an ideal fact looks like, why the definition matters, and how it should shape the extraction pipeline. It is a constraint document, not a suggestion.

---

## Why This Needs a Precise Definition

The system's core promise — "update once, appear everywhere" — only works if facts are the right granularity. Too coarse and a change to one sentence forces a review of an entire paragraph that touches three unrelated topics. Too fine and the corpus becomes thousands of sentence-fragments that lose meaning in isolation.

More concretely: the onboarding pipeline (D13) extracts facts from existing school documents and proposes them for administrator review. If the extracted facts don't match the administrator's mental model of "a thing I'd want to edit", they won't trust the system and won't complete onboarding.

The ideal fact is the thing an administrator would naturally reach for when someone says "can you update the medication policy?"

---

## The Five Tests for an Ideal Fact

A fact passes if and only if it satisfies all five tests simultaneously.

### Test 1 — Stand-Alone

Read the `content` field alone, with no surrounding facts and no knowledge of the source document.

A staff member who has never seen the source document must be able to fully understand the policy, rule, or procedure. If a reasonable reader would ask any of the following, the fact fails:

- "Who does this apply to?"
- "When does this apply?"
- "What's the exception?"
- "Apply in addition to what?"

All necessary context must be inside the fact. Cross-references to other facts ("see also: medication policy") are allowed as navigational aids but the fact must stand without them.

### Test 2 — One Topic

Write a single noun phrase that names this fact's subject. If the phrase requires "and" to be accurate, the fact contains two topics and must be split.

| Passes | Fails |
|---|---|
| "Late collection fee" | "Late collection fee and early drop-off rules" |
| "Emergency medication procedure" | "Medication procedure and contact details for the nurse" |
| "Student dress code — acceptable items" | "Student dress code and staff dress code" |

Note: a fact may contain multiple related sub-rules under one topic without violating this test. "Acceptable items" and "unacceptable items" for the dress code are two sides of one topic. An intro paragraph + a bullet list is one topic if the bullets elaborate the intro.

### Test 3 — Reconstruction

Take all facts extracted from one topic document and concatenate their `content` fields (with their titles as headings). The result must be **informationally equivalent** to that topic document.

- Same obligations. Same permissions. Same exceptions. Same numerical values.
- Different words are fine. Better organisation is fine. Removing redundancy is fine.
- Missing information is a failure: a fact was not extracted.
- Added information is a failure: a fact was hallucinated or over-generated.

This is the primary quality criterion for extraction. Since a topic document is assembled from source spans, passing this test transitively covers the source material.

### Test 4 — Canonical Form

The content should read as if an administrator wrote it from scratch today — not as it happened to appear in a legacy PDF.

**Fails canonical form:**
- Document-navigation language: "As mentioned in section 3.2...", "Refer to the appendix for..."
- Document-framing language: "This handbook states that...", "In this policy we define..."
- Redundant preamble: "It is important to note that students must..."

**Passes canonical form:**
- Active voice, plain English
- Hedging that is itself the policy is kept: "The school aims to provide..." is a legitimate principles-type fact
- Tables, bullet lists, and numbered steps are preserved when they are the natural structure for the content

The test: could this content be read aloud at a staff briefing as a self-contained statement of policy, with no need for the listener to know which document it came from?

### Test 5 — Template-Slot Ready

This fact must be insertable into any document that needs it — staff handbook, parent handbook, chatbot KB — without content modification (only tone/style transforms at publication time, per D6).

**Fails template-slot readiness:**
- Audience-specific framing baked into content: "As a parent, you should be aware that..."
- Channel-specific framing: "As you read this handbook..."
- Instance-specific framing that belongs in metadata: "For the 2024–2025 academic year..."

The test: if you removed all metadata fields and read only the `content`, would the fact still be true and applicable regardless of which document it appears in?

---

## What a Fact Is Not

| Not a fact | Why | Correct handling |
|---|---|---|
| A single sentence extracted verbatim | Usually lacks stand-alone context | Rewrite as canonical form, include necessary context |
| A full section of a document | Almost always contains multiple topics | Split at topic boundaries |
| A navigation entry ("See section 4 for...") | No informational content | Skip entirely |
| A list of legislation titles | No policy content | Skip entirely |
| "This section covers X, Y, and Z" | Introductory meta-text | Skip entirely |
| A contact detail embedded in a policy paragraph | Different type, different lifecycle | Extract as a separate `contact-detail` fact |
| A fee buried in a procedures paragraph | Different type, different update cadence | Extract as a separate `fee` fact |

---

## Fact Size as a Symptom, Not a Criterion

Size (character count) is not a quality measure for facts. It is a symptom of quality problems:

- **Very short facts (< 200 chars)** usually mean a related piece of content was split off unnecessarily, or the fact is a sentence fragment that fails the Stand-Alone test.
- **Very long facts (> 2500 chars)** usually mean two distinct topics were merged, failing the One-Topic test.

When size seems wrong, apply the One-Topic test and Stand-Alone test — not a character limit. A fee schedule with a complex table may legitimately be 3000 characters. A one-sentence fire evacuation rule may legitimately be 120 characters.

---

## Fact Kind

Source documents interleave two types of content: the rule itself, and the reasoning behind it. Both are valuable and both can pass the Five Tests. They have different update cadences and different downstream uses.

A fact carries an optional `kind` field:

| Kind | What it is | Example |
|---|---|---|
| `policy` | The rule, obligation, or procedure | "Students must wear full uniform on all school days." |
| `rationale` | Why the policy exists | "The uniform policy aims to reduce visible socioeconomic difference between students." |
| `principle` | Aspirational or values language | "The school aims to foster an inclusive environment for all students." |
| `context` | Historical or background information | "The current dress code was introduced in 2019 following a parent consultation." |

**Default: do not assign `kind`.** The field is only populated when the extracted content clearly belongs to one of the non-`policy` kinds *and* separating it adds value. Most facts are policy facts; adding `kind` to every fact fragments the store without benefit.

The `kind` decision is made at the end of extraction (Pass 4), not upfront. If a topic document contains both a rule and a rationale worth separating, they become two facts with different `kind` values. If the rationale is a single clause that belongs inside the policy statement, it stays there.

---

## Extraction Pipeline

### Core Principle: Concentrate Before Extracting

Human-written documents are messy. The same topic appears in multiple sections, paragraphs span topic boundaries, and the same policy is restated in different words across the document. Linear per-section extraction produces facts that are incomplete, duplicated, or scope-confused.

The solution is to concentrate all content about a topic before attempting final extraction. The pipeline does this in four passes.

---

### Pass 1 — Topic Scanning *(structural inference, per section)*

**Input:** each source section (heading + body text)

**Output:** one record per paragraph or logical block:
```
{ topic_slug, scope_qualifier, span_text, source_path }
```

**The unit of analysis is the paragraph or logical block, not the section.** The section heading is provenance context, not the topic. A section titled "Communication Between Families and the School" may contain records with slugs like `communication-tools/phidias`, `communication-language/general`, and `communication-channels/newsletter`. The model must ask, for each paragraph: *what is this paragraph actually about?*

- `topic_slug` — normalised, hierarchical identifier: `dress-code/general`, `dress-code/outdoor-events`, `communication-tools/phidias`. The model must produce consistent slugs across sections. This is where merge logic lives — two records with the same slug and qualifier will be grouped mechanically in Pass 2, so the slug must be stable.
- `scope_qualifier` — what makes this instance distinct from other instances of the same topic: `students`, `staff`, `2024-2025`. If no scope distinction applies, omit.
- `span_text` — verbatim paragraph(s). **No summarisation. No rewriting.** The source text is ground truth. Capturing text directly rather than offsets simplifies Pass 3 assembly and eliminates offset-tracking bugs.
- `source_path` — provenance heading for this span: `Family Manual > 12. Dress Code`. Used as a heading in Pass 3 topic document assembly.

The model is doing structural inference only: *where* does this topic appear, and *what scope* applies. It does not write or summarise content. Asking for summaries here is wasteful — they are paid for once and discarded, and a bad summary silently corrupts the grouping step.

**Orphan preamble** — introductory paragraphs that are pure rationale or aspirational framing with no policy content ("At Imagine, we believe that smooth communication is crucial...") should be assigned a `**/principles` slug (e.g. `communication/principles`) or flagged as `skip-candidate`. Pass 4 decides whether they become a `principle`-kind fact or are dropped.

**Paragraph spanning two topics** is a known failure mode. Accept it: include the full paragraph in both records. Pass 4 handles the duplication.

---

### Pass 2 — Grouping *(mechanical, no LLM)*

Group all Pass 1 records by `(topic_slug, scope_qualifier)`.

No LLM call. The slug normalisation in Pass 1 did the semantic work; grouping is pure key equality.

---

### Pass 3 — Topic Document Assembly *(mechanical, no LLM)*

For each group, assemble a **topic document**:

1. Concatenate verbatim `span_text` for all records in the group.
2. Prefix each span with its `source_path` as a heading, so provenance is visible to Pass 4.
3. **Contradiction flag:** if two spans contain conflicting numeric values or opposing obligations on the same subject ("must" vs "must not", different values for the same parameter), mark the topic document for human review before Pass 4 proceeds.

The result is a compact, scoped document containing all source material for one topic, in original wording, with provenance headings. Pass 4 operates on this, not on the raw source.

---

### Pass 4 — Fact Extraction *(generation, per topic document)*

**Input:** one topic document (assembled in Pass 3) + `audience_scope` and `channel_scope` from scope inference (call #11)

**Output:** the final fact set for this topic:
```
{ title, content, kind (optional), topic_tags }
```

This is the **only pass that writes content**. The model applies all Five Tests here. It has everything it needs: all source material for the topic is present, scoped, and attributed.

Responsibilities at this pass:
- Rewrite into canonical form (active voice, no document-navigation language)
- Eliminate redundancy across spans from different sections
- Split at topic boundaries if the assembled document turns out to contain multiple sub-topics
- Assign `kind` only when content clearly separates into a non-policy category and separating it adds value: `rationale`, `principle`, `context`. Default: no `kind`. Most facts are policy facts.

---

### Pass Summary

| Pass | Input | Output | LLM? |
|---|---|---|---|
| 1 | Each source section | `{topic_slug, scope_qualifier, span_text, source_path}` per paragraph | Yes — structural inference only |
| 2 | All Pass 1 records | Grouped by `(topic_slug, scope_qualifier)` | No — mechanical grouping |
| 3 | Groups | Topic documents (concatenated `span_text` with provenance headings) | No — mechanical assembly |
| 4 | Each topic document + scope metadata | Final facts: `{title, content, kind, topic_tags}` | Yes — generation |

The costly generation work is fully concentrated in Pass 4, where it is also individually evaluable. Passes 1–3 are either cheap inference or zero-cost mechanical steps.

---

## Reconstruction Test Applies at Pass 4

The Reconstruction test (Test 3) is verified at the topic-document level, not the source-section level: concatenating all facts produced from a topic document must be informationally equivalent to that topic document. Since the topic document is itself derived from source spans, this transitively covers the source.

The critique call (`reconstruction_critique.j2`) is a **verification** step against this criterion — not the place where quality is defined. Quality is defined here. The critique is used in the POC iteration loop (`run_iteration.py`) for development-loop feedback.

---

## POC Validation

The 4-pass pipeline was validated against a development corpus of four synthetic school policy documents (`poc/test_docs/`):

- **`test_doc_4`** — tests same-topic-different-scope: `dress-code/students` and `dress-code/staff` must produce separate topic documents
- **`test_doc_2`** — tests `kind` assignment: definitions, principles, and objectives mixed in one document
- **`test_doc_1`** — tests embedded type separation: fees and contact-details embedded in procedure text must be extracted as separate facts
- **`test_doc_3`** — tests stand-alone extraction from complex nested procedures

Key findings:
- **Verbatim text capture in Pass 1** (not offsets) eliminates assembly bugs and simplifies debugging
- **Slug stability** is the critical quality criterion for Pass 1 — inconsistent slugs break grouping
- **Most facts should not have `kind`** — over-assignment fragments the corpus without benefit
- **Reconstruction verification** catches both missing content (under-extraction) and hallucinated content (over-generation)
