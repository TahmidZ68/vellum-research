import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  Circle,
  ExternalLink,
  FileText,
  Library,
  Loader2,
  StopCircle,
} from "lucide-react";
import { api } from "@/services/api";
import type { ResearchProgressEvent } from "@/types/api";
import { Badge, Button, Card } from "@/components/ui/primitives";
import { StatusBadge } from "@/components/research/StatusBadge";

const STAGES = [
  { id: "understand_question", label: "Understand Question" },
  { id: "create_research_plan", label: "Research Plan" },
  { id: "generate_search_queries", label: "Search Strategy" },
  { id: "search_web", label: "Web Discovery" },
  { id: "deduplicate_sources", label: "Deduplicate URLs" },
  { id: "rank_sources", label: "Rank Sources" },
  { id: "extract_source_content", label: "Extract Pages" },
  { id: "extract_evidence", label: "Collect Evidence" },
  { id: "evaluate_evidence", label: "Assess Provenance" },
  { id: "cross_check_claims", label: "Cross-Check Claims" },
  { id: "identify_research_gaps", label: "Gap Check" },
  { id: "generate_report", label: "Synthesize Report" },
  { id: "validate_citations", label: "Validate Citations" },
  { id: "completed", label: "Complete" },
];

export function LiveResearchPage() {
  const { runId = "" } = useParams();
  const queryClient = useQueryClient();
  const [events, setEvents] = useState<ResearchProgressEvent[]>([]);
  const [discoveredSources, setDiscoveredSources] = useState<
    Array<{ citation_number?: number; title: string; url: string; extraction_status?: string }>
  >([]);

  const runQuery = useQuery({
    queryKey: ["research-run", runId],
    queryFn: () => api.getResearchRun(runId),
    enabled: Boolean(runId),
    refetchInterval: (q) => {
      const status = q.state.data?.status;
      return status === "queued" || status === "running" ? 2500 : false;
    },
  });

  const cancelMutation = useMutation({
    mutationFn: () => api.cancelResearchRun(runId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["research-run", runId] });
    },
  });

  useEffect(() => {
    if (!runId) return;
    const url = api.getEventsStreamUrl(runId);
    const source = new EventSource(url);

    const handleEvent = (rawEvent: MessageEvent) => {
      try {
        const parsed = JSON.parse(rawEvent.data) as ResearchProgressEvent;
        setEvents((prev) => {
          if (
            prev.some(
              (p) => p.timestamp === parsed.timestamp && p.event === parsed.event && p.stage === parsed.stage
            )
          ) {
            return prev;
          }
          return [...prev, parsed];
        });

        if (parsed.event === "stage_completed" && parsed.data?.selected_sources) {
          setDiscoveredSources(
            parsed.data.selected_sources as Array<{
              citation_number?: number;
              title: string;
              url: string;
            }>
          );
        }

        if (parsed.event === "source_extracted" && parsed.data?.url) {
          setDiscoveredSources((prev) => {
            const urlStr = String(parsed.data.url);
            const idx = prev.findIndex((s) => s.url === urlStr);
            const updated = {
              citation_number: Number(parsed.data.citation_number || 0),
              title: String(parsed.data.title || urlStr),
              url: urlStr,
              extraction_status: String(parsed.data.extraction_status || "extracted"),
            };
            if (idx >= 0) {
              const copy = [...prev];
              copy[idx] = updated;
              return copy;
            }
            return [...prev, updated];
          });
        }

        if (
          parsed.event === "run_completed" ||
          parsed.event === "run_failed" ||
          parsed.event === "run_cancelled" ||
          parsed.event === "plan_created"
        ) {
          void queryClient.invalidateQueries({ queryKey: ["research-run", runId] });
        }
      } catch {
        // ignore malformed keepalive packets
      }
    };

    const eventNames = [
      "run_queued",
      "stage_started",
      "stage_completed",
      "plan_created",
      "queries_generated",
      "sources_discovered",
      "source_extracted",
      "evidence_extracted",
      "contradictions_found",
      "report_generated",
      "citations_validated",
      "run_completed",
      "run_failed",
      "run_cancelled",
      "progress",
    ];
    eventNames.forEach((name) => source.addEventListener(name, handleEvent as EventListener));
    source.onmessage = handleEvent;

    return () => {
      source.close();
    };
  }, [runId, queryClient]);

  if (runQuery.isLoading) {
    return <Card className="p-8 text-center text-sm text-muted-foreground">Loading research run...</Card>;
  }

  if (runQuery.isError || !runQuery.data) {
    return (
      <Card className="p-6 border-destructive/40 bg-destructive/10 text-sm text-rose-300">
        Research run not found or inaccessible.
      </Card>
    );
  }

  const run = runQuery.data;
  const activeStageIdx = STAGES.findIndex((s) => s.id === run.current_stage);
  const isRunning = run.status === "queued" || run.status === "running";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div className="space-y-1.5">
          <div className="flex items-center gap-2 flex-wrap">
            <StatusBadge status={run.status} />
            <Badge tone="neutral">{run.depth}</Badge>
            {run.is_demo_mode && <Badge tone="warning">Demo Sample Mode</Badge>}
            <span className="text-xs font-mono text-muted-foreground">
              Stage: {run.current_stage}
            </span>
          </div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight">{run.query}</h1>
        </div>

        <div className="flex items-center gap-2.5 shrink-0">
          {isRunning && (
            <Button
              variant="destructive"
              size="sm"
              onClick={() => cancelMutation.mutate()}
              disabled={cancelMutation.isPending || run.cancel_requested}
            >
              <StopCircle className="h-4 w-4" />
              {run.cancel_requested ? "Cancelling..." : "Cancel Run"}
            </Button>
          )}
          <Link to={`/research/${run.id}/sources`}>
            <Button variant="outline" size="sm">
              <Library className="h-4 w-4" />
              Sources ({run.source_count || discoveredSources.length})
            </Button>
          </Link>
          {run.has_report && (
            <Link to={`/research/${run.id}/report`}>
              <Button size="sm">
                <FileText className="h-4 w-4" />
                Open Report Reader
                <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
          )}
        </div>
      </div>

      {run.status === "failed" && (
        <Card className="p-4 border-destructive/40 bg-destructive/10 flex items-start gap-3">
          <AlertCircle className="h-5 w-5 text-rose-400 shrink-0 mt-0.5" />
          <div className="space-y-1 text-sm">
            <p className="font-semibold text-rose-300">Research Execution Failed</p>
            <p className="text-muted-foreground">{run.error_message || "Unknown error occurred."}</p>
          </div>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Stage Progress */}
        <Card className="p-5 space-y-4">
          <h2 className="font-semibold text-sm">Workflow Stages</h2>
          <ol className="space-y-2.5">
            {STAGES.map((stage, index) => {
              const completed =
                run.status === "completed" || (activeStageIdx > index && activeStageIdx !== -1);
              const current = isRunning && run.current_stage === stage.id;
              return (
                <li key={stage.id} className="flex items-center gap-2.5 text-xs">
                  {completed ? (
                    <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
                  ) : current ? (
                    <Loader2 className="h-4 w-4 text-primary animate-spin shrink-0" />
                  ) : (
                    <Circle className="h-4 w-4 text-muted-foreground/40 shrink-0" />
                  )}
                  <span
                    className={
                      current
                        ? "font-semibold text-primary"
                        : completed
                        ? "text-foreground"
                        : "text-muted-foreground"
                    }
                  >
                    {stage.label}
                  </span>
                </li>
              );
            })}
          </ol>
        </Card>

        {/* Plan, Sources & Real-Time Event Log */}
        <div className="lg:col-span-2 space-y-6">
          {run.plan && (
            <Card className="p-5 space-y-3">
              <h2 className="font-semibold text-sm">Generated Research Plan</h2>
              <p className="text-xs text-muted-foreground">{run.plan.objective}</p>
              <ul className="space-y-2 pt-1">
                {run.plan.subquestions.map((sq, i) => (
                  <li key={sq.id || i} className="text-xs rounded-lg border bg-background p-2.5">
                    <span className="font-mono text-primary mr-2">Q{i + 1}.</span>
                    {sq.question}
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {discoveredSources.length > 0 && (
            <Card className="p-5 space-y-3">
              <h2 className="font-semibold text-sm">
                Selected & Extracted Sources ({discoveredSources.length})
              </h2>
              <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                {discoveredSources.map((src) => (
                  <div
                    key={src.url}
                    className="flex items-center justify-between gap-3 rounded-lg border bg-background p-2.5 text-xs"
                  >
                    <div className="min-w-0">
                      <p className="font-medium truncate">
                        {src.citation_number ? `[${src.citation_number}] ` : ""}
                        {src.title}
                      </p>
                      <p className="text-muted-foreground truncate">{src.url}</p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      {src.extraction_status && <StatusBadge status={src.extraction_status} />}
                      <a
                        href={src.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-muted-foreground hover:text-foreground"
                      >
                        <ExternalLink className="h-3.5 w-3.5" />
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          <Card className="p-5 space-y-3">
            <h2 className="font-semibold text-sm">Live Backend Event Stream</h2>
            {events.length === 0 ? (
              <p className="text-xs text-muted-foreground">
                Waiting for pipeline events...
              </p>
            ) : (
              <div className="space-y-2 max-h-72 overflow-y-auto font-mono text-xs">
                {events.map((ev, idx) => (
                  <div
                    key={`${ev.timestamp}-${idx}`}
                    className="rounded border bg-background px-3 py-2 flex items-start justify-between gap-3"
                  >
                    <div>
                      <span className="text-primary">[{ev.stage}]</span>{" "}
                      <span className="text-foreground">{ev.message}</span>
                    </div>
                    <span className="text-[11px] text-muted-foreground shrink-0">
                      {new Date(ev.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
