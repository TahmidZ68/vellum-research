import asyncio
from collections import Counter
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from app.agents.prompts.research_prompts import (
    SYSTEM_ANALYST_PROMPT,
    build_cross_check_prompt,
    build_extract_evidence_prompt,
    build_gaps_prompt,
    build_generate_report_prompt,
    build_research_plan_prompt,
    build_search_queries_prompt,
    build_understand_question_prompt,
)
from app.agents.state import ResearchState
from app.core.config import Settings, get_settings
from app.core.security_url import UnsafeURLError, canonicalize_url, validate_public_url
from app.providers.base import BaseLLMProvider, BaseSearchProvider, SearchOptions
from app.services.citation_validator import validate_report_citations
from app.services.extraction import (
    fetch_and_extract_source,
    infer_source_type,
    wrap_untrusted_source,
)

EventEmitter = Callable[[str, str, str, dict[str, Any] | None], Awaitable[None]]
CancelChecker = Callable[[str], Awaitable[bool]]


class ResearchNodes:
    """Testable collection of LangGraph node functions for the research pipeline."""

    def __init__(
        self,
        *,
        llm: BaseLLMProvider,
        search_provider: BaseSearchProvider,
        emit_event: EventEmitter | None = None,
        is_cancelled: CancelChecker | None = None,
        settings: Settings | None = None,
        resolve_dns_on_fetch: bool = True,
    ) -> None:
        self.llm = llm
        self.search_provider = search_provider
        self.emit_event = emit_event
        self.is_cancelled = is_cancelled
        self.settings = settings or get_settings()
        self.resolve_dns_on_fetch = resolve_dns_on_fetch

    async def _emit(
        self,
        state: ResearchState,
        event_type: str,
        stage: str,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        if self.emit_event:
            await self.emit_event(event_type, stage, message, data)

    async def _check_cancelled(self, state: ResearchState) -> bool:
        if state.get("cancel_requested"):
            return True
        run_id = state.get("run_id")
        if self.is_cancelled and run_id:
            return await self.is_cancelled(run_id)
        return False

    async def understand_question(self, state: ResearchState) -> dict[str, Any]:
        if await self._check_cancelled(state):
            return {"cancel_requested": True, "current_stage": "cancelled", "final_status": "cancelled"}

        stage = "understand_question"
        await self._emit(state, "stage_started", stage, "Analyzing research question and scope", None)

        prompt = build_understand_question_prompt(
            state["original_question"],
            state.get("research_context", ""),
            state.get("language", "en"),
        )
        analysis = await self.llm.generate_json(SYSTEM_ANALYST_PROMPT, prompt)
        await self._emit(
            state,
            "stage_completed",
            stage,
            "Question scope identified",
            {"topic": analysis.get("topic", ""), "objective": analysis.get("objective", "")},
        )
        return {"question_analysis": analysis, "current_stage": stage}

    async def create_research_plan(self, state: ResearchState) -> dict[str, Any]:
        if await self._check_cancelled(state):
            return {"cancel_requested": True, "current_stage": "cancelled", "final_status": "cancelled"}

        stage = "create_research_plan"
        await self._emit(state, "stage_started", stage, "Decomposing question into subquestions", None)

        max_subquestions, _ = self.settings.get_depth_limits(state.get("research_depth", "standard"))
        prompt = build_research_plan_prompt(
            state["original_question"],
            state.get("question_analysis", {}),
            max_subquestions,
            state.get("source_preferences", []),
        )
        plan = await self.llm.generate_json(SYSTEM_ANALYST_PROMPT, prompt)
        subquestions = plan.get("subquestions", [])[:max_subquestions]

        await self._emit(
            state,
            "plan_created",
            stage,
            f"Created research plan with {len(subquestions)} subquestions",
            {"subquestions": subquestions, "search_strategy": plan.get("search_strategy", {})},
        )
        return {
            "research_plan": plan,
            "subquestions": subquestions,
            "current_stage": stage,
        }

    async def generate_search_queries(self, state: ResearchState) -> dict[str, Any]:
        if await self._check_cancelled(state):
            return {"cancel_requested": True, "current_stage": "cancelled", "final_status": "cancelled"}

        stage = "generate_search_queries"
        await self._emit(state, "stage_started", stage, "Formulating diverse web search queries", None)

        already_executed = list(state.get("executed_queries", []))
        follow_up_hints = list(state.get("follow_up_queries", []))

        if follow_up_hints and state.get("retry_count", 0) > 0:
            candidate_queries = follow_up_hints
        else:
            prompt = build_search_queries_prompt(
                state["original_question"],
                state.get("subquestions", []),
                already_executed,
                follow_up_hints,
            )
            res = await self.llm.generate_json(SYSTEM_ANALYST_PROMPT, prompt)
            candidate_queries = [str(q).strip() for q in res.get("queries", []) if str(q).strip()]

        seen_norm = {q.lower() for q in already_executed}
        fresh_queries: list[str] = []
        for q in candidate_queries:
            if q.lower() not in seen_norm:
                seen_norm.add(q.lower())
                fresh_queries.append(q)

        if not fresh_queries and not already_executed:
            fresh_queries = [state["original_question"]]

        await self._emit(
            state,
            "queries_generated",
            stage,
            f"Prepared {len(fresh_queries)} targeted search queries",
            {"queries": fresh_queries},
        )
        return {"search_queries": fresh_queries, "current_stage": stage}

    async def search_web(self, state: ResearchState) -> dict[str, Any]:
        if await self._check_cancelled(state):
            return {"cancel_requested": True, "current_stage": "cancelled", "final_status": "cancelled"}

        stage = "search_web"
        queries = list(state.get("search_queries", []))
        await self._emit(
            state,
            "stage_started",
            stage,
            f"Executing {len(queries)} web searches via {self.search_provider.provider_name}",
            {"queries": queries},
        )

        depth = state.get("research_depth", "standard")
        search_depth = "advanced" if depth == "deep" else "basic"
        per_query_limit = 5 if depth == "quick" else 6 if depth == "standard" else 8

        options = SearchOptions(
            max_results=per_query_limit,
            search_depth=search_depth,
            date_range=state.get("date_range", "any"),
            include_raw_content=False,
        )

        all_results = list(state.get("search_results", []))
        executed = list(state.get("executed_queries", []))
        errors = list(state.get("errors", []))

        for query in queries:
            if await self._check_cancelled(state):
                return {"cancel_requested": True, "current_stage": "cancelled", "final_status": "cancelled"}
            executed.append(query)
            try:
                items = await self.search_provider.search(query, options)
                for item in items:
                    all_results.append(
                        {
                            "url": item.url,
                            "title": item.title,
                            "snippet": item.snippet,
                            "publisher": item.publisher,
                            "published_at": item.published_at,
                            "score": item.score,
                            "raw_content": item.raw_content,
                            "query": query,
                            "metadata": item.metadata,
                        }
                    )
            except Exception as exc:
                errors.append(f"Search failed for query '{query}': {exc}")

        await self._emit(
            state,
            "sources_discovered",
            stage,
            f"Discovered {len(all_results)} candidate search hits",
            {"total_hits": len(all_results)},
        )
        return {
            "search_results": all_results,
            "executed_queries": executed,
            "errors": errors,
            "current_stage": stage,
        }

    async def deduplicate_sources(self, state: ResearchState) -> dict[str, Any]:
        stage = "deduplicate_sources"
        raw_results = list(state.get("search_results", []))
        by_canonical: dict[str, dict[str, Any]] = {}

        for item in raw_results:
            raw_url = str(item.get("url", "")).strip()
            if not raw_url:
                continue
            try:
                await validate_public_url(raw_url, resolve_dns=False)
            except UnsafeURLError:
                continue

            canon = canonicalize_url(raw_url)
            existing = by_canonical.get(canon)
            score = float(item.get("score") or 0.5)
            if existing is None or score > float(existing.get("score") or 0.0):
                item_copy = dict(item)
                item_copy["canonical_url"] = canon
                by_canonical[canon] = item_copy

        deduped = list(by_canonical.values())
        await self._emit(
            state,
            "stage_completed",
            stage,
            f"Deduplicated {len(raw_results)} hits into {len(deduped)} unique public URLs",
            {"unique_sources": len(deduped)},
        )
        return {"deduplicated_sources": deduped, "current_stage": stage}

    async def rank_sources(self, state: ResearchState) -> dict[str, Any]:
        stage = "rank_sources"
        _, max_sources = self.settings.get_depth_limits(state.get("research_depth", "standard"))
        candidates = list(state.get("deduplicated_sources", []))
        preferences = {p.lower() for p in state.get("source_preferences", [])}

        # Rank with domain diversity penalty so one domain doesn't monopolize all slots
        domain_counts: Counter[str] = Counter()
        scored: list[tuple[float, dict[str, Any]]] = []
        for item in candidates:
            host = (urlparse(item["url"]).hostname or "").lower().removeprefix("www.")
            inferred_type = item.get("metadata", {}).get("source_type") or infer_source_type(
                item["url"], item.get("title", ""), item.get("snippet", "")
            )
            base_score = float(item.get("score") or 0.5)
            pref_boost = 0.15 if preferences and inferred_type in preferences else 0.0
            recency_boost = 0.05 if item.get("published_at") else 0.0
            diversity_penalty = 0.12 * domain_counts[host]
            domain_counts[host] += 1
            final_score = max(0.0, min(1.0, base_score + pref_boost + recency_boost - diversity_penalty))

            enriched = dict(item)
            enriched["source_type"] = inferred_type
            enriched["relevance_score"] = round(final_score, 3)
            enriched["relevance_note"] = (
                f"Matched search score ({base_score:.2f}); classified as {inferred_type}"
                + (" (matches preference)" if pref_boost > 0 else "")
            )
            scored.append((final_score, enriched))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        selected = [item for _, item in scored[:max_sources]]
        for idx, src in enumerate(selected, start=1):
            src["citation_number"] = idx

        await self._emit(
            state,
            "stage_completed",
            stage,
            f"Selected top {len(selected)} sources for content extraction",
            {
                "selected_sources": [
                    {
                        "citation_number": s["citation_number"],
                        "title": s["title"],
                        "url": s["url"],
                        "publisher": s["publisher"],
                        "source_type": s["source_type"],
                    }
                    for s in selected
                ]
            },
        )
        return {"selected_sources": selected, "current_stage": stage}

    async def extract_source_content(self, state: ResearchState) -> dict[str, Any]:
        if await self._check_cancelled(state):
            return {"cancel_requested": True, "current_stage": "cancelled", "final_status": "cancelled"}

        stage = "extract_source_content"
        selected = list(state.get("selected_sources", []))
        await self._emit(
            state,
            "stage_started",
            stage,
            f"Extracting readable content from {len(selected)} sources",
            None,
        )

        semaphore = asyncio.Semaphore(self.settings.MAX_EXTRACTION_CONCURRENCY)

        async def _extract_one(src: dict[str, Any]) -> dict[str, Any]:
            async with semaphore:
                doc = await fetch_and_extract_source(
                    src["url"],
                    fallback_title=src.get("title", ""),
                    fallback_snippet=src.get("snippet", ""),
                    fallback_published_at=src.get("published_at"),
                    prefetched_raw_content=src.get("raw_content"),
                    resolve_dns=self.resolve_dns_on_fetch,
                )
                merged = dict(src)
                merged.update(
                    {
                        "final_url": doc.final_url,
                        "title": doc.title or src.get("title", "Untitled"),
                        "publisher": doc.publisher or src.get("publisher", "Unknown"),
                        "author": doc.author,
                        "published_at": doc.published_at or src.get("published_at"),
                        "content_text": doc.content_text,
                        "raw_excerpt": doc.raw_excerpt,
                        "content_hash": doc.content_hash,
                        "extraction_status": doc.extraction_status,
                        "limitations": doc.limitations,
                        "error_detail": doc.error_detail,
                        "retrieved_at": datetime.now(UTC).isoformat(),
                    }
                )
                await self._emit(
                    state,
                    "source_extracted",
                    stage,
                    f"Processed source [{merged['citation_number']}]: {merged['title'][:70]}",
                    {
                        "citation_number": merged["citation_number"],
                        "url": merged["url"],
                        "title": merged["title"],
                        "extraction_status": merged["extraction_status"],
                    },
                )
                return merged

        extracted_docs = await asyncio.gather(*[_extract_one(s) for s in selected])
        return {"extracted_documents": list(extracted_docs), "current_stage": stage}

    async def extract_evidence(self, state: ResearchState) -> dict[str, Any]:
        if await self._check_cancelled(state):
            return {"cancel_requested": True, "current_stage": "cancelled", "final_status": "cancelled"}

        stage = "extract_evidence"
        docs = list(state.get("extracted_documents", []))
        await self._emit(state, "stage_started", stage, "Extracting verifiable claims and excerpts", None)

        evidence_records: list[dict[str, Any]] = []
        errors = list(state.get("errors", []))

        for doc in docs:
            text_body = doc.get("content_text") or doc.get("raw_excerpt") or doc.get("snippet") or ""
            if not text_body.strip():
                continue
            ref_num = int(doc["citation_number"])
            wrapped = wrap_untrusted_source(
                ref_num,
                title=doc.get("title", ""),
                publisher=doc.get("publisher", ""),
                url=doc.get("url", ""),
                published_at=doc.get("published_at"),
                source_type=doc.get("source_type", "company"),
                content=text_body,
            )
            prompt = build_extract_evidence_prompt(
                state["original_question"],
                wrapped,
                ref_num,
            )
            try:
                res = await self.llm.generate_json(SYSTEM_ANALYST_PROMPT, prompt)
                items = res.get("evidence", [])
                for item in items:
                    if not isinstance(item, dict) or not item.get("claim"):
                        continue
                    evidence_records.append(
                        {
                            "source_ref": ref_num,
                            "source_url": doc.get("url", ""),
                            "publisher": doc.get("publisher", "Unknown"),
                            "published_at": doc.get("published_at"),
                            "claim": str(item.get("claim", "")).strip(),
                            "excerpt": str(item.get("excerpt") or doc.get("raw_excerpt") or "")[:800],
                            "evidence_type": str(item.get("evidence_type") or doc.get("source_type") or "company"),
                            "claim_category": str(item.get("claim_category") or "source_reported_claim"),
                            "relevance": str(item.get("relevance") or "medium"),
                            "date_context": str(item.get("date_context") or doc.get("published_at") or "Date unspecified"),
                            "limitations": str(item.get("limitations") or doc.get("limitations") or ""),
                            "corroboration_status": "single_source",
                        }
                    )
            except Exception as exc:
                errors.append(f"Evidence extraction failed for source [{ref_num}]: {exc}")

        await self._emit(
            state,
            "evidence_extracted",
            stage,
            f"Collected {len(evidence_records)} evidence records",
            {"evidence_count": len(evidence_records)},
        )
        return {
            "evidence_records": evidence_records,
            "errors": errors,
            "current_stage": stage,
        }

    async def evaluate_evidence(self, state: ResearchState) -> dict[str, Any]:
        stage = "evaluate_evidence"
        records = [dict(r) for r in state.get("evidence_records", [])]
        allowed_types = {"primary", "academic", "government", "journalism", "company", "opinion", "promotional"}
        allowed_categories = {"verified_fact", "source_reported_claim", "interpretation", "unverified"}

        for rec in records:
            if rec.get("evidence_type") not in allowed_types:
                rec["evidence_type"] = "company"
            if rec.get("claim_category") not in allowed_categories:
                rec["claim_category"] = "source_reported_claim"
            if rec.get("evidence_type") == "promotional" and "promotional" not in rec.get("limitations", "").lower():
                rec["limitations"] = (
                    f"{rec.get('limitations', '')} Source appears commercial/promotional; requires independent verification."
                ).strip()
            if not rec.get("published_at") and "date" not in rec.get("limitations", "").lower():
                rec["limitations"] = (
                    f"{rec.get('limitations', '')} Publication date unavailable."
                ).strip()

        await self._emit(
            state,
            "stage_completed",
            stage,
            f"Evaluated provenance and limitations across {len(records)} evidence records",
            {"evaluated_count": len(records)},
        )
        return {"evidence_records": records, "current_stage": stage}

    async def cross_check_claims(self, state: ResearchState) -> dict[str, Any]:
        if await self._check_cancelled(state):
            return {"cancel_requested": True, "current_stage": "cancelled", "final_status": "cancelled"}

        stage = "cross_check_claims"
        records = [dict(r) for r in state.get("evidence_records", [])]
        if len(records) < 2:
            await self._emit(
                state,
                "contradictions_found",
                stage,
                "Insufficient multi-source evidence for cross-checking",
                {"contradictions": []},
            )
            return {
                "identified_contradictions": [],
                "corroborated_claims": [],
                "current_stage": stage,
            }

        prompt = build_cross_check_prompt(state["original_question"], records[:30])
        res = await self.llm.generate_json(SYSTEM_ANALYST_PROMPT, prompt)
        contradictions = res.get("contradictions", [])
        corroborated = [str(c) for c in res.get("corroborated_claims", [])]

        # Mark corroborated items transparently if corroborated claims mention key terms
        for rec in records:
            if rec.get("evidence_type") in {"primary", "academic", "government"} and len(
                {r["source_ref"] for r in records}
            ) > 1:
                if any(
                    word in rec["claim"].lower()
                    for claim_text in corroborated
                    for word in claim_text.lower().split()
                    if len(word) > 5
                ):
                    rec["corroboration_status"] = "corroborated"

        await self._emit(
            state,
            "contradictions_found",
            stage,
            f"Identified {len(contradictions)} cross-source contradictions/discrepancies",
            {"contradictions": contradictions},
        )
        return {
            "evidence_records": records,
            "identified_contradictions": contradictions,
            "corroborated_claims": corroborated,
            "current_stage": stage,
        }

    async def identify_research_gaps(self, state: ResearchState) -> dict[str, Any]:
        stage = "identify_research_gaps"
        iteration = int(state.get("retry_count", 0))
        max_iterations = int(state.get("max_iterations", self.settings.MAX_SEARCH_ITERATIONS))

        prompt = build_gaps_prompt(
            state["original_question"],
            state.get("subquestions", []),
            len(state.get("evidence_records", [])),
            state.get("identified_contradictions", []),
            iteration,
            max_iterations,
        )
        res = await self.llm.generate_json(SYSTEM_ANALYST_PROMPT, prompt)
        gaps = [str(g) for g in res.get("gaps", []) if str(g).strip()]
        follow_up_queries = [str(q) for q in res.get("follow_up_queries", []) if str(q).strip()]
        has_critical_gaps = bool(res.get("has_critical_gaps", False))

        should_retry = (
            has_critical_gaps
            and bool(follow_up_queries)
            and iteration < max_iterations
            and not await self._check_cancelled(state)
        )
        next_retry = iteration + 1 if should_retry else iteration

        await self._emit(
            state,
            "stage_completed",
            stage,
            f"Identified {len(gaps)} research gaps"
            + (" (scheduling targeted follow-up search)" if should_retry else ""),
            {"gaps": gaps, "retrying": should_retry},
        )
        return {
            "research_gaps": gaps,
            "follow_up_queries": follow_up_queries if should_retry else [],
            "retry_count": next_retry,
            "current_stage": stage,
        }

    async def generate_report(self, state: ResearchState) -> dict[str, Any]:
        if await self._check_cancelled(state):
            return {"cancel_requested": True, "current_stage": "cancelled", "final_status": "cancelled"}

        stage = "generate_report"
        await self._emit(state, "stage_started", stage, "Synthesizing cited research report", None)

        docs = list(state.get("extracted_documents", []))
        evidence = list(state.get("evidence_records", []))
        contradictions = list(state.get("identified_contradictions", []))
        gaps = list(state.get("research_gaps", []))
        validation = state.get("citation_validation", {})
        validation_errors = validation.get("errors") if validation and not validation.get("is_valid", True) else None

        prompt = build_generate_report_prompt(
            question=state["original_question"],
            context=state.get("research_context", ""),
            language=state.get("language", "en"),
            sources_catalog=docs,
            evidence_records=evidence,
            contradictions=contradictions,
            gaps=gaps,
            validation_errors=validation_errors,
        )
        report_payload = await self.llm.generate_json(
            SYSTEM_ANALYST_PROMPT, prompt, temperature=0.15, max_tokens=6000
        )

        # Build structured analytics data for UI & Recharts visualizations
        source_type_counts = Counter(d.get("source_type", "company") for d in docs)
        claim_category_counts = Counter(e.get("claim_category", "source_reported_claim") for e in evidence)
        extraction_status_counts = Counter(d.get("extraction_status", "pending") for d in docs)

        structured_data = {
            "key_findings": report_payload.get("key_findings", []),
            "contradictions": contradictions,
            "research_gaps": gaps,
            "subquestions": state.get("subquestions", []),
            "analytics": {
                "source_types": [
                    {"name": k, "count": v} for k, v in source_type_counts.items()
                ],
                "claim_categories": [
                    {"name": k, "count": v} for k, v in claim_category_counts.items()
                ],
                "extraction_statuses": [
                    {"name": k, "count": v} for k, v in extraction_status_counts.items()
                ],
            },
        }

        generated_report = {
            "title": str(report_payload.get("title") or f"Research Report: {state['original_question'][:80]}"),
            "summary": str(report_payload.get("summary") or ""),
            "content": str(report_payload.get("markdown_report") or ""),
            "structured_data": structured_data,
        }
        await self._emit(state, "report_generated", stage, "Draft research report generated", None)
        return {"generated_report": generated_report, "current_stage": stage}

    async def validate_citations(self, state: ResearchState) -> dict[str, Any]:
        stage = "validate_citations"
        docs = list(state.get("extracted_documents", []))
        evidence = list(state.get("evidence_records", []))
        report = dict(state.get("generated_report", {}))

        evidence_by_source: dict[int, str] = {}
        for ev in evidence:
            ref = int(ev.get("source_ref", 0))
            if ref and ref not in evidence_by_source:
                evidence_by_source[ref] = ev.get("claim", "")

        sources_by_num: dict[int, dict[str, Any]] = {}
        for doc in docs:
            num = int(doc["citation_number"])
            enriched = dict(doc)
            enriched["supporting_claim"] = evidence_by_source.get(num, doc.get("raw_excerpt", ""))
            sources_by_num[num] = enriched

        validation_result, final_markdown = validate_report_citations(
            report.get("content", ""),
            sources_by_num,
        )
        report["content"] = final_markdown
        attempts = int(state.get("citation_fix_attempts", 0))

        if not validation_result.is_valid and attempts < 1:
            await self._emit(
                state,
                "stage_completed",
                stage,
                "Citation validation flagged issues; attempting automatic citation repair",
                validation_result.to_dict(),
            )
            return {
                "generated_report": report,
                "citation_validation": validation_result.to_dict(),
                "current_stage": stage,
            }

        await self._emit(
            state,
            "citations_validated",
            stage,
            "Citations validated against collected sources"
            if validation_result.is_valid
            else "Citation validation completed with warnings",
            validation_result.to_dict(),
        )
        return {
            "generated_report": report,
            "citation_validation": validation_result.to_dict(),
            "current_stage": stage,
        }

    async def save_research_results(self, state: ResearchState) -> dict[str, Any]:
        stage = "save_research_results"
        final_status = "cancelled" if state.get("cancel_requested") else "completed"
        return {"current_stage": stage, "final_status": final_status}
