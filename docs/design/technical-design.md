# FactSquid — Technical Design

**This document is an agent coding specification.** Every section is a constraint, not a suggestion. An AI coding agent implementing any epic must read this document before writing a single line of code and must not deviate from the patterns defined here without explicit human instruction.

---

## Invariants — Never Violate These

1. **LLM calls only through `llm_runtime`.** No module other than `app/llm_runtime/` may instantiate a model client, build a prompt string, or call a model API. No exceptions.
2. **Domain knows nothing about infrastructure.** `app/domain/` imports nothing from `app/infrastructure/`, `app/workflows/`, `app/api/`, or any third-party SDK. It depends only on interfaces it defines itself.
3. **All writes are command handlers.** Every state-changing operation is a named command in `app/application/commands/`. Endpoints call handlers; handlers call domain services; domain services call repository interfaces.
4. **Schema validation before downstream consumption.** Every LLM call output is validated against its output schema before the result is passed to the next step. Validation failure triggers retry or escalation — never silent pass-through.
5. **Git is the corpus. Postgres is operational state.** Facts, templates, config, and D4 artifact records live in git. Bundle state, approval tasks, engagement responses, workflow state, and traces live in Postgres (SQLite locally).
6. **No ad hoc prompts.** Prompt strings are `.j2` files in `prompts/`. They are rendered by `llm_runtime` only. A coding agent must not construct prompt strings inline anywhere else.
7. **Import-linter enforces module boundaries.** The `.importlinter` contract file is authoritative. CI fails on violations.

---

## Project Layout

