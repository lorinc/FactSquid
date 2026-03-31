# FactSquid — Build Epics

## Guiding constraints
- Every epic is a thin cut through storage → LLM → rendering → human review
- Each epic ends with a UAT where a human sees real output, not a status page
- Observability is non-negotiable: every LLM call is a named, inspectable unit with prompt/output/validation visible before the next step consumes it
- Epics are ordered by **core loop criticality**, not surface area

---

## Epic 0 — Architecture & Observability Foundation

**What this is:** Set up the structural decisions that all subsequent epics depend on. No application logic yet — but everything real runs through the observability layer.

**Deliverables:**
- Tenant git repo structure: `/tenants/{tenant-id}/facts/`, `/tenants/{tenant-id}/config/`, `/tenants/{tenant-id}/artifacts/`
- Fact markdown + frontmatter schema (D3 fields exactly)
- LLM call tracer: every call emits a structured trace record — call ID, timestamp, named call type (from the D15 taxonomy), full expanded prompt, raw response, parsed structured output, validation result, latency, token counts
- Pipeline step tracer: a workflow execution is a named tree of steps; each step records its named inputs, the LLM call IDs it triggered, and its output state
- Trace viewer: a local web UI that renders a pipeline execution as a step timeline with drill-down into any LLM call
- Structured output schema definitions and validation for all 16 D15 call types (schemas only, no prompts yet)

**UAT:** Developer runs a synthetic pipeline execution with manually constructed inputs. Sees the full trace in the viewer. Deliberately injects a malformed LLM response and confirms the viewer shows the validation failure clearly.

See [Epic 0 detail](epic0.md).

---

## Epic 1 — Single Fact → Single Channel Publication

**What this is:** The simplest complete output path. Proves the publication engine and the LLM channel transform work end-to-end before any change workflow exists.

