Your current design is already pointing in the right direction. The strongest parts are the flat fact store, template-driven assembly, the closed LLM call taxonomy, and the requirement that every LLM call be inspectable before downstream consumption. Those choices already bias the system toward deterministic seams and away from agentic sprawl.  

What I would do is make the architecture more explicit around bounded responsibilities, so the coding agent cannot blur domain logic, orchestration, and infrastructure.

A good target shape is a modular monolith first, with very hard internal boundaries, deployed as a few GCP-managed services rather than many microservices. Your epics are still early enough that microservices would mostly buy you distributed failure modes and prompt drift between services. The workflow you described is a sequence of stateful domain transitions around `FACT`, `CHANGE_BUNDLE`, `CHANNEL_TEMPLATE`, `APPROVAL`, `ENGAGEMENT`, and `GROUP`; that is a strong fit for a modular monolith with separate packages per bounded context and explicit ports between them. 

The bounded contexts I would split out are these.

`fact_store`: canonical facts, frontmatter schema, git-backed persistence, fact/group inheritance, and query interfaces.

`template_catalog`: channels, templates, section trees, topic-tag mappings, empty-section behavior, template coherence rules.

`change_workflow`: request intake, fact discovery, drafting, tag recommendation, bundle assembly, bundle revision, coherence loop.

`publication`: channel transform, human override, deterministic render, chatbot KB preparation.

`approval`: approval-scope resolution, routing, approver decisions, audit record creation, bundle state transitions.

`engagement`: audience targeting, acknowledgment/feedback tracking, reminders, completion metrics.

`onboarding`: document ingestion, heading extraction, decomposition, scope inference, overlap detection, consolidation review.

`observability`: pipeline tracing, LLM call tracing, schema validation results, trace viewer read models.

This maps closely to the entities and flow you already defined, so it is not introducing new concepts; it is just forcing them into code boundaries that an agent can respect.  

Within each bounded context, I would use a ports-and-adapters style. Domain code should know nothing about FastAPI, SQLAlchemy, GCP, GitPython, Vertex AI, or vector stores. It should depend on interfaces such as `FactRepository`, `BundleRepository`, `TemplateRepository`, `LLMClient`, `EmbeddingClient`, `TraceWriter`, `ApprovalNotifier`, and `Renderer`. This is the cleanest way to keep an agent from leaking infrastructure concerns into business rules.

For this project specifically, I would also add an explicit “capability layer” for LLM work instead of letting arbitrary modules call the model directly. In other words: only one package, something like `llm_runtime`, is allowed to talk to models. All 16 D15 call types become typed strategies registered in a `CallRegistry`, each with four artifacts: input schema, prompt template, output schema, evaluator/validator. That directly reflects your “one output type per call” rule and makes it impossible for an agent to create ad hoc prompts in random files. 

The critical pattern here is schema-first typed execution. Every LLM call should be represented by a class or dataclass like:

`AffectedFactIdentificationCall(InputModel, OutputModel, prompt_template_id, validator, retry_policy)`

Then orchestration code invokes only `runner.run(call_type, input_model, context) -> output_model`. That keeps prompt logic, parsing, retries, and tracing in one place and aligns with your requirement that malformed outputs be retried or escalated before consumption.  

On workflow orchestration, I would not encode the change loop as ordinary chained function calls scattered across endpoints. Your flow has retries, human pauses, approval waits, publication scheduling, and per-channel fan-out. That is workflow-engine territory. The most established Python fit on GCP is Temporal. It gives you durable workflow state, resumability, retries, signals for human approval, timers for publication dates, and child workflows for per-channel publication. It also maps unusually well to your change loop and publication subflow. Each epic can be implemented as a workflow and each D15 call can remain an activity wrapped by the typed LLM runtime. 

If you want the lighter alternative, use Google Cloud Workflows only for coarse service-to-service orchestration and keep domain orchestration in Python. I would not recommend that here. You have too many human-in-the-loop pauses and iterative loops. Temporal is materially better for this shape.

For persistence, I would separate three kinds of storage.

Canonical source-of-truth artifacts remain in Git, because that is already a deliberate design decision and it buys you history, rollback, provenance, and legal look-back. Keep that.  

Operational state should not live in Git. Bundle drafts, workflow executions, approval tasks, engagement responses, scheduled jobs, and trace indexes belong in a transactional datastore. On GCP, use Cloud SQL Postgres unless you have a very strong reason not to. It will simplify relational querying for bundle state, approval chains, and review screens.

Search/index state should be separate again. For semantic retrieval over facts and chatbot chunks, use a dedicated vector index rather than overloading Postgres early. On GCP that usually means Vertex AI Vector Search if you want managed scale, or pgvector in Cloud SQL if you want operational simplicity first. Given your current stage, pgvector is enough unless you expect large tenant corpora quickly. Your own epics call for a “simple vector index” first, which supports starting with pgvector. 