```
factsquid/
├── app/
│   ├── api/                    # FastAPI routes and request/response DTOs
│   │   ├── v1/
│   │   │   ├── change_workflow.py
│   │   │   ├── publication.py
│   │   │   ├── onboarding.py
│   │   │   ├── approval.py
│   │   │   ├── engagement.py
│   │   │   └── consumer.py
│   │   └── deps.py             # FastAPI Depends wiring
│   │
│   ├── application/            # Use case layer
│   │   ├── commands/           # One file per command, one handler per file
│   │   │   ├── submit_change_request.py
│   │   │   ├── review_bundle.py
│   │   │   ├── approve_bundle.py
│   │   │   ├── publish_bundle.py
│   │   │   ├── ingest_document.py
│   │   │   ├── fill_stub.py
│   │   │   └── answer_question.py
│   │   └── queries/            # Read-only use cases backed by readmodels
│   │       ├── get_trace.py
│   │       ├── get_bundle.py
│   │       └── get_approval_queue.py
│   │
│   ├── domain/                 # Business logic core — no infrastructure imports
│   │   ├── fact/
│   │   │   ├── models.py       # Fact, FactStatus, FactGroup value objects
│   │   │   └── repository.py   # FactRepository interface (ABC)
│   │   ├── bundle/
│   │   │   ├── models.py       # ChangeBundle, BundleItem, BundleState FSM
│   │   │   └── repository.py   # BundleRepository interface
│   │   ├── template/
│   │   │   ├── models.py       # ChannelTemplate, SectionNode, TopicMapping
│   │   │   └── repository.py   # TemplateRepository interface
│   │   ├── approval/
│   │   │   ├── models.py       # ApprovalTask, ApprovalRule, ApprovalAuditRecord
│   │   │   └── repository.py   # ApprovalRepository interface
│   │   ├── engagement/
│   │   │   ├── models.py       # EngagementRequest, EngagementResponse
│   │   │   └── repository.py   # EngagementRepository interface
│   │   ├── tenant/
│   │   │   └── models.py       # TenantConfig, GroupRegistry, AudienceRole
│   │   └── services/           # Domain services for cross-entity invariants
│   │       ├── coherence_service.py        # Hard coherence constraint enforcement
│   │       ├── approval_scope_resolver.py  # Most-restrictive rule across bundle items
│   │       ├── group_inheritance_resolver.py
│   │       └── publication_planner.py      # Stub blocking, publication ordering
│   │
│   ├── llm_runtime/            # ONLY module that talks to models
│   │   ├── call_registry.py    # Maps D15CallType → CallStrategy instances
│   │   ├── runner.py           # LLMRunner.run(call_type, input, context) → output
│   │   ├── calls/              # One file per D15 call type
│   │   │   ├── affected_fact_identification.py
│   │   │   ├── fact_content_drafting.py
│   │   │   ├── topic_tag_recommendation.py
│   │   │   ├── template_change_identification.py
│   │   │   ├── coherence_resolution.py
│   │   │   ├── bundle_revision.py
│   │   │   ├── stub_metadata_generation.py
│   │   │   ├── heading_hierarchy_extraction.py
│   │   │   ├── topic_tag_inference.py
│   │   │   ├── fact_decomposition.py
│   │   │   ├── scope_inference.py
│   │   │   ├── overlap_detection.py
│   │   │   ├── consolidation_drafting.py
│   │   │   ├── channel_transform.py
│   │   │   ├── newsletter_narrative_assembly.py
│   │   │   └── qa_answer_generation.py
│   │   ├── providers/          # Anti-corruption layer per model provider
│   │   │   ├── base.py         # LLMProvider ABC
│   │   │   ├── anthropic.py
│   │   │   └── vertexai.py
│   │   ├── prompt_registry.py  # Loads and renders .j2 templates from prompts/
│   │   └── tracer.py           # Writes LLMCallRecord; called by runner only
│   │
│   ├── workflows/              # Temporal workflows and activities
│   │   ├── change_workflow.py
│   │   ├── publication_workflow.py
│   │   ├── onboarding_workflow.py
│   │   ├── approval_workflow.py
│   │   └── activities/         # Each activity wraps one or more llm_runtime calls
│   │       ├── fact_discovery.py
│   │       ├── bundle_assembly.py
│   │       ├── coherence_gate.py
│   │       ├── channel_transform.py
│   │       ├── document_extraction.py
│   │       └── kb_indexing.py
│   │
│   ├── infrastructure/         # All third-party and cloud adapters
│   │   ├── git/
│   │   │   └── tenant_repo.py  # TenantRepo — implements FactRepository et al. via git
│   │   ├── db/
│   │   │   ├── models.py       # SQLAlchemy ORM models (separate from domain models)
│   │   │   ├── migrations/     # Alembic migration scripts
│   │   │   ├── bundle_repo.py
│   │   │   ├── approval_repo.py
│   │   │   └── engagement_repo.py
│   │   ├── trace/
│   │   │   ├── base.py         # TraceStore ABC
│   │   │   ├── sqlite_store.py # Local dev
│   │   │   └── postgres_store.py
│   │   ├── vector/
│   │   │   └── pgvector_store.py  # Fact embedding index via pgvector
│   │   ├── render/
│   │   │   ├── html_renderer.py   # markdown → HTML via Jinja2 + CSS
│   │   │   └── pdf_renderer.py    # HTML → PDF via WeasyPrint
│   │   ├── extraction/
│   │   │   ├── pdf_extractor.py   # pymupdf
│   │   │   └── docx_extractor.py  # python-docx
│   │   ├── notifications/
│   │   │   └── email_notifier.py
│   │   └── gcs/
│   │       └── blob_store.py      # Uploaded docs, render artifacts
│   │
│   ├── readmodels/             # Denormalized projections for UI read paths
│   │   ├── trace_view.py       # Pipeline timeline + LLM call drill-down payloads
│   │   ├── bundle_diff.py      # Before/after state diffs for review UI
│   │   └── approval_queue.py
│   │
│   ├── ui/                     # Server-rendered Jinja2 templates
│   │   ├── templates/
│   │   └── static/
│   │
│   └── bootstrap.py            # Composition root — single place all adapters are wired
│
├── prompts/                    # Versioned Jinja2 prompt templates (.j2)
│   ├── affected_fact_identification.j2
│   ├── fact_content_drafting.j2
│   └── ...                     # one per D15 call type
│
├── schemas/
│   ├── llm-calls/              # JSON Schema for every D15 call output
│   │   ├── affected_fact_identification.json
│   │   └── ...
│   └── facts/
│       └── frontmatter.json    # Canonical fact frontmatter schema
│
└── tests/
    ├── unit/                   # Pure domain logic, no I/O
    ├── integration/            # Real DB, real git; mocked LLM
    ├── contracts/              # One test per D15 call: fixed input → schema validation
    └── snapshots/              # Golden outputs: prompts, HTML renders, trace payloads
```