**Deliverables:**
- One tenant with one hardcoded fact (markdown + frontmatter) committed to git
- One channel (`parent-newsletter`) with a minimal template and LLM transform config
- LLM channel transform (D15 call #14): canonical fact + channel config → channel-specific markdown rendition
- Deterministic HTML renderer: markdown → HTML via CSS
- Publication runner: reads fact from git, runs transform, writes rendition, renders HTML
- Trace viewer integration: publication run visible as a pipeline with the LLM call fully inspectable

**UAT:** Admin puts a real policy paragraph in git as a fact, runs publication, opens the trace viewer. Sees the canonical fact, the LLM call #14 with full prompt and raw output, and the rendered HTML — side by side. Can immediately judge whether the channel transform is doing what was intended.

---

## Epic 2 — Change Workflow: Request → Bundle → Commit

**What this is:** The core daily loop. A human makes a request in natural language; the system identifies affected facts, proposes edits, human confirms, committed to git.

**Deliverables:**
- Semantic search over the fact store (embedding-based, simple vector index)
- LLM call #1 (affected fact identification): request + corpus → ranked fact IDs with relevance reasoning
- LLM call #2 (fact content drafting): affected facts + request → revised markdown per fact
- LLM call #3 (topic tag recommendation): revised content → tag set per fact
- Bundle assembler: constructs a `CHANGE_BUNDLE` with `BUNDLE_ITEM`s
- Bundle review UI: each proposed change as a diff (before/after), recommended tags, reasoning from each LLM call
- Human confirm/edit/reject → git commit with bundle provenance record (D4)
- No approval routing yet — all bundles are `self-service`

**UAT:** Admin types "update the medication policy to allow EpiPen administration". Sees which facts were identified with relevance reasoning, proposed edits as diffs with proposed tags, and can drill into any LLM call to see the exact prompt and raw output. Confirms, sees the git commit created with provenance record.

---

## Epic 3 — Onboarding: Document → Facts

**What this is:** The entry point for real tenants. A school uploads their existing handbook; the system decomposes it into the fact store.

**Deliverables:**
- Document upload handler (PDF/DOCX → raw text extraction)
- LLM call #8 (heading hierarchy extraction): returns section tree
- LLM call #9 (topic tag inference): tags per section name
- LLM call #10 (fact decomposition): atomic fact paragraphs per section
- LLM call #11 (scope inference): audience/channel scope per document type
- Onboarding review UI: proposed template structure + each extracted fact in its section; flags facts missing approval scope / owner / expiry for human fill-in
- Human confirms → facts batch-committed to git as initial corpus

**UAT:** Admin uploads a real excerpt of their staff handbook (2–3 sections). Sees the inferred section tree, each body paragraph decomposed into discrete facts with proposed tags, and flagged fields highlighted for input. Can drill into every LLM call to see why a fact was split the way it was.

---

## Epic 4 — Coherence Gate + Auto-Resolution

**What this is:** The safety mechanism that prevents the corpus from entering a broken state. Extends Epic 2's change workflow.

**Deliverables:**
- Coherence checker: validates that after applying a bundle, all facts have at least one matching template section, and all non-optional sections have at least one matching fact
- LLM call #4 (template change identification): when tags don't match any section, proposes section additions or renames
- LLM call #5 (coherence resolution, looping): one call per violation, produces a specific resolution; loops until bundle is clean
- Bundle review UI extended: coherence violations shown inline with their auto-proposed resolutions; human can accept or override each resolution

**UAT:** Admin makes a change that introduces a new topic with a tag no template section covers. Sees the coherence violation called out explicitly, the auto-proposed resolution (new template section), and the full LLM call trace for the resolution. Can accept, edit, or reject the resolution before committing.

---

## Epic 5 — Multi-Channel Publication

**What this is:** Proves the channel model — the same fact rendered differently for different audiences. Extends Epics 1 and 2.

**Deliverables:**
- Multiple channels configured: `staff-handbook` (formal), `parent-newsletter` (friendly), at minimum
- Publication pipeline runs LLM call #14 per channel per fact
- Human override window: after LLM transform, before final render; override tracked as a diff committed alongside the rendition (D4)
- Multi-channel rendition viewer: side-by-side display of all channel renditions for a fact, with their LLM call traces

**UAT:** Admin publishes one policy fact to both channels. Side-by-side: canonical fact, staff handbook rendition, parent newsletter rendition — each with its LLM call trace showing the transform instructions. Admin edits the newsletter rendition manually; sees the override diff recorded.

---

## Epic 6 — Approval Routing

**What this is:** Adds governance. Changes requiring sign-off are gated before publication.

**Deliverables:**
- Approval scope on facts wired to approval rules in tenant config
- Bundle approval scope resolution: most restrictive rule wins across all facts in bundle
- Approval engine: routes pending bundle to approver(s), tracks responses
- Simple approver notification (email or in-app)
- Approval audit record committed to git on bundle approval (D4)
- Bundle state machine: `draft → pending_approval → approved → scheduled → published`

**UAT:** Admin submits a change to the medication policy (approval scope: `head-of-school`). The head of school receives a notification with the bundle diff. Approves. Admin sees the bundle advance to `approved` and the approval audit record committed to git. Can inspect git history to see who approved what and when.

---

## Epic 7 — Consumer Q&A

**What this is:** The end-user interface. Replaces "call the school to ask a question."

**Deliverables:**
- Chatbot KB publication pipeline: chunking + embedding of facts scoped to the chatbot channel
- LLM call #16 (Q&A answer generation): retrieves relevant chunks by semantic search, generates a grounded answer citing fact IDs
- Consumer interface: simple chat UI scoped by tenant + audience role
- Answer trace: each answer shows which facts were retrieved, their relevance scores, and the full LLM call trace

**UAT:** Parent logs in, asks "what's the school's policy on EpiPens?". Gets a plain-language answer. In the admin/dev trace view: which facts were retrieved, relevance scores, the full LLM call with retrieved context and raw answer. Admin can immediately spot if the wrong fact was retrieved or the answer is inaccurate.

---

## Epic 8 — Event Groups

**What this is:** Shared lifecycle metadata across a coherent set of facts. The spring-break scenario from D14.

**Deliverables:**
- Group registry in tenant config (D14 YAML format)
- Fact `group` field inheritance: facts inherit publication/effective/expiry/approval from group
- LLM call #7 (stub metadata generation): given an event template, generates stub facts for unpopulated sections with full metadata but no content
- Stub publication blocking: pipeline checks for unresolved stubs before rendering
- Event bundle review UI: full event structure including stubs with owner assignments visible

**UAT:** Admin creates a "Sports Day 2026" event. System generates stub facts for all event template sections (date, venue, schedule, catering, dress code) with owner suggestions. Sections with unresolved stubs are visibly blocked from publication. Admin fills in one stub; that section unblocks.

---

## Epic 9 — Engagement Engine

**What this is:** Closes the loop — post-publish responses from the audience.

**Deliverables:**
- Engagement configuration on change bundles (type: `acknowledgment` or `feedback`, target audience roles)
- Engagement notifications to audience members post-publication
- Response tracking UI: completion rates per audience role, list of non-respondents
- Reminder sending to non-respondents
- Admin dashboard: outstanding engagement items and completion rates

**UAT:** Admin publishes an updated safeguarding policy with `acknowledgment` engagement targeting all staff. Staff receive the acknowledgment request. Admin sees the completion rate tick up as staff respond. Can see non-respondents and trigger a reminder.

---

## Epic 10 — Onboarding Deduplication

**What this is:** Completes the onboarding flow for schools with multiple overlapping documents.

**Deliverables:**
- Extend Epic 3 to accept multiple documents in one onboarding session
- LLM call #12 (overlap detection): pairwise comparison of extracted facts, binary overlap signal
- LLM call #13 (consolidation drafting): merged canonical fact for each overlapping pair
- Deduplication review UI: overlapping pairs shown side-by-side with the proposed consolidation; human chooses authoritative phrasing

**UAT:** Admin uploads both the staff handbook and the parent handbook. System flags facts that say the same thing differently across both documents. For each, admin sees both phrasings and the proposed merge, picks the authoritative phrasing; one canonical fact committed with appropriate audience and channel scope covering both origins.
