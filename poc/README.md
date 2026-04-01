# FactSquid POC

Prove the two LLM-heavy flows work before building infrastructure.

**Chain A — Document → Facts** (4-pass extraction per `docs/design/fact-definition.md`)  
**Chain B — Change Request → Proposal** (D15 calls #1 → #2 → #3)

Not in scope: auth, git, Postgres, Temporal, rendering, deduplication (calls #12, #13), production reliability.

---

## Core Principle

**Concentrate all content about a topic before generating facts from it.** Per-section extraction produces fragments; grouping first produces whole facts.

This is the foundation of the 4-pass pipeline:
1. **Pass 1** — Topic Scanning (LLM, per section): structural inference only, no summarisation
2. **Pass 2** — Grouping (deterministic): group by `(topic_slug, scope_qualifier)`
3. **Pass 3** — Topic Document Assembly (deterministic): concatenate verbatim spans with provenance
4. **Pass 4** — Fact Extraction (LLM, per topic document): the only pass that writes content

---

## The Five Tests

Every fact must pass all five tests from `fact-definition.md`:

1. **Stand-Alone** — a reader with no other facts must fully understand the policy. No implied "who does this apply to?", "when?", "except what?"
2. **One Topic** — a single noun phrase names the subject. If "and" is needed, split.
3. **Reconstruction** — concatenating all facts from a topic document must be informationally equivalent to the topic document: same obligations, permissions, exceptions, values.
4. **Canonical Form** — active voice, no document-navigation language ("as mentioned in", "refer to"), no redundant preamble ("it is important to note that").
5. **Template-Slot Ready** — no audience-specific framing baked in ("as a parent, you should…"), no channel-specific framing ("as you read this handbook…").

---

## Development Corpus

**`poc/test_docs/`** — four synthetic excerpts from Imagine Montessori School Valencia, small enough to run cheaply during iteration.

| File | Content | Audience |
|---|---|---|
| `test_doc_1_school_hours.md` | Hours, punctuality, fees, absence procedure | Parents |
| `test_doc_2_terminology.md` | Outings definitions + policy principles + objectives | Staff |
| `test_doc_3_emergency_procedure.md` | Accident and emergency procedure on outings | Staff |
| `test_doc_4_dress_code.md` | §2.4 Student dress code + §2.5 Staff dress code | Students, Staff, Parents |

**Key test properties**:
- `test_doc_4` has two distinct scoped sub-topics in one document (`dress-code/students` and `dress-code/staff`) — the primary same-topic-different-scope test case.
- `test_doc_2` mixes definitions, principles, and objectives — tests `kind` assignment and skip-candidate behaviour.
- `test_doc_1` has fees and contact-details embedded in procedure text — tests type variety and whether fee/contact-detail facts are separated cleanly.
- `test_doc_3` is a single deep-nested procedure — tests whether Pass 4 produces stand-alone facts from complex nested content.

**Graduation**: once the pipeline produces good results on the development corpus, run once against `data/test_corpus/` as a scale check. Do not iterate on the full corpus — token cost is prohibitive.

---

## Setup

```bash
cd poc
python3 -m venv .venv
source .venv/bin/activate  # or .venv/bin/activate.fish
pip install ".[anthropic]"    # or: openai / gemini
pip install ".[embed]"         # needed for Chain B only
```

Create a `.env` file:
```
OPENAI_API_KEY=sk-...
# or ANTHROPIC_API_KEY / GOOGLE_API_KEY
```

---

## Running the POC

```bash
set -a && source .env && set +a

# Chain A — run all 4 test docs
python3 run_onboarding.py --model anthropic/claude-sonnet-4-6 --save output/corpus.json

# Chain A — iteration loop (one doc at a time)
python3 run_iteration.py --model anthropic/claude-sonnet-4-6 --doc 4 --save iterations/iter_001

# Chain B — change proposals
python3 run_change.py --model anthropic/claude-sonnet-4-6 --corpus output/corpus.json --save output/proposals.json
```

Set `FACTSQUID_TRACE_DIR=./traces` to save every LLM call's prompt, raw response, and parsed output as JSON files.

---

## Testing Process

### Iteration Loop (Chain A quality improvement)

Each iteration: **pick test doc → extract → reconstruct → critique → improve one thing → repeat**.

```bash
# Random test doc (recommended — avoids overfitting to one doc)
python run_iteration.py --model anthropic/claude-sonnet-4-6 --save iterations/iter_001

# Force a specific test doc (1–4)
python run_iteration.py --model anthropic/claude-sonnet-4-6 --doc 2 --save iterations/iter_001
```

Output per topic document:
- Topic slug and scope qualifier
- Span count (how many source spans were grouped)
- Fact count (how many facts were extracted)
- Reconstruction critique (LLM evaluation against the Five Tests)

**After reading the output**:
1. Identify the **most frequent or most damaging** problem type.
2. Make **one targeted change** — usually to `prompts/fact_extraction.j2` or `prompts/topic_scanning.j2`.
3. Re-run on a different test doc to verify the fix generalises.
4. Save each iteration's output to a numbered directory (`iter_001`, `iter_002`, …).

### Reconstruction Verification

Primary quality criterion for Chain A (Test 3 from `fact-definition.md`).

For each topic document: concatenate `title + content` of all facts extracted from it. Compare to the topic document. Must be informationally equivalent: same obligations, permissions, exceptions, numerical values. Different words are fine. Missing or added information is a failure.

Run with an LLM critique call (`reconstruction_critique.j2`) per topic document. Used in `run_iteration.py` for development-loop feedback.

### The Three Change Requests (Chain B)

1. **Dress code** — "Update the student dress code: students may now wear trainers on any day, not just PE days."
   - Expected: `dress-code/students` facts from `test_doc_4`. Must not affect `dress-code/staff` facts. Tests scope isolation.

2. **Late arrival fee** — "Update the late arrival fee threshold: the €5 fee now applies from the third late arrival in the year, not the fifth."
   - Expected: fee facts in `test_doc_1`. Tests whether embedded fee facts are cleanly separated from procedure text.

3. **Missing child procedure** — "When a child goes missing on a trip abroad, staff must also contact the local consulate in addition to calling the police."
   - Expected: missing-child procedure facts in `test_doc_3`. Tests whether a targeted change to one sub-procedure leaves the rest of the emergency procedure facts unchanged.

---

## What a "Pass" Looks Like

**Chain A** — an administrator looking at the output says: *"This looks like my school's structure. The facts make sense. Where the same policy appeared in multiple documents, it's been concentrated into one place."*

**Chain B** — an administrator says: *"Yes, these are the right facts to change — including the ones I forgot were duplicated — and the proposed wording captures what I asked for."*

---

## Key Files

```
poc/
├── schemas.py              Pydantic output models for all LLM calls
├── llm.py                  LLMProvider ABC + Anthropic/OpenAI/Gemini + call() with trace
├── corpus.py               Code-fence stripping, H1 chunking
├── embed.py                sentence-transformers index for Chain B retrieval
├── reconstruct.py          Deterministic fact → markdown reconstruction
├── run_iteration.py        Quality iteration loop
├── run_onboarding.py       Chain A (full corpus)
├── run_change.py           Chain B
├── prompts/                Jinja2 templates
│   ├── topic_scanning.j2                   Pass 1 (structural inference)
│   ├── fact_extraction.j2                  Pass 4 (content writing)
│   ├── scope_inference.j2                  Call #11 (audience/channel)
│   ├── affected_fact_identification.j2     Chain B call #1
│   ├── fact_content_drafting.j2            Chain B call #2
│   ├── topic_tag_recommendation.j2         Chain B call #3
│   └── reconstruction_critique.j2          Evaluation tool
├── test_docs/              Development corpus (4 synthetic excerpts)
└── archive/                Obsolete scripts from old 3-call pipeline
```
