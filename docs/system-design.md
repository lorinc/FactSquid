# FactSquid — System Design

## Context and Core Problem

A massively multi-tenant knowledge management SaaS for schools. Each tenant is a school. The corpus is managed by school administrators and leads. Consumers are parents, all staff, and applicants.

The core pain is threefold:
- **Version and approval hell**: changes propagate unreliably across documents and channels
- **Document-editing overhead**: every change requires hours of manual reformatting across multiple formats
- **Info dump failure**: the end product — monolithic handbooks — is not read. Staff and parents call or email instead of consulting the documentation

The system's goal is not just to manage documents better, but to make the corpus **conversational and always current**, eliminating the need for anyone to read a handbook.

---

## Decision Log

### D1 — The corpus is a flat fact store, not a knowledge graph

Facts are clearly-scoped paragraphs on specific topics. They are not sentence-level atoms, not full documents, and not nodes in a semantic graph. The granularity is "the attendance policy paragraph" or "the peanut allergy clause" — a human-writable, human-readable unit with a single clear topic.

**Why not a knowledge graph**: introduces relational complexity that breaks the zero-friction requirement and makes the system too fragile for non-technical administrators.

**Why not full documents**: defeats the "update once, appear everywhere" model and reintroduces the document-editing overhead problem.

---

### D2 — Facts are flat; document structure lives in templates

Early consideration: facts in a parent-child hierarchy, reflected as H1/H2/H3 in rendered documents. Rejected because a single fact routinely belongs in multiple documents — a dress code fact appears in the Behaviour Policy, the Staff Handbook, and the Parent Handbook simultaneously.

**Decision**: facts carry **topic tags**. Document templates define a section hierarchy (H1/H2/H3) and declare which topic tags belong in each section. At render time, facts slot into every section where their tags match — across multiple documents, with no duplication of the source fact.

**Implication**: the LLM's job when proposing a change is to recommend topic tags. The tags implicitly determine where the fact appears. The human confirms or adjusts tags, not document placement.

---

### D3 — Fact metadata schema

Every fact carries the following fields:

| Field | Purpose |
|---|---|
| `content` | Markdown body — the canonical phrasing of the fact |
| `type` | Semantic type: `policy`, `event-detail`, `announcement`, `menu-item`, etc. |
| `topic_tags` | One or more topic tags determining section placement in templates |
| `audience_scope` | Who can see this fact: `staff`, `parents`, `applicants`, `students`, etc. |
| `channel_scope` | Which channels receive this fact on publication |
| `approval_scope` | Which approval rule applies to changes on this fact |
| `owner` | The role or user responsible for keeping this fact current |
| `publication_date` | When this fact is pushed to its channels — triggers the publication pipeline |
| `effective_date` | When this fact's content is in force (e.g., a policy published in March but effective from September) |
| `expiry_date` | When this fact triggers a review or sunset workflow |
| `status` | `stub` or `live`. Stubs have metadata but no real content — placeholders proposed by the LLM to represent expected-but-unwritten sections. Stubs block publication on non-optional sections; they do not block commit. |
| `group` | Optional. References a named group in tenant config. Facts inherit the group's shared metadata fields (`effective_date`, `expiry_date`, `approval_scope`). Per-fact overrides are allowed but flagged. Used for events and any other coherent publication bundle with shared lifecycle properties. |

Scopes are multi-dimensional and independent. A fact can be visible to parents and staff (audience), appear in the handbook and newsletter (channel), and require legal sign-off (approval) — all configured separately.

---

### D4 — Git as the persistence and versioning layer

Facts are stored as markdown files in a git repository. Metadata is stored as frontmatter.

**What git solves out of the box**: version history, rollback, audit trail, change attribution (blame), diffing between versions, and legal look-back ("what did the policy say on this date").

**Implication**: the application layer does not need to model versioning, change logs, or archiving. These are infrastructure concerns, not application concerns. The system remains append-friendly and the history is immutable by design.

**Complete tenant restore requires three additional artifact types in the repo:**