---

## Module Dependency Rules

Enforced via `import-linter`. The `.importlinter` file defines these contracts:

```
app.domain        → (nothing outside app.domain)
app.application   → app.domain
app.llm_runtime   → app.domain, app.infrastructure.trace (TraceStore only)
app.workflows     → app.application, app.llm_runtime
app.api           → app.application, app.readmodels
app.infrastructure → app.domain (interfaces only)
app.readmodels    → app.infrastructure.db
app.bootstrap     → everything (composition root only)
```

**Violations are CI-blocking.** A coding agent must not add imports that violate these contracts. If a new dependency seems necessary, the constraint must be explicitly reviewed and updated in this document first.

---

## Bounded Contexts

Eight bounded contexts, each owns its domain models, its repository interface, and its application commands. They communicate through explicit interfaces — never by importing each other's internals.

| Context | Domain models | Repository interface |
|---|---|---|
| `fact_store` | `Fact`, `FactStatus`, `FactGroup` | `FactRepository` |
| `template_catalog` | `ChannelTemplate`, `SectionNode`, `TopicMapping` | `TemplateRepository` |
| `change_workflow` | `ChangeBundle`, `BundleItem`, `BundleState` | `BundleRepository` |
| `publication` | `Rendition`, `RenditionOverride`, `PublicationJob` | `RenditionRepository` |
| `approval` | `ApprovalTask`, `ApprovalRule`, `ApprovalAuditRecord` | `ApprovalRepository` |
| `engagement` | `EngagementRequest`, `EngagementResponse` | `EngagementRepository` |
| `onboarding` | `IngestionJob`, `ExtractedSection`, `ConsolidationProposal` | `IngestionRepository` |
| `observability` | `LLMCallRecord`, `PipelineStepRecord`, `PipelineRun` | `TraceStore` |

---

## LLM Runtime

### Principle
Only `app/llm_runtime/` may call models. All 16 D15 call types are registered strategies. The runner is the single entry point.

### CallStrategy
Every D15 call type is a class with four required attributes:

```python
@dataclass
class CallStrategy:
    call_type: D15CallType          # closed enum from D15 taxonomy
    input_schema: type[BaseModel]   # Pydantic v2 model
    output_schema: type[BaseModel]  # Pydantic v2 model
    prompt_template_id: str         # filename in prompts/ without .j2
    retry_policy: RetryPolicy       # max_attempts, backoff
```

### LLMRunner
```python
class LLMRunner:
    def run(
        self,
        call_type: D15CallType,
        input_model: BaseModel,
        context: RunContext,   # pipeline_run_id, step_name, tenant_id
    ) -> BaseModel:
        ...
```

Execution sequence (enforced, not optional):
1. Load strategy from `CallRegistry`
2. Render prompt via `PromptRegistry.render(template_id, input_model)`
3. Call provider adapter — `LLMProvider.complete(prompt) -> raw_str`
4. Parse raw response → attempt `output_schema.model_validate_json(raw_str)`
5. On validation failure: retry up to `retry_policy.max_attempts`; on exhaustion: raise `LLMCallEscalationError`
6. Write `LLMCallRecord` to `TraceStore` **synchronously before returning**
7. Return validated output model

### D15CallType Enum
```python
class D15CallType(str, Enum):
    AFFECTED_FACT_IDENTIFICATION = "affected_fact_identification"
    FACT_CONTENT_DRAFTING = "fact_content_drafting"
    TOPIC_TAG_RECOMMENDATION = "topic_tag_recommendation"
    TEMPLATE_CHANGE_IDENTIFICATION = "template_change_identification"
    COHERENCE_RESOLUTION = "coherence_resolution"
    BUNDLE_REVISION = "bundle_revision"
    STUB_METADATA_GENERATION = "stub_metadata_generation"
    HEADING_HIERARCHY_EXTRACTION = "heading_hierarchy_extraction"
    TOPIC_TAG_INFERENCE = "topic_tag_inference"
    FACT_DECOMPOSITION = "fact_decomposition"
    SCOPE_INFERENCE = "scope_inference"
    OVERLAP_DETECTION = "overlap_detection"
    CONSOLIDATION_DRAFTING = "consolidation_drafting"
    CHANNEL_TRANSFORM = "channel_transform"
    NEWSLETTER_NARRATIVE_ASSEMBLY = "newsletter_narrative_assembly"
    QA_ANSWER_GENERATION = "qa_answer_generation"
```

