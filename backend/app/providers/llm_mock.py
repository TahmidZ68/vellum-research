import re
from typing import Any

from app.providers.base import BaseLLMProvider


class MockLLMProvider(BaseLLMProvider):
    """
    Deterministic mock LLM provider for automated testing and clearly-labeled demo runs.
    Generates structured analytical outputs grounded strictly in the provided source IDs.
    """

    provider_name = "mock"
    model_name = "mock-analyst-v1"

    @staticmethod
    def _extract_source_ids(user_prompt: str) -> list[str]:
        return re.findall(r"SOURCE_REF:\s*\[(\d+)\]", user_prompt)

    @staticmethod
    def _extract_question(user_prompt: str) -> str:
        match = re.search(r"Question:\s*(.+)", user_prompt)
        return match.group(1).strip() if match else "Research Investigation"

    async def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> str:
        if "TASK:follow_up" in user_prompt:
            refs = self._extract_source_ids(user_prompt)
            cite = f"[{refs[0]}]" if refs else "[Unverified]"
            return (
                "**[DEMO / SAMPLE DATA]** Based on the collected sources in this run, "
                f"available evidence indicates measurable enterprise adoption alongside cost and integration constraints {cite}. "
                "Claims beyond the extracted excerpts cannot be verified from the current source library."
            )
        return "[DEMO / SAMPLE DATA] Mock analysis response."

    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        question = self._extract_question(user_prompt)

        if "TASK:understand_question" in user_prompt:
            return {
                "topic": question[:120],
                "objective": f"Investigate {question} using verifiable evidence and source cross-checking.",
                "scope": "Primary documentation, industry reporting, empirical studies, and institutional briefs.",
                "location": "Global / Regional where specified",
                "time_period": "Recent 2024–2026 evidence prioritized",
                "expected_format": "Structured analytical research report with inline citations",
            }

        if "TASK:create_research_plan" in user_prompt:
            max_sq = 4
            m = re.search(r"Target subquestions:\s*(\d+)", user_prompt)
            if m:
                max_sq = max(2, min(int(m.group(1)), 8))
            base_subquestions = [
                {
                    "id": "sq-1",
                    "question": f"What are the primary market/technical drivers and adoption patterns in {question[:60]}?",
                    "angle": "adoption_and_scale",
                },
                {
                    "id": "sq-2",
                    "question": f"Who are the key participants, models, or frameworks in {question[:60]}?",
                    "angle": "landscape_and_models",
                },
                {
                    "id": "sq-3",
                    "question": f"What empirical limitations, pricing structures, or contradictions exist around {question[:60]}?",
                    "angle": "economics_and_limitations",
                },
                {
                    "id": "sq-4",
                    "question": f"What regulatory, infrastructural, or strategic opportunities remain unaddressed in {question[:60]}?",
                    "angle": "gaps_and_opportunities",
                },
                {
                    "id": "sq-5",
                    "question": f"How do independent benchmarks compare against commercial claims for {question[:60]}?",
                    "angle": "verification_and_benchmarks",
                },
                {
                    "id": "sq-6",
                    "question": f"What deployment risks and implementation barriers are documented for {question[:60]}?",
                    "angle": "risks_and_barriers",
                },
            ]
            return {
                "subquestions": base_subquestions[:max_sq],
                "search_strategy": {
                    "perspectives": ["primary_docs", "independent_journalism", "academic_benchmarks", "institutional_data"],
                    "deduplication": "canonical_url_and_domain_diversity",
                },
            }

        if "TASK:generate_search_queries" in user_prompt:
            return {
                "queries": [
                    f"{question[:80]} industry adoption report 2025 2026",
                    f"{question[:80]} pricing models competitors comparison",
                    f"{question[:80]} empirical benchmark limitations study",
                    f"{question[:80]} regulatory readiness challenges",
                ]
            }

        if "TASK:extract_evidence" in user_prompt:
            refs = self._extract_source_ids(user_prompt)
            ref = refs[0] if refs else "1"
            return {
                "evidence": [
                    {
                        "source_ref": int(ref),
                        "claim": "Enterprise adoption has grown steadily while small-business data remains sparse.",
                        "excerpt": "42% enterprise workflow automation adoption in 2025, while noting limited survey coverage among small businesses.",
                        "evidence_type": "primary",
                        "claim_category": "source_reported_claim",
                        "relevance": "high",
                        "date_context": "2025–2026",
                        "limitations": "Survey sample skewed toward mid-to-large organizations.",
                    },
                    {
                        "source_ref": int(ref),
                        "claim": "Controlled pilot efficiency gains (~28%) are lower than aggressive vendor marketing figures (up to 70%).",
                        "excerpt": "Empirical benchmark showing 28% efficiency gains in controlled pilots, contradicting vendor claims of 70% immediate cost reduction.",
                        "evidence_type": "academic",
                        "claim_category": "verified_fact",
                        "relevance": "high",
                        "date_context": "2026",
                        "limitations": "Controlled pilot setting may differ from full production rollouts.",
                    },
                ]
            }

        if "TASK:cross_check_claims" in user_prompt:
            refs = self._extract_source_ids(user_prompt)
            r1 = int(refs[0]) if len(refs) >= 1 else 1
            r2 = int(refs[1]) if len(refs) >= 2 else r1
            return {
                "contradictions": [
                    {
                        "topic": "Magnitude of operational cost reduction",
                        "claim_a": f"Controlled academic pilots report ~28% efficiency gains [{r1}].",
                        "claim_b": f"Commercial promotional materials claim up to 70% immediate cost savings [{r2}].",
                        "classification": "difference_in_measurement",
                        "explanation": "Promotional case studies often omit integration overhead and baseline selection criteria, whereas academic benchmarks measure net controlled gains.",
                        "source_refs": sorted(list({r1, r2})),
                    }
                ],
                "corroborated_claims": [
                    "Adoption is concentrated in larger organizations while SMB adoption faces integration cost barriers."
                ],
            }

        if "TASK:identify_research_gaps" in user_prompt:
            return {
                "has_critical_gaps": False,
                "gaps": [
                    "Limited longitudinal data on small-business unit economics and retention beyond 12 months."
                ],
                "follow_up_queries": [],
            }

        if "TASK:generate_report" in user_prompt:
            refs = [int(r) for r in self._extract_source_ids(user_prompt)] or [1]
            c1 = refs[0]
            c2 = refs[1] if len(refs) > 1 else c1
            c3 = refs[2] if len(refs) > 2 else c1
            title = f"Research Report: {question[:90]}"
            markdown = f"""# {title}

> **Notice (Demo / Sample Mode):** This report was generated using deterministic sample providers for testing or demonstration. Replace `LLM_PROVIDER=mock` / `SEARCH_PROVIDER=mock` with live API credentials in `.env` for live web research.

## Executive Summary
Available evidence indicates steady enterprise workflow adoption alongside meaningful pricing variation and integration constraints [{c1}] [{c2}]. Independent benchmarks show more conservative efficiency gains than vendor marketing claims [{c3}], highlighting the importance of separating empirical pilots from promotional material.

## Research Question and Scope
- **Primary Question:** {question}
- **Scope:** Multi-angle synthesis across primary documentation, industry reporting, empirical benchmarks, and institutional briefs.

## Methodology
This investigation decomposed the primary question into focused subquestions, executed multi-query discovery, deduplicated canonical URLs, extracted readable content, evaluated evidence provenance, cross-checked claims for contradictions, and validated all inline citations against collected sources.

## Key Findings
1. **Verified Fact — Measured Pilot Gains vs. Vendor Claims:** Empirical pilot evaluations report approximately 28% efficiency improvements [{c3}], whereas commercial vendor pages advertise up to 70% cost reductions without disclosing baseline methodology [{c2}].
2. **Source-Reported Claim — Enterprise vs. SMB Adoption:** Industry documentation reports 42% adoption among larger organizations, while evidence regarding small-business adoption remains limited [{c1}].
3. **Source-Reported Claim — Pricing & Packaging Models:** Market analysis observes hybrid tiered subscriptions paired with custom implementation retainers [{c2}].
4. **Interpretation — Strategic Entry Wedge:** *Interpretation:* The gap between enterprise-focused custom retainers and underserved SMB requirements suggests an opportunity for standardized, transparent deployment packages, though this remains an analytical inference rather than a directly measured survey finding.

## Detailed Analysis
### Market Dynamics and Adoption
Enterprise deployments lead current adoption due to dedicated engineering budgets and compliance readiness [{c1}]. Smaller firms face upfront integration friction, creating a concentration of visible case studies in mid-to-large firms [{c2}].

### Pricing and Delivery Models
| Segment | Observed Model | Typical Structure | Evidence |
| --- | --- | --- | --- |
| Mid-Market / SMB | Tiered SaaS | Monthly subscription tiers | [{c2}] |
| Enterprise | Retainer + Platform | Custom integration + licensing | [{c1}] [{c2}] |

## Evidence Comparison
Primary and academic sources provide clearer methodological boundaries than commercial vendor pages [{c1}] [{c3}]. Where independent corroboration was unavailable, claims are explicitly attributed to their single reporting publisher [{c2}].

## Conflicting Findings
- **Cost-Reduction Discrepancy (Difference in Measurement):** Controlled pilot benchmarks report ~28% efficiency gains [{c3}], conflicting with commercial promotional claims of 70% cost reductions [{c2}]. The discrepancy reflects differences in measurement boundaries and undisclosed vendor sample selection rather than a direct factual impossibility.

## Research Limitations
- Sample coverage for small and micro-enterprises is thin across publicly indexed sources [{c1}].
- Promotional vendor materials frequently omit sample sizes and evaluation windows [{c2}].

## Conclusions
The evidence supports cautious optimism around measurable workflow efficiency gains [{c3}], tempered by clear disparities between vendor marketing claims and controlled evaluations [{c2}].

## Further Research Recommendations
1. Conduct primary pricing and retention interviews with SMB buyers to close the small-business evidence gap.
2. Track post-implementation total cost of ownership over 12–24 month windows.
"""
            return {
                "title": title,
                "summary": (
                    f"Synthesis of {len(refs)} collected sample sources examining {question[:100]}, "
                    "contrasting measured pilot outcomes with commercial claims."
                ),
                "markdown_report": markdown.strip(),
                "key_findings": [
                    f"Controlled pilot evaluations report ~28% efficiency gains [{c3}].",
                    f"Enterprise adoption leads (42% reported), while SMB data is sparse [{c1}].",
                    f"Pricing combines tiered subscriptions with custom retainers [{c2}].",
                ],
            }

        return {"status": "ok"}
