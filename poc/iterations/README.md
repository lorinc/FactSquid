# Iteration Results

Each subdirectory (e.g. `iter_001/`, `iter_002/`) is one run of `run_iteration.py` against a single test document. It contains the full pipeline output plus a root cause diagnosis for every quality problem found.

## Folder layout in context

- `poc/test_docs/` — **input**: the 4 synthetic policy documents the pipeline reads
- `poc/iterations/` — **per-doc quality runs**: critique + diagnosis output (this folder)
- `poc/output/` — **full corpus run**: `corpus.json` (all facts from all 4 docs) and `proposals.json` (Chain B change proposals)

## Files in each iteration

### `facts.json`
The 4-pass pipeline's final output: all extracted facts for the document.

Each fact has:
- `id` — deterministic: `topic_slug__scope_qualifier__index`
- `title`, `content`, `kind` — the fact itself (`kind` is `rationale`/`principle`/`context` or null)
- `topic_slug`, `scope_qualifier` — grouping key from Pass 1
- `source_spans` — list of `source_path` values (provenance: where in the document each contributing span came from)
- `audience_scope`, `channel_scope` — inferred from the document by Call #11

### `topic_docs.json`
The Pass 3 assembled topic documents, one per `(topic_slug, scope_qualifier)` group.

Each value is a markdown string of concatenated verbatim spans with `### source_path` provenance headers. This is exactly what the Pass 4 LLM received as input for fact extraction.

**Key use:** if a fact is wrong or missing, check the topic document first. If the information is here, the error is in Pass 4 (extraction). If it's not here, the error is in Pass 1 (scanning) or Pass 2 (grouping).

### `critiques.json`
Per-topic quality assessment. For each topic group:
- `overall` — one-sentence verdict
- `problems` — list of specific issues, each with a `problem_type` and `description`

Problem types:
| Type | Meaning |
|---|---|
| `missing-content` | An obligation, permission, exception, or value is absent from the extracted facts |
| `not-standalone` | A fact implies "who", "when", or "except what" without stating it |
| `not-canonical` | Navigation language, passive construction, or redundant preamble |
| `not-template-ready` | Audience- or channel-specific framing baked into the fact content |
| `over-atomized` | One logical unit split into too many facts |
| `under-atomized` | Multiple distinct topics merged into one fact |
| `wrong-tags` | Topic tags inconsistent with the topic_slug or source |
| `other` | Other quality issues |

### `diagnosis.json`
Root cause attribution for every critique problem. For each problem:
- `problem_type`, `description` — copied from the critique
- `root_cause.pass_attribution` — which pass introduced the error: `pass-1`, `pass-3`, or `pass-4`
- `root_cause.component` — the specific file or function (e.g. `fact_extraction.j2`, `topic_scanning.j2`)
- `root_cause.explanation` — what decision went wrong and what evidence in the data shows it
- `root_cause.recommended_fix` — a concrete, actionable change to make

**Reading a diagnosis entry:**
```
pass-4 / fact_extraction.j2
explanation: The LLM transformed 'are expected to dress' into 'are required to,'
             which makes the tone less neutral and less adaptable.
recommended_fix: Modify prompt to favor adaptable language: preserve original modal
                 verbs unless the meaning requires change.
```
This tells you: the topic document had the right text, Pass 4 rewrote it incorrectly, and here is the prompt change that would fix it.

### `problem_summary.json`
Counts of each problem type across all topics. Use this to prioritise which prompt to fix first.

### `traces/`
One JSON file per LLM call, named `{seq}__{call_number}_{call_name}__{slug}.json`.

Each trace contains:
- `prompt` — the full rendered prompt sent to the model
- `raw_response` — the model's raw JSON output
- `parsed_output` — the validated Pydantic output
- `tokens_in`, `tokens_out`, `latency_s`

Call number reference:
| Call # | Name | When |
|---|---|---|
| `#11` | `scope_inference` | Once per document |
| `#01` | `topic_scanning` | Once per section (Pass 1) |
| `#04` | `fact_extraction` | Once per topic group (Pass 4) |
| `#99` | `reconstruction_critique` | Once per topic group |
| `#98` | `root_cause_analysis` | Once per topic group with problems |

Trace files are numbered sequentially so you can follow the exact execution order.

---

## How to trace a specific problem

1. Find the topic in `critiques.json` and note the `problem_type` and `description`.
2. Open `topic_docs.json` and find the same topic key.
   - If the missing/wrong information **is** in the topic document → the error is in Pass 4. Open the matching `#04_fact_extraction` trace to see exactly what the model produced.
   - If the information **is not** in the topic document → the error is in Pass 1. Open the matching `#01_topic_scanning` traces to see what spans were captured and what slugs/scopes were assigned.
3. Read `diagnosis.json` for the pre-computed attribution and recommended fix.
4. To verify the fix worked, re-run with a modified prompt and compare `problem_summary.json` across iterations.