### Provider Abstraction
```python
class LLMProvider(ABC):
    @abstractmethod
    def complete(self, prompt: str, config: ProviderConfig) -> str: ...
```

Concrete implementations: `AnthropicProvider`, `VertexAIProvider`. Wired at bootstrap. Prompt templates are provider-neutral — they must not contain provider-specific formatting markers.

### Prompt Registry
- Templates live in `prompts/` as `{template_id}.j2`
- Rendered with `jinja2.Environment(undefined=StrictUndefined)` — missing variables are errors, not silently empty
- Template IDs are stable identifiers versioned in git
- No inline prompt construction anywhere else in the codebase

---

## Workflow Orchestration (Temporal)

All long-running operations with human pauses, retries, approval waits, or scheduled timers are Temporal workflows. Plain async Python is used only for request-scoped operations with no human interruption points.

### Workflow topology

**`ChangeWorkflow`** (D8 change loop)
```
Signal: SubmitRequest(request_text, requester_id, tenant_id)
  → Activity: FactDiscoveryActivity        # calls D15 #1
  → Activity: BundleAssemblyActivity       # calls D15 #2, #3, #4
  → Activity: CoherenceGateActivity        # calls D15 #5 (loops until clean)
Signal: HumanReviewSignal(edits)
  → Activity: BundleRevisionActivity       # calls D15 #6 if feedback
Signal: HumanConfirmSignal
  → Child: ApprovalWorkflow
  → Activity: SchedulePublicationActivity
```

**`ApprovalWorkflow`**
```
Activity: RouteToApprovers
Timer: reminder cadence
Signal: ApproverDecisionSignal(approved/rejected, approver_id)
  → Activity: WriteApprovalAuditRecord     # D4 artifact committed to git
```

**`PublicationWorkflow`** (per fact, per channel fan-out)
```
Timer: wait until publication_date
Activity: StubBlockingCheck                # refuses if unresolved stubs
For each channel in channel_scope:
  → Activity: ChannelTransformActivity     # calls D15 #14 or #15
  → Signal: HumanOverrideWindowSignal (optional, timeout-gated)
  → Activity: DeterministicRenderActivity  # markdown → HTML/PDF
  → Activity: DeliverToChannelActivity
  → Activity: UpdateChatbotKBActivity      # if channel is chatbot-kb
```

**`OnboardingWorkflow`**
```
Activity: DocumentExtractionActivity      # pymupdf / python-docx, no LLM
Activity: HeadingHierarchyActivity        # D15 #8
Activity: TopicTagInferenceActivity       # D15 #9
Activity: FactDecompositionActivity       # D15 #10
Activity: ScopeInferenceActivity          # D15 #11
Signal: HumanReviewSignal
Activity: BatchCommitActivity             # writes facts to git
```

### Activities wrap application commands
Temporal activities are thin wrappers. They call `app/application/commands/` handlers — not domain services directly. This keeps domain logic testable outside Temporal.

---

## Persistence Design

### Three storage layers

**Layer 1 — Git (corpus)**
Owned by `TenantRepo` in `app/infrastructure/git/`. Contains:
- `tenants/{tenant-id}/facts/*.md` — one file per fact with YAML frontmatter (D3 schema)
- `tenants/{tenant-id}/config/` — channels, templates, approval rules, audience roles, groups
- `tenants/{tenant-id}/artifacts/provenance/` — bundle provenance records (D4)
- `tenants/{tenant-id}/artifacts/approvals/` — approval audit records (D4)
- `tenants/{tenant-id}/artifacts/overrides/` — rendition override diffs (D4)

All git operations go through `TenantRepo`. No other module may use `git` CLI or GitPython directly.

**Layer 2 — Postgres (operational state)**
Cloud SQL Postgres in production. Contains:
- Bundle state and `BundleItem` records
- Approval tasks and approver decisions
- Engagement requests and responses
- Workflow execution references (Temporal run IDs)
- Trace records (`LLMCallRecord`, `PipelineStepRecord`) — production only
- Denormalized read model projections (trace view, approval queue, bundle diff)
- pgvector extension: fact embedding index for semantic retrieval

