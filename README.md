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

## Design documents

- [System Design](docs/system-design.md) — full decision log with rationale for every architectural choice
- [Change Loop — Workflow Diagram](docs/workflow-change-loop.md) — the central workflow from request to post-publish engagement
- [Core Data Model](docs/data-model.md) — entities, relationships, and scope resolution rules