The design pattern for synchronization between Git and operational DB should be an outbox/inbox pattern, not implicit “save here and then maybe save there.” When a bundle is committed, emit a durable domain event in Postgres in the same transaction as the state change, then have workers materialize git artifacts, refresh vector indexes, schedule publication, and update trace read models. That avoids double-write inconsistencies.

I would also introduce CQRS-lite, not full CQRS. Writes go through workflow/domain services. Reads for UI should come from denormalized projections optimized for trace views, bundle diffs, approval queues, and publication status. Your trace viewer requirement is already effectively asking for read models. Build explicit projection tables for them rather than querying raw traces ad hoc. 

For GCP deployment, the cleanest split is usually this:

FastAPI API/UI on Cloud Run.

Temporal server on Temporal Cloud if allowed; otherwise self-hosted is possible but adds friction.

Background workers on Cloud Run Jobs or GKE Autopilot if you need long-running worker pools.

Cloud SQL Postgres for operational state and projections.

GCS for uploaded documents, intermediate render artifacts, and optionally trace blobs if you outgrow SQLite/JSON for local traces.

Pub/Sub for integration events where async fan-out is enough.

Secret Manager for model/API credentials and Git deploy keys.

Cloud Tasks for lightweight deferred actions if not handled inside Temporal timers.

Cloud Logging + Cloud Trace + OpenTelemetry collector for platform observability.

Vertex AI for embeddings/model access if you want GCP-native model plumbing.

That gives you managed infrastructure without forcing every domain boundary to become a network hop.

On the Python stack, these are the libraries I would use because they are established and fit the patterns above.

For domain modeling and validation: `pydantic v2`. Use it for fact frontmatter, bundle items, template schemas, LLM input/output contracts, and API DTOs. It is the obvious fit for your schema-first design.

For ORM and DB: `SQLAlchemy 2.x` plus `alembic`. Keep domain models separate from ORM models; do not let ORM classes become business objects.

For Git integration: `GitPython` is acceptable, but for robustness I would prefer invoking `git` CLI via a small adapter if you need exact parity with Git behavior. Keep all git operations behind a `TenantRepo` port.

For markdown/frontmatter: `python-frontmatter`, `markdown-it-py`, and possibly `mdformat` for canonical formatting.

For deterministic rendering: `Jinja2` for HTML assembly, `WeasyPrint` for HTML-to-PDF if CSS fidelity matters and system dependencies are acceptable. If you need fewer native dependencies, `wkhtmltopdf` wrappers are possible, but I would prefer WeasyPrint for Python integration.

For workflow orchestration: `temporalio`.

For state machines: `python-statemachine` or `transitions`. Bundle lifecycle and approval lifecycle should be explicit finite-state machines, not ad hoc enums with if-statements. Your bundles already have defined states. Encode transitions formally. 

For eventing and message contracts: plain dataclasses or Pydantic models plus Pub/Sub adapters. You do not need a heavy event-sourcing framework.

For LLM guardrails and structured output: plain Pydantic validation first. If you want an established helper layer, `instructor` is a practical choice for schema-constrained structured output. If you are on Vertex/OpenAI models that support strong JSON modes, use those under your own wrapper and keep the dependency surface small. The important thing is that validation remains your contract boundary, exactly as in Epic 0. 

For prompt templating: Jinja2 is sufficient. Do not add a separate prompt framework unless it earns its keep. A versioned prompt registry plus Jinja2 templates is more stable for agentic coding than a sprawling orchestration library.

For LLM observability: `opentelemetry` plus your own `LLMCallRecord` persistence should be the core. If you want a dedicated LLM observability product/library, `Langfuse` is the best fit because it can coexist with your custom trace model instead of replacing it. I would not let Langfuse become the source of truth; your internal `LLMCallRecord` remains canonical because your viewer and downstream debugging depend on it. 

For retries/circuit breaking: `tenacity` for retriable operations around model calls, git operations, and transient external APIs.

For diffing: `deepdiff` for JSON/state diffs and standard unified diffs for markdown. Your trace viewer explicitly needs before/after state diffs. 

For document extraction in onboarding: `pymupdf` for PDFs, `python-docx` for DOCX, and only add OCR if you later encounter image-only scans. Your onboarding pipeline already isolates extraction from decomposition, so keep extraction deterministic and LLM-free where possible. 

For vector search: `pgvector` if starting in Postgres, or Vertex AI SDK if moving to managed vector search later.

For testing: `pytest`, `pytest-asyncio`, `hypothesis`, `respx` or `httpx.MockTransport`, `factory-boy`, and `approvaltests` or snapshot testing for prompt/render regression. For this project, snapshot tests are especially valuable for prompt templates, schema outputs, HTML render outputs, and trace JSON.