SQLAlchemy 2.x ORM. ORM models (`app/infrastructure/db/models.py`) are **separate classes** from domain models. Mapping between them is explicit — no domain model may inherit from a SQLAlchemy base.

**Layer 3 — SQLite (local dev traces)**
`TraceStore` is an ABC with two implementations:
- `SqliteTraceStore` — used when `ENV=development`; single file, zero setup, sufficient for Epic 0 UAT
- `PostgresTraceStore` — used when `ENV=production`

Wired at bootstrap via environment variable. The rest of the system calls `TraceStore` — it never knows which implementation is active.

### Outbox pattern for async propagation
When a bundle is committed to git, a domain event (`BundleCommitted`) is written to a Postgres outbox table **in the same transaction** as the bundle state update. Workers consume the outbox to:
- Refresh the vector index
- Schedule publication timers in Temporal
- Update read model projections
- Trigger engagement notifications

No double-write between git and Postgres. The git write is authoritative; Postgres state is derived from domain events.

---

## Key Patterns

### Command handlers
Every state-changing use case is a command with a single handler:

```
SubmitChangeRequestCommand → SubmitChangeRequestHandler
ReviewBundleCommand        → ReviewBundleHandler
ApproveBundleCommand       → ApproveBundleHandler
PublishBundleCommand       → PublishBundleHandler
IngestDocumentCommand      → IngestDocumentHandler
FillStubCommand            → FillStubHandler
AnswerQuestionCommand      → AnswerQuestionHandler
```

Handlers are called by:
1. FastAPI endpoints (via `app/api/deps.py`)
2. Temporal activities (as thin wrappers)

Handlers never call each other. They call domain services and repository interfaces.

### Bundle state machine
`BundleState` is an explicit FSM using `python-statemachine`. No `if bundle.state == "X"` conditionals scattered across the codebase. All valid transitions are declared in one place:

```
draft → pending_approval  (trigger: submit_for_approval)
draft → approved          (trigger: self_service_approve, guard: approval_scope == self-service)
pending_approval → approved  (trigger: approval_received)
pending_approval → draft     (trigger: approval_rejected)
approved → scheduled         (trigger: schedule_publication)
scheduled → published        (trigger: publication_complete)
```

Illegal transitions raise `InvalidTransitionError`. The FSM is a value object on `ChangeBundle` — it has no infrastructure dependencies.

### Channel publication strategy
`PublicationEngine` dispatches to a strategy based on channel type:

```python
class ChannelPublisher(Protocol):
    def publish(self, fact: Fact, channel: ChannelTemplate, context: ...) -> Rendition: ...

class TaxonomyPublisher:    # D5 taxonomy-driven channels
class ChangelogPublisher:   # D5 changelog (newsletter)
class ChatbotKBPublisher:   # D6 chatbot KB — diverges at chunking/embedding
```

`ChannelPublisherRegistry` maps `channel.type → publisher`. No if/else chains. New channel types are new strategy implementations, not branches in existing code.

### Coherence service
`CoherenceService` is a first-class domain service. It is not a validator, a lint, or a UI concern. It enforces D7:
- Every fact must have at least one matching template section
- Every non-optional template section must have at least one matching fact

