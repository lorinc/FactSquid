# iter_002 — Session notes & next steps

## What changed in iter_002
- Rewrote `prompts/fact_decomposition.j2`: replaced "ONE SOURCE ELEMENT = ONE FACT" with concept-driven grouping
- Facts now expected to span multiple paragraphs/bullets when they cover the same topic
- Added concrete good/bad examples including the "Pedagogical Meetings" full-section example
- Fixed `llm.py` `_strict_schema` to include all properties in `required` (OpenAI strict mode fix)
- Added trace saving to `--save` dir: sets `FACTSQUID_TRACE_DIR` automatically when `--save` is given

## Results: iter_001 vs iter_002 (same doc: test_doc_4_dress_code.md)
| | iter_001 | iter_002 |
|---|---|---|
| Facts extracted | 20 | 6 |
| Total critique problems | 6 | 6 |

Grouping dramatically improved. "Not acceptable" list (7 bullets) correctly collapsed to 1 fact.

## Remaining problems

### 1. Multi-bullet content uses " / " separators instead of markdown
The model serialised the "Not acceptable" bullets as:
`"Mini-skirts... / Leisure shorts... / Transparent..."`
instead of preserving `*` markdown bullets. reconstruct.py can't render these as a list → `wrong-render`.

**Proposed fix:** Add to the prompt: "Preserve the original markdown formatting in `content` — keep `*` bullets as `*` bullets on separate lines, do not join them with separators."

### 2. Duplicate fact + missing sub-section (student dress code)
Headwear block extracted twice (once `paragraph`, once `bullet`); Footwear sub-section absent as a distinct fact. Likely caused by ambiguity about whether to group Headwear+Footwear+General+PE into one fact or keep as sub-topic facts.

**Proposed fix:** Clarify in the prompt that sub-sections within a document section can remain as separate facts when they cover clearly distinct sub-topics (headwear vs footwear vs general style). The 300–2000 char guideline should be the primary grouping signal.

### 3. Critique truncation artefact
Some `missing-content` critique problems appear to be triggered by the 800-char truncation of `original_content` and `reconstructed_content` passed to the critique prompt (see `run_iteration.py:63`). The critique LLM sees incomplete text and flags content as missing.

**Proposed fix:** Increase or remove the `:800` slice, or pass full section text.

## Next iteration recommendation
Fix issue #1 (markdown preservation in content) — it's the most mechanically clear and has the highest impact on reconstruction quality. Test on `--doc 2` (terminology/definitions) to check generalisation.
