import re
from dataclasses import dataclass, field
from typing import Any

# Match [1], [2], etc. that are NOT followed by '(' (which would be a markdown link [label](url))
INLINE_CITATION_RE = re.compile(r"\[(\d+)\](?!\()")
URL_IN_TEXT_RE = re.compile(r"https?://[^\s\)\]>\"']+")
CODE_BLOCK_RE = re.compile(r"```[\s\S]*?```")


@dataclass
class CitationValidationResult:
    is_valid: bool
    cited_numbers: list[int] = field(default_factory=list)
    invalid_numbers: list[int] = field(default_factory=list)
    ungrounded_urls: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    references_markdown: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "cited_numbers": self.cited_numbers,
            "invalid_numbers": self.invalid_numbers,
            "ungrounded_urls": self.ungrounded_urls,
            "errors": self.errors,
            "warnings": self.warnings,
        }


def build_references_section(
    cited_numbers: list[int],
    sources_by_num: dict[int, dict[str, Any]],
) -> str:
    """Build a deterministic numbered References markdown section from collected sources."""
    if not cited_numbers:
        return "## References\n\n_No verified external citations were referenced in this report._\n"

    lines = ["## References", ""]
    for num in sorted(set(cited_numbers)):
        src = sources_by_num.get(num)
        if not src:
            continue
        title = src.get("title") or "Untitled Source"
        publisher = src.get("publisher") or "Unknown Publisher"
        author = src.get("author")
        published_at = src.get("published_at") or "Date unavailable"
        retrieved_at = str(src.get("retrieved_at") or "")[:10] or "Unknown"
        source_type = src.get("source_type") or "company"
        url = src.get("url") or ""
        excerpt = (src.get("supporting_claim") or src.get("raw_excerpt") or "").strip()
        if len(excerpt) > 220:
            excerpt = excerpt[:217].rstrip() + "..."

        parts = [f"[{num}] **{title}** — {publisher}"]
        if author:
            parts.append(f"Author: {author}")
        parts.append(f"Published: {published_at}")
        parts.append(f"Accessed: {retrieved_at}")
        parts.append(f"Type: `{source_type}`")
        lines.append(" | ".join(parts) + f"  \nURL: <{url}>")
        if excerpt:
            lines.append(f"> Evidence note: {excerpt}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def strip_existing_references_section(markdown: str) -> str:
    """Remove any LLM-written References section so deterministic verified references are appended."""
    pattern = re.compile(r"\n##\s+References\b[\s\S]*$", re.IGNORECASE)
    return pattern.sub("", markdown).strip()


def validate_report_citations(
    markdown_report: str,
    sources_by_num: dict[int, dict[str, Any]],
) -> tuple[CitationValidationResult, str]:
    """
    Validate that every inline citation [n] maps to an actual collected source,
    no ungrounded URLs were invented, and attach a verified References section.
    """
    body_without_refs = strip_existing_references_section(markdown_report)
    scan_text = CODE_BLOCK_RE.sub("", body_without_refs)

    found_numbers = [int(m.group(1)) for m in INLINE_CITATION_RE.finditer(scan_text)]
    unique_found = sorted(set(found_numbers))
    invalid_numbers = [n for n in unique_found if n not in sources_by_num]
    valid_cited = [n for n in unique_found if n in sources_by_num]

    known_urls = {
        str(src.get("url", "")).rstrip("/").lower() for src in sources_by_num.values()
    } | {
        str(src.get("canonical_url", "")).rstrip("/").lower()
        for src in sources_by_num.values()
        if src.get("canonical_url")
    }

    found_urls = [u.rstrip(".,;:").lower() for u in URL_IN_TEXT_RE.findall(scan_text)]
    ungrounded_urls = sorted(
        {
            u
            for u in found_urls
            if u.rstrip("/") not in known_urls
        }
    )

    errors: list[str] = []
    warnings: list[str] = []

    if not sources_by_num:
        errors.append("No collected sources exist for this research run.")
    if not valid_cited:
        errors.append("Report contains zero valid inline citations referencing collected sources.")
    if invalid_numbers:
        errors.append(
            f"Report references non-existent citation numbers: {invalid_numbers}"
        )
    if ungrounded_urls:
        errors.append(
            f"Report contains ungrounded URLs not present in collected sources: {ungrounded_urls}"
        )

    references_md = build_references_section(valid_cited, sources_by_num)
    final_markdown = f"{body_without_refs}\n\n{references_md}".strip() + "\n"

    result = CitationValidationResult(
        is_valid=len(errors) == 0,
        cited_numbers=valid_cited,
        invalid_numbers=invalid_numbers,
        ungrounded_urls=ungrounded_urls,
        errors=errors,
        warnings=warnings,
        references_markdown=references_md,
    )
    return result, final_markdown
