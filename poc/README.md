# FactSquid POC

Proves the two LLM-heavy flows before building infrastructure.

**Chain A — Document → Facts**: extract atomic, reusable policy facts from markdown documents.  
**Chain B — Change Request → Proposal**: given a natural-language change, identify the affected facts and propose revised wording.

Not in scope: auth, git, Postgres, Temporal, rendering, deduplication, production reliability.

---

## Setup

```bash
cd poc
python3 -m venv .venv
source .venv/bin/activate
pip install ".[anthropic]"   # or: openai / gemini
pip install ".[embed]"       # needed for Chain B only
```

Create `poc/.env`:
```
OPENAI_API_KEY=sk-...
# or ANTHROPIC_API_KEY / GOOGLE_API_KEY
```

---

## Running

```bash
set -a && source .env && set +a

# Chain A — extract facts from all 4 test docs
python run_onboarding.py --model openai/gpt-4o --save output/corpus.json

# Chain A — one-doc quality iteration (see Iteration Loop below)
python run_iteration.py --model openai/gpt-4o --doc 4 --save iterations/iter_001

# Chain B — change proposals against the corpus
python run_change.py --model openai/gpt-4o --corpus output/corpus.json --save output/proposals.json
```

---

## Development Corpus

`poc/test_docs/` — four synthetic excerpts from Imagine Montessori School Valencia. Small enough to run cheaply; each doc exercises a different extraction challenge.

| File | Content | Key challenge |
|---|---|---|
| `test_doc_1_school_hours.md` | Hours, punctuality, fees, absence procedure | Fee facts embedded in procedure text |
| `test_doc_2_terminology.md` | Outings definitions + policy principles + objectives | Mixed `kind` values; skip-candidate behaviour |
| `test_doc_3_emergency_procedure.md` | Accident and emergency procedure on outings | Deep-nested procedure → stand-alone facts |
| `test_doc_4_dress_code.md` | §2.4 Student dress code + §2.5 Staff dress code | Two scoped sub-topics in one document |

Once the pipeline produces good results on these four docs, run once against `data/test_corpus/` as a scale check. Do not iterate on the full corpus — token cost is prohibitive.

---

## The Five Tests

Every extracted fact must pass all five:

1. **Stand-Alone** — a reader with no other facts must fully understand the policy. No implied "who?", "when?", "except what?"
2. **One Topic** — a single noun phrase names the subject. If "and" is needed, split.
3. **Reconstruction** — concatenating all facts from a topic must be informationally equivalent to the source: same obligations, permissions, exceptions, values.
4. **Canonical Form** — active voice, no navigation language ("as mentioned in", "refer to"), no redundant preamble.
5. **Template-Slot Ready** — no audience framing ("as a parent, you should…"), no channel framing baked in.

---

## The Iteration Loop

The core quality workflow. Pick one test document, run the full pipeline, review the critique and diagnosis, make one targeted change to a prompt, repeat.

```bash
# Force a specific doc (1–4)
python run_iteration.py --model openai/gpt-4o --doc 4 --save iterations/iter_001

# Random doc (recommended — avoids overfitting to one doc)
python run_iteration.py --model openai/gpt-4o --save iterations/iter_002
```

Each iteration produces output in `iterations/iter_NNN/`. The terminal output shows:
- Per topic: extracted facts, critique verdict, and — for any topic with problems — a root cause diagnosis
- Summary: problem counts by type

**After reading the output:**
1. Check `problem_summary.json` for the dominant problem type.
2. Read `diagnosis.json` to find which pass and prompt introduced each problem.
3. Make **one targeted change** to `prompts/fact_extraction.j2` or `prompts/topic_scanning.j2`.
4. Re-run on a different doc to verify the fix generalises.

---

## Reading Iteration Output

Each `iterations/iter_NNN/` directory contains:

### `facts.json`
The pipeline's final output: all extracted facts. Key fields per fact:
- `id` — `topic_slug__scope_qualifier__index`
- `title`, `content`, `kind` — the fact (`kind` is `rationale`/`principle`/`context` or null for policy facts)
- `topic_slug`, `scope_qualifier` — the grouping key from Pass 1
- `source_spans` — provenance: which source headings contributed content
- `audience_scope`, `channel_scope` — inferred from the document

