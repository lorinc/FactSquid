"""Deterministic document reconstruction from extracted facts + template."""
from __future__ import annotations

from collections import defaultdict

from schemas import ExtractedFact


def reconstruct_document(facts: list[ExtractedFact], template: dict) -> str:
    """Rebuild a markdown document from facts + template section order.

    Args:
        facts: all facts extracted from the document, in extraction order
        template: {"document": str, "sections": [{"section_title", "level", ...}]}

    Returns:
        Markdown string approximating the original document structure.
    """
    facts_by_section: dict[str, list[ExtractedFact]] = defaultdict(list)
    for f in facts:
        facts_by_section[f.source_section].append(f)

    lines: list[str] = []
    doc_title = template["document"].replace("_", " ").replace("-", " ").title()
    lines.append(f"# {doc_title}")
    lines.append("")

    for section_info in template["sections"]:
        title = section_info["section_title"]
        level = section_info.get("level", 2)
        heading = "#" * min(level + 1, 4)
        lines.append(f"{heading} {title}")
        lines.append("")

        section_facts = facts_by_section.get(title, [])
        if not section_facts:
            lines.append("*(no facts extracted)*")
            lines.append("")
            continue

        _render_facts(section_facts, lines)

    return "\n".join(lines).rstrip() + "\n"


def _render_facts(facts: list[ExtractedFact], lines: list[str]) -> None:
    """Render facts in order using their render_as hint."""
    prev_render = None
    numbered_counter = 0

    for f in facts:
        r = f.render_as

        # Reset numbering when render type changes away from numbered-step
        if r != "numbered-step":
            numbered_counter = 0

        # Blank line between render-type groups (except within a list)
        if prev_render is not None and r != prev_render and prev_render in ("paragraph",):
            lines.append("")

        if r == "paragraph":
            lines.append(f.content)
            lines.append("")

        elif r == "bullet":
            lines.append(f"- {f.content}")

        elif r == "numbered-step":
            numbered_counter += 1
            lines.append(f"{numbered_counter}. {f.content}")

        elif r == "definition-entry":
            # Content should already be in **Term:** format; render as bullet if not
            lines.append(f"- {f.content}")

        else:
            lines.append(f"- {f.content}")

        prev_render = r

    # Trailing blank line after list blocks
    if prev_render in ("bullet", "numbered-step", "definition-entry"):
        lines.append("")


def section_text(facts: list[ExtractedFact]) -> str:
    """Render a flat list of facts for one section as a string (for critique prompts)."""
    lines: list[str] = []
    _render_facts(facts, lines)
    return "\n".join(lines).strip()