When a bundle would violate coherence, `CoherenceService.check(bundle, template) -> list[CoherenceViolation]` returns violations. Each violation is passed to `LLMRunner.run(COHERENCE_RESOLUTION, ...)` which returns a specific resolution. The bundle is extended with the resolution and re-checked. This loops until clean (D15 call #5 behavior).

`CoherenceService` depends only on `FactRepository` and `TemplateRepository` interfaces — no infrastructure.

### Domain services (complete list)
```
CoherenceService          — coherence invariant enforcement
ApprovalScopeResolver     — most-restrictive rule across bundle items
GroupInheritanceResolver  — fact inherits from group registry, per-fact overrides flagged
PublicationPlanner        — stub blocking check, publication ordering
```

---

## Library Manifest

This is the authoritative list. A coding agent must not add libraries outside this list without explicit instruction. Each entry states what it is used for.

| Library | Version constraint | Used for |
|---|---|---|
| `fastapi` | `>=0.115` | API delivery layer |
| `pydantic` | `v2` | All schemas: fact frontmatter, bundle items, LLM I/O contracts, API DTOs |
| `sqlalchemy` | `>=2.0` | ORM for operational state (separate from domain models) |
| `alembic` | latest | DB migrations |
| `temporalio` | latest | Workflow orchestration |
| `python-statemachine` | latest | Bundle and approval lifecycle FSMs |
| `gitpython` | latest | Git operations in `TenantRepo` (adapter only) |
| `python-frontmatter` | latest | Fact markdown + YAML frontmatter parsing |
| `markdown-it-py` | latest | Markdown processing |
| `jinja2` | latest | Prompt templates (`StrictUndefined`) and HTML rendering |
| `weasyprint` | latest | HTML → PDF rendering |
| `tenacity` | latest | Retries on LLM calls, git ops, transient external APIs |
| `pgvector` | latest | Semantic search over fact embeddings (via psycopg2/asyncpg) |
| `pymupdf` | latest | PDF text extraction in onboarding |
| `python-docx` | latest | DOCX text extraction in onboarding |
| `deepdiff` | latest | State diffs in trace viewer (before/after bundle/fact state) |
| `anthropic` | latest | AnthropicProvider adapter (behind LLMProvider ABC) |
| `google-cloud-aiplatform` | latest | VertexAIProvider adapter (behind LLMProvider ABC) |
| `google-cloud-storage` | latest | GCS blob store for uploads and render artifacts |
| `opentelemetry-sdk` | latest | Platform observability (Cloud Trace integration) |
| `structlog` | latest | Structured JSON logging |
| `pytest` | latest | Test runner |
| `pytest-asyncio` | latest | Async test support |
| `hypothesis` | latest | Property-based tests for domain services |
| `approvaltests` | latest | Snapshot/golden tests for prompt renders, HTML renders, trace payloads |
| `respx` | latest | HTTP mocking for provider adapters in tests |
| `factory-boy` | latest | Test fixture factories for domain models |
| `import-linter` | latest | Architecture boundary enforcement |
| `ruff` | latest | Linting and formatting |
| `mypy` | latest | Static type checking |
| `pre-commit` | latest | Hook runner (ruff, mypy, import-linter) |

**Not in scope (do not add):**
- LangChain, LlamaIndex, or any LLM orchestration framework — `llm_runtime` replaces these
- Any agentic framework (LangGraph, AutoGen, etc.) — workflows are Temporal
- Separate prompt management services — `PromptRegistry` + git is sufficient
- `instructor` — plain Pydantic v2 validation is used; add only if structured output reliability proves insufficient and only in `llm_runtime`

---

## Testing Strategy

Four layers, run in order. All layers are required; none is optional.

### Layer 1 — Unit tests (`tests/unit/`)
- Pure domain logic only: domain services, FSMs, value objects, `CoherenceService`, `ApprovalScopeResolver`, `GroupInheritanceResolver`
- No I/O, no database, no LLM calls
- `hypothesis` for property-based tests on `CoherenceService` and FSM transition rules
- **Coverage target: 100% of `app/domain/`**

### Layer 2 — Contract tests (`tests/contracts/`)
One test file per D15 call type. Each test:
1. Loads a fixed input fixture (from `tests/contracts/fixtures/`)
2. Calls the call strategy's validator directly with a synthetic "valid" response
3. Calls the validator with a "malformed" response (missing required field, wrong type)
4. Asserts the valid case passes schema validation
5. Asserts the malformed case raises a `ValidationError` before being returned
6. Asserts `LLMCallRecord` is written with the correct `call_type` and `validation_result`

These tests never call a real model. They validate that the contract between `llm_runtime` and downstream consumers is correctly enforced.

### Layer 3 — Integration tests (`tests/integration/`)
- Real SQLite/Postgres (via Docker Compose in CI), real git repo (temp dir), mocked LLM provider
- Tests command handlers end-to-end through domain services to infrastructure adapters
- `respx` to mock provider HTTP calls; returns fixture responses
- `factory-boy` for domain object construction
- Key flows to cover: submit change request → bundle assembled, approve bundle → audit record written to git, coherence violation → resolution proposed and applied

### Layer 4 — Snapshot tests (`tests/snapshots/`)
- Golden output tests using `approvaltests`
- Prompt template rendering: given a fixed input model, assert the rendered prompt matches the approved snapshot
- HTML renderer output: given a fixed fact + template, assert the HTML output matches the approved snapshot
- Trace view payloads: given a fixed pipeline run, assert the JSON payload served to the trace viewer matches the approved snapshot
- Snapshots are committed to git. CI fails on divergence. Intentional changes require `approvaltests` approval file update.

---

## Infrastructure (GCP)

| Service | Role |
|---|---|
| **Cloud Run** | FastAPI API + UI server; Temporal worker containers |
| **Cloud SQL (Postgres)** | Operational state, read model projections, trace store (prod), pgvector index |
| **Cloud Storage (GCS)** | Uploaded documents (onboarding), intermediate render artifacts, trace blobs if overflowing DB |
| **Temporal Cloud** | Workflow orchestration server (preferred over self-hosted) |
| **Secret Manager** | Model API keys, git deploy keys, DB credentials |
| **Cloud Pub/Sub** | Outbox event fan-out to workers |
| **Cloud Logging + Cloud Trace** | Platform observability via OpenTelemetry collector |
| **Artifact Registry** | Container images |
| **Cloud Build** | CI/CD pipeline |

Tenant git repos are hosted on GitHub or equivalent, accessed via deploy keys stored in Secret Manager. The `TenantRepo` adapter holds the clone locally for the duration of a workflow execution and pushes on commit.

---

## Observability

### LLMCallRecord (written synchronously by `llm_runtime/tracer.py`)
```python
class LLMCallRecord(BaseModel):
    id: UUID
    call_type: D15CallType
    pipeline_run_id: UUID
    step_name: str
    timestamp: datetime
    prompt_template_id: str
    prompt_variables: dict           # variables injected into template
    prompt_rendered: str             # actual prompt sent
    raw_response: str                # raw model output before parsing
    parsed_output: dict | None       # structured output after schema parse
    validation_result: Literal["pass", "fail"]
    validation_errors: list[str]
    latency_ms: int
    token_counts: TokenCounts        # prompt + completion
```

### PipelineStepRecord
```python
class PipelineStepRecord(BaseModel):
    id: UUID
    pipeline_run_id: UUID
    parent_step_id: UUID | None
    step_name: str
    started_at: datetime
    completed_at: datetime
    status: Literal["running", "completed", "failed"]
    inputs: dict                     # named input snapshot
    outputs: dict                    # named output snapshot
    llm_call_ids: list[UUID]
    error: str | None
```

### Trace viewer (Epic 0 deliverable)
A local web UI served by FastAPI. Three views:
1. **Pipeline timeline** — collapsible step tree with duration, status, LLM call count
2. **LLM call drill-down** — per call: Prompt tab (variables highlighted), Response tab (raw), Parsed tab (JSON), Validation tab (schema + pass/fail)
3. **State diff view** — inputs/outputs of any step shown as JSON diff (`deepdiff`)

The viewer is read-only. It queries `TraceStore` via `readmodels/trace_view.py`. It never drives the pipeline.

---

## Per-Epic Technical Notes

### Epic 0 — Architecture & Observability Foundation
- Deliverables: project structure, fact schema, `LLMCallRecord`/`PipelineStepRecord` models and schemas, `TraceStore` ABC + `SqliteTraceStore`, `LLMRunner` skeleton with all 16 call type stubs, all 16 output JSON schemas in `schemas/llm-calls/`, trace viewer UI
- `LLMRunner` in this epic uses a mock provider that returns fixture responses — no real model calls
- Import-linter, ruff, mypy, pre-commit all configured and passing before this epic closes

### Epic 1 — Single Fact → Single Channel Publication
- First real LLM call: D15 #14 (`channel_transform`) via `LLMRunner`
- `TenantRepo` read path (fact loading from git) implemented
- `TaxonomyPublisher` strategy implemented
- `HtmlRenderer` and `PdfRenderer` implemented
- Publication runner is a simple Temporal workflow (no human pause signals yet)
- Trace viewer wired to a real pipeline execution

### Epic 2 — Change Workflow: Request → Bundle → Commit
- D15 calls #1, #2, #3 implemented with real prompts
- `ChangeWorkflow` Temporal workflow implemented with `HumanReviewSignal` and `HumanConfirmSignal`
- Bundle review UI: diff view + LLM call trace per proposed change
- `TenantRepo` write path (fact commit + bundle provenance record)
- pgvector fact embedding index initialized; `FactDiscoveryActivity` uses it for call #1 context
- Approval scope: all bundles are `self-service` (no `ApprovalWorkflow` yet)

### Epic 3 — Onboarding: Document → Facts
- `OnboardingWorkflow` Temporal workflow
- `DocumentExtractionActivity` (deterministic, no LLM)
- D15 calls #8, #9, #10, #11 implemented with real prompts
- Onboarding review UI: proposed section tree + extracted facts + flagged fields
- `BatchCommitActivity` writes initial corpus to git

### Epic 4 — Coherence Gate + Auto-Resolution
- `CoherenceService` domain service fully implemented
- D15 calls #4, #5 implemented
- Coherence loop in `CoherenceGateActivity` (calls #5 until clean, bounded by max iterations)
- Bundle review UI extended with coherence violation + resolution display

### Epic 5 — Multi-Channel Publication
- Multiple `ChannelPublisher` strategies registered
- Human override window: `HumanOverrideWindowSignal` in `PublicationWorkflow` (timeout-gated)
- Override diff committed to git artifacts (D4)
- Multi-channel rendition viewer in UI

### Epic 6 — Approval Routing
- `ApprovalWorkflow` implemented
- `ApprovalScopeResolver` domain service
- `ApprovalRepository` and Postgres implementation
- `ApprovalAuditRecord` written to git artifacts (D4)
- Bundle state machine transitions for `pending_approval → approved/draft`
- Approver notification via `EmailNotifier`

### Epic 7 — Consumer Q&A
- Chatbot KB publication pipeline: `ChatbotKBPublisher` strategy (chunking + embedding)
- D15 call #16 implemented
- Consumer chat UI (tenant + audience-role scoped)
- Answer trace: retrieved facts, relevance scores, full LLM call trace

### Epic 8 — Event Groups
- `GroupRegistry` in tenant config
- `GroupInheritanceResolver` domain service
- D15 call #7 implemented (stub metadata generation)
- Stub blocking in `PublicationPlanner`
- Stub publication blocking check in `PublicationWorkflow`

### Epic 9 — Engagement Engine
- `EngagementRequest` and `EngagementResponse` domain models
- Engagement configuration on `ChangeBundle` at review time
- Post-publication notification trigger in `PublicationWorkflow`
- Engagement tracking UI: completion rates, non-respondent list, reminder trigger

### Epic 10 — Onboarding Deduplication
- D15 calls #12, #13 implemented
- Pairwise overlap detection across extracted facts within an onboarding session
- Deduplication review UI: side-by-side pairs + proposed consolidation
- Batch commit handles consolidated facts with merged `audience_scope` + `channel_scope`

---

## Composition Root

`app/bootstrap.py` is the only file that instantiates concrete adapter classes and wires them into the application. It reads configuration from environment variables (via Pydantic Settings). All other modules receive their dependencies via constructor injection.

**Nothing outside `bootstrap.py` may instantiate a concrete adapter class.** A coding agent must not create `AnthropicProvider()`, `SqliteTraceStore()`, or any infrastructure class outside the composition root.

```python
# Sketch — not prescriptive of exact API
def build_container(settings: Settings) -> Container:
    trace_store = SqliteTraceStore(settings.sqlite_path) if settings.env == "development" \
                  else PostgresTraceStore(settings.db_url)
    llm_provider = AnthropicProvider(settings.anthropic_api_key) if settings.llm_provider == "anthropic" \
                   else VertexAIProvider(settings.vertex_project)
    runner = LLMRunner(
        registry=build_call_registry(),
        prompt_registry=PromptRegistry(settings.prompts_dir),
        provider=llm_provider,
        trace_store=trace_store,
    )
    tenant_repo = TenantRepo(settings.git_repos_root)
    bundle_repo = PostgresBundleRepo(settings.db_url)
    # ... wire all repositories, domain services, command handlers
    return Container(runner=runner, tenant_repo=tenant_repo, ...)
```