### `topic_docs.json`
The assembled topic documents from Pass 3, one per `(topic_slug, scope_qualifier)` group. Each is the verbatim source text the Pass 4 LLM received. **Start here when tracing a problem**: if the missing information is in this file, the error is in Pass 4 (extraction); if it's absent, the error is in Pass 1 (scanning).

### `critiques.json`
Per-topic quality assessment against the Five Tests.

| Problem type | Meaning |
|---|---|
| `missing-content` | An obligation, permission, exception, or value is absent |
| `not-standalone` | Implies "who", "when", or "except what" without stating it |
| `not-canonical` | Navigation language, passive construction, or redundant preamble |
| `not-template-ready` | Audience- or channel-specific framing baked in |
| `over-atomized` | One logical unit split into too many facts |
| `under-atomized` | Multiple distinct topics merged into one fact |
| `wrong-tags` | Topic tags inconsistent with topic_slug or source |

### `diagnosis.json`
Root cause attribution for every critique problem. Each entry names the pass that introduced the error (`pass-1`, `pass-3`, or `pass-4`), the specific component (`fact_extraction.j2`, `topic_scanning.j2`, etc.), an explanation of what went wrong, and a concrete recommended fix.

```json
{
  "root_cause": {
    "pass_attribution": "pass-4",
    "component": "fact_extraction.j2",
    "explanation": "The LLM transformed 'are expected to dress' into 'are required to,' making the tone less neutral.",
    "recommended_fix": "Preserve original modal verbs unless the meaning requires change."
  }
}
```

### `problem_summary.json`
Problem type counts across all topics. Use this to prioritise which prompt to fix first.

### `traces/`
One JSON file per LLM call: `{seq}__{call_number}_{call_name}__{slug}.json`. Contains the full rendered prompt, raw model response, parsed output, token counts, and latency. Files are sequentially numbered so you can follow exact execution order.

| Call # | Name | Frequency |
|---|---|---|
| `#11` | `scope_inference` | Once per document |
| `#01` | `topic_scanning` | Once per section |
| `#04` | `fact_extraction` | Once per topic group |
| `#99` | `reconstruction_critique` | Once per topic group |
| `#98` | `root_cause_analysis` | Once per topic group with problems |

---

## Tracing a Specific Problem

1. Find the topic in `critiques.json`. Note `problem_type` and `description`.
2. Open `topic_docs.json` for the same topic key.
   - Information **present** in topic doc → Pass 4 fault. Open the `#04_fact_extraction` trace.
   - Information **absent** from topic doc → Pass 1 fault. Open the `#01_topic_scanning` traces.
3. Read `diagnosis.json` for the pre-computed attribution and fix recommendation.
4. Apply the fix, re-run, compare `problem_summary.json` across iterations.

---

## Folder Layout

```
poc/
├── run_onboarding.py       Chain A — full corpus extraction
├── run_iteration.py        Quality iteration loop (critique + diagnosis)
├── run_change.py           Chain B — change proposals
├── schemas.py              Pydantic output models for all LLM calls
├── llm.py                  Provider abstraction + call() with tracing
├── corpus.py               Document loading, token counting, chunking
├── embed.py                Embedding index for Chain B retrieval
├── reconstruct.py          Deterministic fact → markdown reconstruction
├── prompts/                Jinja2 prompt templates
│   ├── topic_scanning.j2               Pass 1: structural inference
│   ├── fact_extraction.j2              Pass 4: content writing
│   ├── scope_inference.j2              Call #11: audience/channel
│   ├── reconstruction_critique.j2      Call #99: quality evaluation
│   ├── root_cause_analysis.j2          Call #98: error attribution
│   ├── affected_fact_identification.j2 Chain B call #1
│   ├── fact_content_drafting.j2        Chain B call #2
│   └── topic_tag_recommendation.j2     Chain B call #3
├── test_docs/              Development corpus (4 synthetic documents)
├── output/                 Full corpus run (corpus.json, proposals.json, traces/)
├── iterations/             Per-doc quality runs (this iteration loop)
└── archive/                Obsolete scripts from the old 3-call pipeline
```
