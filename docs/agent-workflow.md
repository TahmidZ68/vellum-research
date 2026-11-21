# Agent Workflow — LangGraph Pipeline

Rather than using unconstrained autonomous loops, Vellum Research executes a controlled 14-node LangGraph workflow:

```
START
  -> understand_question
  -> create_research_plan
  -> generate_search_queries
  -> search_web
  -> deduplicate_sources
  -> rank_sources
  -> extract_source_content
  -> extract_evidence
  -> evaluate_evidence
  -> cross_check_claims
  -> identify_research_gaps
       |-- (critical gaps & retry_count < MAX_SEARCH_ITERATIONS) --> generate_search_queries
       |-- (otherwise) --> generate_report
  -> validate_citations
       |-- (invalid & citation_fix_attempts < 1) --> generate_report
       |-- (otherwise) --> save_research_results
  -> END
```

## Depth Presets

| Depth | Subquestions | Max Selected Sources |
| --- | --- | --- |
| `quick` | Up to 3 | Up to 5 |
| `standard` | Up to 5 | Up to 12 |
| `deep` | Up to 8 | Up to 25 |

Limits are configurable via environment variables (`DEPTH_QUICK_*`, `DEPTH_STANDARD_*`, `DEPTH_DEEP_*`).

## Citation Validation

`validate_report_citations` checks:
1. Every `[n]` inline reference corresponds to an actual collected source for that run.
2. No ungrounded external URLs appear in the body outside collected sources.
3. A deterministic `## References` section is generated directly from verified source metadata.
