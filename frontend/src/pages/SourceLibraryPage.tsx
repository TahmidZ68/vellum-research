import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ExternalLink, FileText, Search } from "lucide-react";
import { api } from "@/services/api";
import { formatDate } from "@/lib/utils";
import { StatusBadge } from "@/components/research/StatusBadge";
import { Badge, Button, Card, Input } from "@/components/ui/primitives";

export function SourceLibraryPage() {
  const { runId = "" } = useParams();
  const [searchTerm, setSearchTerm] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");

  const sourcesQuery = useQuery({
    queryKey: ["research-sources", runId],
    queryFn: () => api.getResearchSources(runId),
    enabled: Boolean(runId),
  });

  const evidenceQuery = useQuery({
    queryKey: ["research-evidence", runId],
    queryFn: () => api.getResearchEvidence(runId),
    enabled: Boolean(runId),
  });

  const sources = sourcesQuery.data || [];
  const evidence = evidenceQuery.data || [];

  const evidenceBySourceId = useMemo(() => {
    const map = new Map<string, typeof evidence>();
    for (const ev of evidence) {
      const list = map.get(ev.source_id) || [];
      list.push(ev);
      map.set(ev.source_id, list);
    }
    return map;
  }, [evidence]);

  const filtered = useMemo(() => {
    return sources.filter((src) => {
      if (typeFilter !== "all" && src.source_type !== typeFilter) return false;
      if (statusFilter !== "all" && src.extraction_status !== statusFilter) return false;
      if (searchTerm.trim()) {
        const q = searchTerm.toLowerCase();
        return (
          src.title.toLowerCase().includes(q) ||
          src.publisher.toLowerCase().includes(q) ||
          src.url.toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [sources, typeFilter, statusFilter, searchTerm]);

  const sourceTypes = Array.from(new Set(sources.map((s) => s.source_type)));

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="space-y-1">
          <Link
            to={`/research/${runId}`}
            className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to Investigation
          </Link>
          <h1 className="text-2xl font-bold tracking-tight">Source Library</h1>
          <p className="text-sm text-muted-foreground">
            Browse extracted sources, provenance metadata, limitations, and linked claims.
          </p>
        </div>

        <Link to={`/research/${runId}/report`}>
          <Button size="sm">
            <FileText className="h-4 w-4" />
            Open Report
          </Button>
        </Link>
      </div>

      {/* Filters */}
      <Card className="p-4 flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="h-4 w-4 text-muted-foreground absolute left-3 top-3" />
          <Input
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Filter by title, publisher, or URL..."
            className="pl-9"
          />
        </div>
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="h-10 rounded-lg border bg-background px-3 text-sm"
        >
          <option value="all">All source types</option>
          {sourceTypes.map((st) => (
            <option key={st} value={st}>
              {st}
            </option>
          ))}
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="h-10 rounded-lg border bg-background px-3 text-sm"
        >
          <option value="all">All extraction statuses</option>
          <option value="extracted">extracted</option>
          <option value="failed">failed</option>
          <option value="pending">pending</option>
        </select>
      </Card>

      {sourcesQuery.isLoading ? (
        <Card className="p-8 text-center text-sm text-muted-foreground">Loading sources...</Card>
      ) : filtered.length === 0 ? (
        <Card className="p-8 text-center text-sm text-muted-foreground">
          No sources match the active filters.
        </Card>
      ) : (
        <div className="space-y-4">
          {filtered.map((src) => {
            const linkedEvidence = evidenceBySourceId.get(src.id) || [];
            return (
              <Card key={src.id} className="p-5 space-y-3">
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                  <div className="space-y-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <StatusBadge status={src.extraction_status} />
                      <Badge tone="neutral">{src.source_type}</Badge>
                      <Badge tone="primary">Relevance: {Math.round(src.relevance_score * 100)}%</Badge>
                    </div>
                    <h2 className="font-semibold text-base">{src.title}</h2>
                    <p className="text-xs text-muted-foreground">
                      {src.publisher}
                      {src.author ? ` · ${src.author}` : ""} · Published:{" "}
                      {src.published_at || "Unknown"} · Retrieved: {formatDate(src.retrieved_at)}
                    </p>
                  </div>
                  <a
                    href={src.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="shrink-0"
                  >
                    <Button variant="outline" size="sm">
                      <ExternalLink className="h-3.5 w-3.5" />
                      Open Original
                    </Button>
                  </a>
                </div>

                {src.relevance_note && (
                  <p className="text-xs text-muted-foreground">{src.relevance_note}</p>
                )}

                {src.limitations && (
                  <p className="text-xs text-amber-300/90">Limitations: {src.limitations}</p>
                )}

                {linkedEvidence.length > 0 && (
                  <div className="pt-2 border-t space-y-2">
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      Extracted Evidence ({linkedEvidence.length})
                    </p>
                    {linkedEvidence.map((ev) => (
                      <div key={ev.id} className="rounded-lg border bg-background p-3 text-xs space-y-1">
                        <div className="flex items-center gap-2">
                          <Badge tone="neutral">{ev.claim_category}</Badge>
                          <Badge tone="neutral">{ev.corroboration_status}</Badge>
                        </div>
                        <p className="font-medium text-foreground">{ev.claim}</p>
                        {ev.excerpt && (
                          <p className="text-muted-foreground italic">“{ev.excerpt}”</p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
