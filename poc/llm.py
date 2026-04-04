"""LLM provider abstraction, prompt rendering, and call execution with trace output."""
from __future__ import annotations

import abc
import copy
import json
import os
import re
import time
from pathlib import Path
from typing import Type, TypeVar

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

# ── Prompt registry ───────────────────────────────────────────────────────────

_prompts_dir = Path(__file__).parent / "prompts"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_prompts_dir)),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_prompt(template_name: str, **kwargs: object) -> str:
    template = _jinja_env.get_template(f"{template_name}.j2")
    return template.render(**kwargs)


# ── Provider ABC ──────────────────────────────────────────────────────────────

class LLMProvider(abc.ABC):
    @abc.abstractmethod
    def complete(
        self,
        prompt: str,
        output_schema: type[BaseModel],
        model: str,
    ) -> tuple[str, int, int]:
        """Call the model. Returns (raw_json_str, input_tokens, output_tokens)."""
        ...


# ── Anthropic ─────────────────────────────────────────────────────────────────

class AnthropicProvider(LLMProvider):
    def __init__(self) -> None:
        try:
            import anthropic
        except ImportError:
            raise ImportError("Install with: pip install anthropic")
        self._client = anthropic.Anthropic()

    def complete(self, prompt: str, output_schema: type[BaseModel], model: str) -> tuple[str, int, int]:
        response = self._client.messages.create(
            model=model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
            tools=[{
                "name": "structured_output",
                "description": "Return the structured output as specified.",
                "input_schema": output_schema.model_json_schema(),
            }],
            tool_choice={"type": "tool", "name": "structured_output"},
        )
        tool_block = next(b for b in response.content if b.type == "tool_use")
        return json.dumps(tool_block.input), response.usage.input_tokens, response.usage.output_tokens


# ── OpenAI ────────────────────────────────────────────────────────────────────

def _strict_schema(schema: dict) -> dict:
    """Recursively add additionalProperties: false for OpenAI strict mode."""
    schema = copy.deepcopy(schema)

    def _add(node: dict) -> None:
        if node.get("type") == "object":
            node.setdefault("additionalProperties", False)
            props = node.get("properties", {})
            if props:
                node["required"] = list(props.keys())
            for v in props.values():
                _add(v)
        for sub in node.get("anyOf", []):
            _add(sub)
        if "items" in node:
            _add(node["items"])
        for v in node.get("$defs", {}).values():
            _add(v)

    _add(schema)
    return schema


class OpenAIProvider(LLMProvider):
    def __init__(self) -> None:
        try:
            import openai
        except ImportError:
            raise ImportError("Install with: pip install openai")
        self._client = openai.OpenAI()

    def complete(self, prompt: str, output_schema: type[BaseModel], model: str) -> tuple[str, int, int]:
        response = self._client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "structured_output",
                    "strict": True,
                    "schema": _strict_schema(output_schema.model_json_schema()),
                },
            },
        )
        raw = response.choices[0].message.content
        return raw, response.usage.prompt_tokens, response.usage.completion_tokens


# ── Gemini ────────────────────────────────────────────────────────────────────

class GeminiProvider(LLMProvider):
    def __init__(self) -> None:
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError("Install with: pip install google-generativeai")
        self._genai = genai

    def complete(self, prompt: str, output_schema: type[BaseModel], model: str) -> tuple[str, int, int]:
        genai = self._genai
        model_obj = genai.GenerativeModel(
            model,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=output_schema,
            ),
        )
        response = model_obj.generate_content(prompt)
        meta = response.usage_metadata
        return response.text, meta.prompt_token_count, meta.candidates_token_count


# ── Provider factory ──────────────────────────────────────────────────────────

def make_provider(model_string: str) -> LLMProvider:
    """Parse 'provider/model-name' and return the appropriate LLMProvider."""
    if "/" not in model_string:
        raise ValueError(
            f"--model must be 'provider/model-name' (e.g. anthropic/claude-sonnet-4-6), got: {model_string!r}"
        )
    provider_name = model_string.split("/", 1)[0].lower()
    if provider_name == "anthropic":
        return AnthropicProvider()
    if provider_name == "openai":
        return OpenAIProvider()
    if provider_name in ("gemini", "google"):
        return GeminiProvider()
    raise ValueError(
        f"Unknown provider {provider_name!r}. Supported: anthropic, openai, gemini"
    )


# ── Result summary ────────────────────────────────────────────────────────────

