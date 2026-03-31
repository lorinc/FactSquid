# FactSquid
> Change a fact. Let the squid work.
<p align="center"><img src="data/transparent_kraken.png" width="400"></p>

School policy management is broken in a predictable way. Policies live in Word documents and shared drives. Newsletters are assembled by hand from scattered sources. Every change requires editing multiple files, reformatting for every channel, chasing approvals over email, and publishing to a website that nobody reads. Staff and parents call the school instead of consulting the handbook — because the handbook is a 60-page PDF that is already out of date, and the newsletter from last week contradicts it.

FactSquid replaces documents with a **living corpus of facts**. A fact is a scoped paragraph on a single topic. Facts are the source of truth. Documents, newsletters, chatbot answers, and parent portals are all derived from the same facts — automatically, across every channel, every time something changes.

## Problems and solutions

**Version hell** → Facts are stored in git. Every change is tracked. Rollback, audit trail, and legal look-back are handled at the infrastructure level, not the application level.

**Approval chaos** → Every fact carries an approval scope. Changes are bundled and routed automatically to the right approvers — self-service for a menu update, legal sign-off for a regulated policy clause.

**Multi-channel reformatting** → Each channel has an LLM transform layer that rephrases the same fact appropriately — formal in the policy document, conversational in the newsletter. One change, every channel updated.

**Nobody reads the handbook** → The corpus powers a natural-language chatbot. Staff and parents ask questions and get answers. The handbook becomes something the system consults on their behalf.

**Onboarding friction** → Schools upload their existing documents. FactSquid extracts the structure and facts from what they already have. The first view looks like their own content, reorganised — not a blank slate.

**Structural drift** → The system enforces corpus coherence as a hard constraint. A fact that appears nowhere, or a template section that references nothing, cannot be committed. Every proposed change ships as a coherent bundle.

## What the system does automatically

| When | What the system does |
|---|---|
| **Setting up a new school** | Reads your existing documents and maps their section structure |
| | Infers which topic category each section belongs to |
| | Splits each section into individual, self-contained policy facts |
| | Works out who should see each document and which channels it belongs in |
| | Spots when two documents say the same thing in different words |
| | Drafts a single merged version of any duplicated content for your review |
| **When a change is requested** | Finds which existing facts are affected by the request |
| | Drafts updated or new policy text |
| | Suggests which topic categories the new content belongs to |
| | Identifies whether new document sections are needed to fit the new content |
| | Adjusts the proposal in response to your feedback |
| **Before anything is saved** | Detects when a change would leave a fact with nowhere to appear, or a section with nothing in it |
| | Proposes a specific fix for each gap or inconsistency found |
| **When publishing** | Rewrites each fact in the right tone for each channel — formal for policy documents, conversational for newsletters |
| | Writes the connecting narrative that links updates together in a newsletter |
| **When planning an event** | Generates placeholder entries for missing event sections with suggested owners |
| **When someone asks a question** | Finds the relevant facts and writes a plain-language answer, noting exactly which facts it drew from |
| **Always, in the background** | Manages the full change lifecycle — from request through approval to scheduled publication |
| | Routes changes to the right approvers and tracks who has signed off |
| | Schedules publication across all channels at the right time |
| | Sends reminders for missing content and outstanding approvals |

---

## Design documents

- [System Design](docs/design/system-design.md) — full decision log with rationale for every architectural choice
- [Technical Design](docs/design/technical-design.md) — agent coding spec: project layout, module boundaries, LLM runtime, Temporal workflows, persistence layers, library manifest

## Build plan

- [Epics](docs/plan/epics.md) — vertical slice build plan with UAT criteria per epic
- [Epic 0 — Observability Foundation](docs/plan/epic0.md) — architecture detail: repo structure, LLM call tracer, pipeline tracer, trace viewer spec