For architecture enforcement: `import-linter`. This is worth calling out. Since your priority is strict separation and lower token drift, define import contracts so `domain` cannot import `infrastructure`, `api` cannot import workflow internals directly, and only the composition root wires dependencies. This is one of the most effective anti-drift tools for agent-generated code.

For static quality: `ruff`, `mypy`, `pytest`, `pre-commit`. Keep the rules strict.

The most important concrete design patterns I would apply are these.

First, a composition root. One place only, probably `app/bootstrap.py`, where all adapters are wired. No hidden singleton clients inside feature modules.

Second, command handlers for all write use cases. `SubmitChangeRequest`, `ReviewBundle`, `ApproveBundle`, `PublishBundle`, `IngestDocument`, `FillStub`, `AnswerQuestion`. Each command has one handler. This keeps endpoint code thin and agent-friendly.

Third, explicit domain services for invariants that cross entities. `CoherenceService`, `ApprovalScopeResolver`, `PublicationPlanner`, `GroupInheritanceResolver`. Do not bury these in repositories or workflows. Your coherence gate especially deserves to be a first-class service because it is a hard constraint in the system, not a UI concern. 

Fourth, a policy/strategy registry for call types and channel types. Publication differs between taxonomy-driven channels, changelog channels, and chatbot KB. That is a textbook strategy pattern. `ChannelPublisher` should dispatch to `TaxonomyPublisher`, `ChangelogPublisher`, or `ChatbotPublisher`, not a giant if/else chain. Your design explicitly identifies two assembly models plus the chatbot divergence. Encode that directly. 

Fifth, anti-corruption layers around third-party systems. Model providers, embeddings, email/notification providers, and Git should all be wrapped. This is especially important for agentic coding because otherwise generated code starts reaching through abstractions and coupling to SDK specifics.

Sixth, immutable trace records and append-only operational audit logs. You already want synchronous trace writing before downstream consumption. Keep those records immutable and keyed by workflow run and step. That will make debugging far more reliable. 

A codebase layout that fits this well would look like:

`app/api` for FastAPI routes and request/response DTO mapping.

`app/application` for command/query handlers.

`app/domain` for entities, value objects, domain services, repository interfaces, policies.

`app/workflows` for Temporal workflows and activities orchestration.

`app/llm_runtime` for call registry, prompt registry, parsers, validators, retry policies, trace hooks.

`app/infrastructure` for Postgres, Git, GCP, model SDKs, notifications, renderers, vector store, extraction adapters.

`app/readmodels` for projections and query services backing UI.

`app/ui` for server-rendered Jinja pages or a thin frontend.

`tests/unit`, `tests/integration`, `tests/contracts`, `tests/snapshots`.

That structure is not fashionable; it is useful. It creates stable module targets for a coding agent and suppresses gratuitous invention.

Two design choices I would change slightly.

I would not keep the trace store as JSON files or SQLite beyond local dev. For development, yes. For shared environments, store canonical traces in Postgres or GCS-backed blobs with indexed metadata in Postgres. Your viewer needs timeline trees, call drill-down, validation history, and input/output diffs. That will get painful fast if traces stay purely file-based. Epic 0 can start locally, but the production shape should diverge. 

I would also separate “canonical domain events” from “workflow step traces.” They are related but not the same. A trace says what happened inside execution. A domain event says a business fact occurred: `BundleSubmitted`, `BundleApproved`, `PublicationScheduled`, `RenditionOverridden`. Keeping both prevents you from abusing traces as application state.

For testing strategy, I would use four layers.

Pure unit tests for domain services and state machines.

Contract tests for every D15 call type: fixed input fixture, expected output schema, expected retry/escalation behavior on malformed responses.

Golden snapshot tests for prompt rendering, HTML rendering, and trace-view payloads.

Workflow tests for Temporal processes using mocked activities, especially around the coherence loop, approval waits, and per-channel publication fan-out. Your own UAT definitions already imply this separation.  

If I compress this to a concrete recommendation set, it is this.

Use a modular monolith with bounded contexts.

Use ports-and-adapters plus a single composition root.

Make all write paths command handlers.

Make all long-running flows Temporal workflows.

Make all 16 LLM calls typed, schema-first strategy objects in one `llm_runtime` module.

Keep Git as canonical corpus storage, but use Postgres for operational state and read models.

Use explicit finite-state machines for bundle and approval lifecycle.

Use strategy objects for channel-specific publication.

Use outbox/inbox for async propagation to indexing, notifications, and projections.

Enforce boundaries with `import-linter`, `mypy`, and strict CI.

That would make the system more robust, more modular, and harder for a coding agent to “invent” around established patterns, while staying faithful to the design you already wrote. 