- **Rendition override diffs**: the LLM channel transform and the canonical fact are both reproducible. Human editorial overrides applied to a rendition are not — they represent judgment calls that cannot be regenerated. The minimum non-derivable artifact is a per-rendition override diff, committed alongside the fact it modifies.

- **Approval audit records**: git commit history captures what changed and when, but not who approved it under which rule. A structured record per committed bundle — approver identities, timestamps, the approval rule version in effect, and the bundle it governed — is required for legal look-back ("who signed off on the medication policy change on this date"). This is committed as a structured file at the time of approval.

- **Bundle provenance records**: the git log shows what the corpus looks like at any point in time, but not why a change was made or who requested it. A structured record per committed bundle — requester identity, original natural language request, bundle ID — makes the history interpretable without an external database.

Everything else is derivable from the repo: channel renditions can be regenerated by re-running the publication pipeline (overrides preserved), the chatbot KB index can be rebuilt by re-running KB pre-processing, and rendered HTML/PDF can be reproduced by re-running the deterministic renderer. User accounts, engagement responses, and in-flight draft bundles are operational/per-user data and live outside the repo.

---

### D5 — Two document assembly models

Documents are not uniformly structured. Two distinct assembly models were identified:

**Changelog (Newsletter)**
Time-driven. Collects all facts changed within a period and assembles them into a narrative. The LLM writes connective language around the changed facts. No fixed structure — the structure emerges from what changed. Analogous to a game update changelog.

**Taxonomy-driven (Policy / Handbook / Event page)**
Structure-driven. All facts matching a channel scope are assembled according to the channel template's section hierarchy. Topic tags determine placement. When a new fact is added, it auto-slots into the correct section. The document is always complete and always current.

Event pages are taxonomy-driven documents. An event's template defines sections (date, venue, schedule, dress code, catering); topic tags determine placement within those sections. The event's facts are scoped to the event's channels via `channel_scope`, and share lifecycle metadata via `group`. See D14.

---

### D6 — The publication pipeline

Publishing is not a single step. For each fact reaching its publication date, the pipeline is:

```
Canonical fact (markdown)
  → LLM channel transform (per channel, per tenant: tone, style, narrative fit)
  → Channel-specific markdown draft
  → Human override window
  → Deterministic render (markdown → HTML → PDF via CSS)
```

**Two artifacts are maintained**: the canonical fact (source of truth) and one rendered rendition per channel. The renditions are derived, not authoritative.

**Channel LLM transform**: configured per channel, per tenant. The same dress code fact becomes formal legal language in the policy document and a friendly reminder in the newsletter. The transform is instructed by the channel's semantic configuration — not just tone, but also structural expectations ("this channel uses bullet points for rules").

**Human override**: after LLM transformation and before final render, an administrator can edit the channel-specific draft. Overrides are scoped to the rendition, not the canonical fact. Overrides are tracked (via git) but do not propagate back to the fact.

**Chatbot KB as a separate branch**: the chatbot knowledge base is a channel, but its pre-processing pipeline diverges from the HTML/PDF path. Facts must be chunked, indexed, and embedded for semantic retrieval. This is a distinct publication step with its own configuration.

---

### D7 — Coherence as a constraint, not a lint

Initial framing: a lint that checks corpus coherence and warns on problems (orphaned facts, empty template sections).

**Revised decision**: the system enforces coherence as a hard constraint. Inconsistency cannot be committed. There is no warn-and-proceed path.

**Rationale**: an orphaned fact — a fact with topic tags that match no template section — is invisible to all users and all channels. It has no purpose. Allowing it to exist would be a data quality failure. Similarly, a template section that references a topic no facts are tagged with produces a broken document.

**How it works**: when a proposed change would create an inconsistency, the system does not block and wait. It automatically extends the proposal to include a resolution — re-tag the orphan, add a new template section, redirect affected links. The human reviews and approves a **coherent bundle**, never a partial change.

**Empty sections**: whether an empty template section auto-hides or renders visibly is a **per-section attribute** configured in the template, not a system-wide policy. Some sections may intentionally display as placeholders ("Coming Soon"); others should disappear when empty.

---

### D8 — The change workflow

The central loop of the system:

1. **Request intake**: any stakeholder submits a natural-language request ("we need to update the medication policy to include EpiPens")
2. **LLM fact discovery**: the LLM identifies which existing facts are affected, using semantic search against the corpus
3. **LLM proposal**: the LLM proposes a coherent bundle — edits to affected facts, new facts if needed, topic tag updates, and template changes if the new content doesn't fit the current structure
4. **Coherence gate**: the system validates the bundle. If it would create an inconsistency, the bundle is extended with a resolution before being shown to the human
5. **Human iteration**: the proposer reviews, edits, and confirms the bundle. The LLM adjusts on feedback
6. **Approval routing**: the bundle is routed to approvers determined by the approval scope of the affected facts
7. **Scheduled publication**: approved changes are queued for their publication date
8. **Post-publish engagement**: triggered per fact change, based on engagement configuration

**Key principle**: the LLM is not an assistant in this workflow — it is the primary author. The human's role is judgment and confirmation, not drafting.

---

### D9 — Approval engine

Approval rules are configured **per tenant**. The approval scope field on a fact determines which rule applies to changes on that fact.

Examples of approval scope configurations:
- `self-service` — no approval required (e.g., next week's menu)
- `head-of-school` — single sign-off from the principal
- `legal` — requires sign-off from a legal officer
- `multi-stakeholder` — requires sequential or parallel sign-offs from multiple roles

The approval engine routes the change bundle to the correct approvers, collects approvals, and unblocks publication when the approval matrix is satisfied. Approval is always human — the AI flags, routes, and reminds, but never approves.

---

### D10 — Engagement engine

After publication, some fact changes require a response from the audience. Two types:

- **Acknowledgment**: the recipient must confirm they have read the change ("I've read and understood the updated medication policy")
- **Feedback**: the recipient is invited to respond ("Please share your thoughts on the new lunch menu")

Engagement is configured per fact change at the time of the change workflow, not as a fixed fact attribute. The engagement engine:
- Targets the correct audience (driven by audience scope)
- Tracks responses per audience member
- Sends reminders to non-respondents
- Surfaces completion rates to administrators

---

### D11 — Consumer interface

LLM-powered natural language Q&A over the corpus. Scoped by:
- **Tenant**: a parent at School A cannot see anything from School B
- **Audience role**: within a school, a parent cannot see staff-only facts

Powered by the chatbot KB channel (see D6). The consumer does not browse documents — they ask questions and receive answers grounded in the current corpus. This is the primary mechanism for replacing "call the school to ask a question."

---

### D12 — Tenant configuration

Each school configures its own instance of:
- **Channels**: which delivery channels exist (newsletter, staff handbook, parent handbook, event pages, chatbot)
- **Channel templates**: section hierarchy per channel, topic-to-section mappings, LLM transform instructions, empty section behavior
- **Approval rules**: named approval scopes and their corresponding approver roles/chains
- **Audience roles**: the set of audience categories relevant to this school and their visibility permissions
- **Engagement defaults**: default engagement type per fact type or approval scope

Tenant configuration is itself versioned (also in git) and changes to it go through a simplified approval flow.

---

### D13 — Onboarding by document ingestion, not blank-slate setup

**Decision**: onboarding initialises the corpus by extracting structure and facts from the school's existing documents, not by asking administrators to configure templates from scratch or choose from a library of starter templates.

**Rationale**: two competing approaches were considered:

- *Proposed setup*: the LLM analyses uploaded documents and proposes an optimised template structure from first principles. Likely produces better-structured templates, but confronts the administrator with an unfamiliar organisation of their own content.
- *Extracted setup*: the LLM infers template structure directly from the heading hierarchy of uploaded documents. The result looks like what the school already had — same sections, same organisation — just decomposed into facts.

The extracted approach was chosen on psychological grounds: administrators adopt systems that feel like improvements on the familiar, not replacements of it. The heading hierarchy of an existing staff handbook already encodes the school's mental model of how information should be organised. Overriding that model during onboarding creates resistance; preserving it creates trust.

**What the LLM extracts reliably:**
- Template section hierarchy (from document headings → H1/H2/H3)
- Topic tags (inferred from section names)
- Fact decomposition (body content split into scoped paragraphs under their sections)
- Audience and channel scope (inferred from document type: "parent handbook" → `audience: parents`, `channel: parent-handbook`)

**What the LLM cannot reliably extract and flags for human input:**
- Approval scope (who owns this policy — not inferable from content)
- Ownership (which role is responsible for keeping this fact current)
- Expiry dates (rarely stated explicitly in legacy documents)

**Onboarding flow:**
1. Administrator uploads existing documents
2. System proposes extracted template structure and decomposed facts
3. Administrator reviews — recognises their own structure and content, reorganised
4. Administrator fills in flagged gaps (approval scope, ownership, expiry)
5. Corpus goes live

Onboarding is structurally the first run of the change workflow, with document ingestion as the request. Administrators learn the review-and-confirm pattern on familiar content before any real change is made.

**Cross-document deduplication**: schools uploading multiple documents (staff handbook, parent handbook, safeguarding policy) will have the same facts stated differently across them. The LLM detects overlapping content and proposes consolidation — one canonical fact with the appropriate channel and audience scope — rather than creating near-identical facts that will diverge over time. Proposed consolidations are surfaced explicitly during review, since merging two differently-worded statements of the same policy requires human judgement on which phrasing is authoritative.

---

### D14 — Event groups: shared metadata and multi-channel routing

Events require two things the flat fact schema (D3) does not provide by default: shared lifecycle metadata across all facts belonging to the event, and multi-channel publication (PDF, HTML page, chatbot KB) from a single authoring act.

**Shared metadata via the group registry**

All facts in a spring break event share `publication_date`, `effective_date`, `expiry_date`, and `approval_scope`. Duplicating these across every fact creates a consistency risk — one mistyped date produces a valid-but-wrong fact the coherence gate cannot catch.

Resolution: facts carry an optional `group` field referencing a named entry in tenant config (D12). The group definition holds the shared metadata:

```yaml
# Tenant config — group registry
spring-break-2026:
  publication_date: 2026-03-17
  effective_date: 2026-04-14
  expiry_date: 2026-04-22
  approval_scope: head-of-school
  default_channel_scope: [event-page, chatbot]
```

Facts in the group inherit these fields. Per-fact overrides are allowed (e.g., a logistics-only fact excluded from the chatbot) but are flagged during review. The coherence gate enforces that inherited and overridden dates are consistent within the group.

**Multi-channel routing via `channel_scope`**

Events publish to multiple channels: an event page (rendered as both HTML and PDF — two output formats of one channel), the chatbot KB, and optionally the newsletter. `channel_scope` handles this directly. The group's `default_channel_scope` sets the baseline; individual facts override where needed.

**Progressive completion via stubs**

An event is rarely fully detailed at creation time. When the LLM proposes a new event bundle, it examines the event template and proposes stub facts for all non-optional sections it cannot yet populate — each stub has full metadata (`type`, `group`, `topic_tags`, `owner`, `approval_scope`) but no real content. The administrator reviews and confirms the complete intended structure, including stubs, as part of the initial bundle. Stubs make gaps explicit and assignable from the first commit.

Filling a stub is a normal D8 change workflow on an existing fact. The `owner` field creates the assignment — the stub is a concrete work item for a named role.

Stubs do not block commit but do block publication on non-optional template sections. The publication pipeline checks for unresolved stubs before rendering and refuses to proceed if any remain. Reminders are sent to stub owners as `publication_date` approaches.

**Why the grouping-driven model was retired (see D5)**

The earlier framing — "an event is a named parent fact with child facts belonging to it" — introduced a fact-to-fact hierarchy, which D2 rejected for document structure. The same problem applies here. The group is not a fact; it is a configuration entity in the tenant config, already the established pattern for named approval rules and audience roles. Facts reference a config entity, not another fact. The flat fact store remains flat.

**Why `type: event-detail/spring-break-2026` was rejected**

The slash notation encodes both semantic category (`event-detail`) and instance identity (`spring-break-2026`) in a single field. This unbounds the type vocabulary — every new event creates a new type — and forces the pipeline to use prefix pattern-matching instead of exact matching. Type is a bounded semantic classifier. Instance identity belongs in `group`. Two fields, two concerns.

---

### D15 — LLM call taxonomy: one output type per call, context by injection

The system relies heavily on LLM judgment across every subsystem. Left unconstrained, LLM calls become the hardest part of the system to test, debug, and improve. The governing principle:

**Each LLM call produces exactly one type of output.** Output types are: generate content, classify/tag, detect/identify, or infer structure. Calls that mix types fail in different ways simultaneously — the error is unlocatable, the call is untestable in isolation, and no single improvement to the prompt or model can fix both failure modes at once.

**Context loss is not a reason to bundle.** The legitimate concern with splitting calls is that joint reasoning is lost — a single call drafting content and recommending tags can reason about both together. The mitigation is output chaining: the result of each call is passed as context into the next. A tag recommendation call receives the just-drafted content as input. The model has full context; the output is still narrow and validatable. Wider context is always addable to a narrow task. Bundling outputs is never the right solution to a context problem.

**Structured output schemas are mandatory.** Every call in this taxonomy produces a machine-validatable output — a typed JSON schema with strict field requirements. Validation happens before the output is consumed by the next step. A call that returns a malformed structure is retried or escalated, not passed forward.

#### Call taxonomy

| # | Call | Subsystem | Output type | Output |
|---|---|---|---|---|
| 1 | Affected fact identification | Change workflow | Detect | Ranked list of fact IDs relevant to the request |
| 2 | Fact content drafting | Change workflow | Generate | New or revised markdown content per fact |
| 3 | Topic tag recommendation | Change workflow | Classify | Tag set per fact |
| 4 | Template change identification | Change workflow | Infer structure | Required section additions or renames |
| 5 | Coherence resolution | Change workflow | Generate | Specific resolution for one detected violation |
| 6 | Bundle revision | Change workflow | Detect | Which bundle items to change, given human feedback |
| 7 | Stub metadata generation | Event groups | Classify | Tags and owner suggestion per empty template section (no content) |
| 8 | Heading hierarchy extraction | Onboarding | Infer structure | Section tree from document headings |
| 9 | Topic tag inference | Onboarding | Classify | Tag set per section name |
| 10 | Fact decomposition | Onboarding | Generate | List of atomic fact paragraphs per section |
| 11 | Scope inference | Onboarding | Classify | `audience_scope` and `channel_scope` per document |
| 12 | Overlap detection | Onboarding | Detect | Binary: do these two facts overlap? |
| 13 | Consolidation drafting | Onboarding | Generate | Canonical merged fact content for an overlapping pair |
| 14 | Channel transform | Publication | Generate | Channel-specific rendition of one fact for one channel |
| 15 | Newsletter narrative assembly | Publication | Generate | Connective text linking changed facts in a changelog channel |
| 16 | Q&A answer generation | Consumer interface | Generate | Grounded answer from retrieved facts |

Calls 3 and 9 share a task type (tag classification) but operate in different contexts and will have different prompt configurations and evaluation sets. They are listed separately to make that explicit.

Call 5 (coherence resolution) may loop — one call per violation, fed back into the coherence gate until the bundle is clean. Each iteration is a separate call with the current bundle state as context.

---

## Supporting Documents

- [Change Loop — Workflow Diagram](workflow-change-loop.md)
- [Core Data Model](data-model.md)

## Functional Map Summary

| Area | Responsibility |
|---|---|
| **Fact Store** | Flat markdown facts in git, with typed metadata and multi-dimensional scopes |
| **Change Workflow** | LLM-driven request → coherent bundle proposal → human iteration → approval → publication |
| **Approval Engine** | Per-tenant routing rules driven by fact approval scope |
| **Publication Engine** | Per-channel LLM transform → human override → deterministic render → channel delivery |
| **Engagement Engine** | Post-publish acknowledgment and feedback tracking per audience member |
| **Consumer Interface** | Scoped LLM Q&A over the corpus |
| **Tenant Configuration** | Per-school channels, templates, approval rules, audience roles |
| **Onboarding Engine** | Document ingestion → structure extraction → guided review → corpus initialisation |