def _result_summary(result: BaseModel) -> str:
    from schemas import (
        AffectedFactIdentificationOutput,
        DiagnosisOutput,
        FactContentDraftingOutput,
        FactExtractionOutput,
        ScopeInferenceOutput,
        TopicScanOutput,
        TopicTagRecommendationOutput,
    )
    if isinstance(result, TopicScanOutput):
        skipped = sum(1 for r in result.records if r.topic_slug == "skip-candidate")
        return f"{len(result.records)} scan records ({skipped} skip-candidates)"
    if isinstance(result, FactExtractionOutput):
        return f"{len(result.facts)} facts extracted"
    if isinstance(result, ScopeInferenceOutput):
        return f"audience={result.audience_scope}  channel={result.channel_scope}"
    if isinstance(result, AffectedFactIdentificationOutput):
        return f"{len(result.affected_facts)} facts identified"
    if isinstance(result, FactContentDraftingOutput):
        return f"revised — {result.change_summary[:70]}"
    if isinstance(result, TopicTagRecommendationOutput):
        adds = sum(1 for t in result.tag_changes if t.action == "add")
        removes = sum(1 for t in result.tag_changes if t.action == "remove")
        return f"{len(result.topic_tags)} tags ({adds} added, {removes} removed)"
    if isinstance(result, DiagnosisOutput):
        return f"{len(result.problems)} problems attributed"
    return "done"


# ── Trace printer ─────────────────────────────────────────────────────────────

def _print_trace(
    call_number: int,
    call_name: str,
    description: str,
    in_tok: int,
    out_tok: int,
    elapsed: float,
    validation: str,
    result: BaseModel | None,
) -> None:
    print(f'[#{call_number} {call_name}] "{description}"')
    print(f"  tokens: {in_tok} in / {out_tok} out  |  latency: {elapsed:.1f}s  |  validation: {validation}")
    if result is not None:
        print(f"  → {_result_summary(result)}")


# ── Trace file writer ─────────────────────────────────────────────────────────

_call_counter = 0  # global sequence number for ordering trace files


def _save_trace(
    call_number: int,
    call_name: str,
    description: str,
    prompt: str,
    raw: str,
    result: BaseModel | None,
    validation: str,
    in_tok: int,
    out_tok: int,
    elapsed: float,
) -> None:
    trace_dir = os.environ.get("FACTSQUID_TRACE_DIR")
    if not trace_dir:
        return
    Path(trace_dir).mkdir(parents=True, exist_ok=True)
    global _call_counter
    _call_counter += 1
    slug = re.sub(r'[^a-z0-9]+', '_', description.lower()).strip('_')[:50]
    filename = f"{_call_counter:04d}__{call_number:02d}_{call_name}__{slug}.json"
    record = {
        "seq": _call_counter,
        "call_number": call_number,
        "call_name": call_name,
        "description": description,
        "validation": validation,
        "tokens_in": in_tok,
        "tokens_out": out_tok,
        "latency_s": round(elapsed, 2),
        "prompt": prompt,
        "raw_response": raw,
        "parsed_output": result.model_dump() if result is not None else None,
    }
    Path(trace_dir, filename).write_text(json.dumps(record, indent=2, ensure_ascii=False))


# ── Main call function ────────────────────────────────────────────────────────

def call(
    provider: LLMProvider,
    model: str,
    call_number: int,
    call_name: str,
    description: str,
    prompt: str,
    output_schema: Type[T],
) -> T:
    """Render prompt, call provider, validate output, print trace. Retries once on validation failure."""
    model_name = model.split("/", 1)[-1]
    start = time.monotonic()
    total_in = total_out = 0
    raw = ""

    raw, in_tok, out_tok = provider.complete(prompt, output_schema, model_name)
    total_in += in_tok
    total_out += out_tok

    validation = "PASS"
    try:
        result: T = output_schema.model_validate_json(raw)
    except (ValidationError, Exception) as first_err:
        retry_prompt = (
            prompt
            + f"\n\n---\nYour previous response failed validation:\n{first_err}\n\n"
            "Please respond again with a corrected JSON structure matching the schema exactly."
        )
        raw2, in_tok2, out_tok2 = provider.complete(retry_prompt, output_schema, model_name)
        total_in += in_tok2
        total_out += out_tok2
        raw = raw2
        try:
            result = output_schema.model_validate_json(raw2)
            validation = "RETRY-PASS"
        except (ValidationError, Exception) as e2:
            elapsed = time.monotonic() - start
            _print_trace(call_number, call_name, description, total_in, total_out, elapsed, "FAIL", None)
            _save_trace(call_number, call_name, description, retry_prompt, raw2, None, "FAIL", total_in, total_out, elapsed)
            raise RuntimeError(f"Call {call_name!r} failed after retry: {e2}") from e2

    elapsed = time.monotonic() - start
    _print_trace(call_number, call_name, description, total_in, total_out, elapsed, validation, result)
    _save_trace(call_number, call_name, description, prompt, raw, result, validation, total_in, total_out, elapsed)
    return result
