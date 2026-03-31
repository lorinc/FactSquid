# Epic 0 — Architecture & Observability Foundation

**What this is:** Set up the structural decisions that all subsequent epics depend on. No application logic yet — but everything real runs through the observability layer.

---

## Deliverables

### Tenant repo structure

Facts and config live in a git repository per tenant:

```
/tenants/{tenant-id}/
  facts/                        # one .md file per fact
  config/
    channels/                   # one .yaml per channel
    templates/                  # one .yaml per channel template
    approval-rules.yaml
    audience-roles.yaml
    groups.yaml
  artifacts/
    provenance/                 # bundle provenance records (D4)
    approvals/                  # approval audit records (D4)
    overrides/                  # rendition override diffs (D4)
```

### Fact schema

Every fact is a markdown file with YAML frontmatter carrying the D3 fields exactly:

```markdown
---
id: fact-uuid
type: policy
topic_tags: [medication, health-safety]
audience_scope: [staff, parents]
channel_scope: [staff-handbook, parent-newsletter, chatbot-kb]
approval_scope: head-of-school
owner: school-nurse
publication_date: 2026-04-01
effective_date: 2026-09-01
expiry_date: 2027-08-31
status: live
group: null
---

Markdown body of the fact goes here.
```

### LLM call tracer

Every LLM call in the system emits a structured `LLMCallRecord`:

```typescript
interface LLMCallRecord {
  id: string                    // uuid
  call_type: D15CallType        // enum matching D15 taxonomy
  pipeline_run_id: string       // which pipeline execution this belongs to
  step_name: string             // human-readable step label
  timestamp: string             // ISO 8601
  prompt_template_id: string    // versioned prompt template identifier
  prompt_variables: object      // variables injected into the template
  prompt_rendered: string       // the actual prompt sent to the model
  raw_response: string          // raw model output, before parsing
  parsed_output: object         // structured output after schema parse
  validation_result: 'pass' | 'fail'
  validation_errors: string[]   // empty on pass
  latency_ms: number
  token_counts: {
    prompt: number
    completion: number
  }
}
```

`D15CallType` is a closed enum of the 16 call types from D15:

```
affected_fact_identification
fact_content_drafting
topic_tag_recommendation
template_change_identification
coherence_resolution
bundle_revision
stub_metadata_generation
heading_hierarchy_extraction
topic_tag_inference
fact_decomposition
scope_inference
overlap_detection
consolidation_drafting
channel_transform
newsletter_narrative_assembly
qa_answer_generation
```

### Pipeline step tracer

A pipeline execution is a named tree of steps. Each step emits a `PipelineStepRecord`:

```typescript
interface PipelineStepRecord {
  id: string                    // uuid
  pipeline_run_id: string
  parent_step_id: string | null // null for root step
  step_name: string
  started_at: string
  completed_at: string
  status: 'running' | 'completed' | 'failed'
  inputs: object                // named input snapshot (fact IDs, bundle state, etc.)
  outputs: object               // named output snapshot
  llm_call_ids: string[]        // IDs of LLMCallRecords triggered by this step
  error: string | null
}
```

Both record types are written to a local append-only trace store (flat JSON files per pipeline run, or SQLite — implementation choice). They must be written synchronously before the next step consumes their output.

### Trace viewer

A local web UI (served during development and UAT sessions) that renders a pipeline execution as an interactive timeline.

**Required views:**

**Pipeline timeline view** — the root step and its children rendered as a collapsible tree, each node showing: step name, duration, status (green/red), number of LLM calls triggered.

**LLM call drill-down** — clicking any step shows the LLM calls it triggered. Each call is a panel with four tabs:
1. **Prompt** — the rendered prompt with injected variables highlighted (diff-style against the raw template)
2. **Response** — raw model output
3. **Parsed** — parsed structured output rendered as formatted JSON
4. **Validation** — pass/fail, validation errors if any, the JSON schema that was applied

**State diff view** — clicking the inputs/outputs of a step shows the before/after state of the bundle or fact being processed (JSON diff).

The viewer is read-only. It does not drive the pipeline — it only observes.

### Structured output schemas

All 16 D15 call types have defined JSON schemas before any prompts are written. Schemas are the contract between the LLM call and the next step. A call that returns a response that fails schema validation is retried (up to a configurable limit) before escalating.

Schema definitions live in `/schemas/llm-calls/` and are referenced by `prompt_template_id` in `LLMCallRecord`.

---

## What is explicitly deferred

- Actual prompt templates (no prompts written in this epic)
- Real LLM API calls (synthetic/mock calls are sufficient for UAT)
- Any application-layer logic (no facts are created or modified)
- Authentication or multi-user concerns

---

## UAT

**Setup:** Developer constructs a synthetic pipeline run with 3–4 steps and 2–3 LLM calls per step. LLM responses are mocked — one valid response, one response with a missing required field (validation failure), one with a field of the wrong type.

**What the developer sees in the trace viewer:**

1. Pipeline timeline shows 3–4 steps in sequence, each with duration and status
2. Expanding a step reveals its LLM calls
3. The valid call shows: full rendered prompt (variables highlighted), raw response, parsed JSON, green validation pass
4. The invalid calls show: red validation fail, the specific schema violation, the raw response that caused it
5. Clicking inputs/outputs on any step shows the state snapshot diff

**Pass criteria:** A developer who has not seen the pipeline code can look at the trace viewer and reconstruct, without guessing, exactly what the system sent to the model, what it received back, and why validation failed on the failing call. No terminal output required — everything is visible in the viewer.
