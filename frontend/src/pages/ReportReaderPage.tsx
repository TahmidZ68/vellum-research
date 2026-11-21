import React, { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  BookOpen,
  Download,
  ExternalLink,
  Library,
  MessageSquarePlus,
  Scale,
  Send,
  ShieldCheck,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, ApiError } from "@/services/api";
import { formatDate, slugifyHeading } from "@/lib/utils";
import { MarkdownReport } from "@/components/reports/MarkdownReport";
import { StatusBadge } from "@/components/research/StatusBadge";
import { Badge, Button, Card, Input } from "@/components/ui/primitives";

export function ReportReaderPage() {
  const { runId = "" } = useParams();
  const queryClient = useQueryClient();
  const [selectedCitationNum, setSelectedCitationNum] = useState<number | null>(null);
  const [followUpInput, setFollowUpInput] = useState("");
  const [exportError, setExportError] = useState("");

  const runQuery = useQuery({
    queryKey: ["research-run", runId],
    queryFn: () => api.getResearchRun(runId),
    enabled: Boolean(runId),
  });

  const reportQuery = useQuery({
    queryKey: ["research-report", runId],
    queryFn: () => api.getResearchReport(runId),
    enabled: Boolean(runId),
  });

  const messagesQuery = useQuery({
    queryKey: ["research-messages", runId],
    queryFn: () => api.getResearchMessages(runId),
    enabled: Boolean(runId),
  });

  const followUpMutation = useMutation({
    mutationFn: (question: string) => api.askFollowUp(runId, question),
    onSuccess: () => {
      setFollowUpInput("");
      void queryClient.invalidateQueries({ queryKey: ["research-messages", runId] });
    },
  });

  const report = reportQuery.data;
  const run = runQuery.data;

  const tocItems = useMemo(() => {
    if (!report?.content) return [];
    return report.content
      .split("\n")
      .filter((line) => line.startsWith("## "))
      .map((line) => {
        const text = line.replace(/^##\s+/, "").trim();
        return { text, id: slugifyHeading(text) };
      });
  }, [report?.content]);

  const activeCitation = useMemo(() => {
    if (!report?.citations?.length) return null;
    if (selectedCitationNum !== null) {
      return report.citations.find((c) => c.citation_number === selectedCitationNum) || null;
    }
    return report.citations[0];
  }, [report?.citations, selectedCitationNum]);

  const handleExport = async (format: "markdown" | "pdf") => {
    setExportError("");
    try {
      await api.downloadExport(runId, format);
    } catch (err) {
      setExportError(err instanceof ApiError ? err.detail : "Export failed.");
    }
  };

  const handleFollowUpSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (followUpInput.trim().length < 2) return;
    followUpMutation.mutate(followUpInput.trim());
  };

  if (reportQuery.isLoading || runQuery.isLoading) {
    return (
      <Card className="p-8 text-center text-sm text-muted-foreground">
        Loading research report and evidence workspace...
      </Card>
    );
  }

  if (reportQuery.isError || !report) {
    return (
      <Card className="p-6 space-y-3 border-destructive/40 bg-destructive/10">
        <p className="text-sm font-semibold text-rose-300">Report not available yet</p>
        <p className="text-xs text-muted-foreground">
          This investigation may still be running or failed before report synthesis.
        </p>
        <Link to={`/research/${runId}`}>
          <Button variant="outline" size="sm">
            Return to Live Research Workspace
          </Button>
        </Link>
      </Card>
    );
  }

  const sourceAnalytics = report.structured_data?.analytics?.source_types || [];
  const claimAnalytics = report.structured_data?.analytics?.claim_categories || [];
  const contradictions = report.structured_data?.contradictions || [];

  return (
    <div className="space-y-6">
      {/* Top Action Bar */}
      <Card className="p-5 space-y-4">
        <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4">
          <div className="space-y-2">
            <div className="flex items-center gap-2 flex-wrap">
              <StatusBadge status={report.status} />
              <Badge tone="neutral">v{report.version}</Badge>
              {run?.is_demo_mode && <Badge tone="warning">Demo Sample Data</Badge>}
              <span className="text-xs text-muted-foreground">
                {report.citations.length} cited sources · {formatDate(report.created_at)}
              </span>
            </div>
            <h1 className="text-2xl font-bold tracking-tight">{report.title}</h1>
            {report.summary && (
              <p className="text-sm text-muted-foreground leading-relaxed max-w-3xl">
                {report.summary}
              </p>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-2 shrink-0">
            <Link to={`/research/${runId}/sources`}>
              <Button variant="outline" size="sm">
                <Library className="h-4 w-4" />
                Source Library
              </Button>
            </Link>
            <Button variant="outline" size="sm" onClick={() => handleExport("markdown")}>
              <Download className="h-4 w-4" />
              Export Markdown
            </Button>
            <Button size="sm" onClick={() => handleExport("pdf")}>
              <Download className="h-4 w-4" />
              Export PDF
            </Button>
          </div>
        </div>

        {exportError && (
          <p className="text-xs text-rose-400">{exportError}</p>
        )}

        {!report.citation_validation?.is_valid && (
          <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-xs flex items-start gap-2.5">
            <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-amber-300">Citation Validation Warning</p>
              <ul className="list-disc pl-4 mt-1 text-muted-foreground">
                {(report.citation_validation?.errors || []).map((err, i) => (
                  <li key={i}>{err}</li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </Card>

      {/* Main 3-column Research Reader Layout */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6 items-start">
        {/* Left: Sticky Table of Contents */}
        <aside className="hidden xl:block xl:col-span-2 sticky top-6">
          <Card className="p-4 space-y-3">
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Contents
            </p>
            <nav className="space-y-1.5">
              {tocItems.map((item) => (
                <a
                  key={item.id}
                  href={`#${item.id}`}
                  className="block text-xs text-muted-foreground hover:text-primary transition-colors py-0.5 truncate"
                >
                  {item.text}
                </a>
              ))}
            </nav>
          </Card>
        </aside>

        {/* Center: Report Body + Charts + Contradictions + Follow-up */}
        <div className="xl:col-span-7 space-y-6">
          {/* Analytics Charts */}
          {(sourceAnalytics.length > 0 || claimAnalytics.length > 0) && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {sourceAnalytics.length > 0 && (
                <Card className="p-4 space-y-2">
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    Source Types Collected
                  </p>
                  <div className="h-44 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={sourceAnalytics}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.15)" />
                        <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                        <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                        <Tooltip />
                        <Bar dataKey="count" fill="#6366f1" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </Card>
              )}

              {claimAnalytics.length > 0 && (
                <Card className="p-4 space-y-2">
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    Evidence Classification
                  </p>
                  <div className="h-44 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={claimAnalytics}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.15)" />
                        <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                        <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                        <Tooltip />
                        <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </Card>
              )}
            </div>
          )}

          {/* Markdown Report */}
          <Card className="p-6 sm:p-8">
            <MarkdownReport
              content={report.content}
              onSelectCitation={(num) => setSelectedCitationNum(num)}
              activeCitation={activeCitation?.citation_number ?? null}
            />
          </Card>

          {/* Structured Contradictions & Disagreements */}
          {contradictions.length > 0 && (
            <Card className="p-6 space-y-4">
              <div className="flex items-center gap-2">
                <Scale className="h-4 w-4 text-amber-400" />
                <h2 className="text-base font-semibold">Contradictions & Disagreements</h2>
              </div>
              <div className="space-y-3">
                {contradictions.map((c, idx) => (
                  <div key={idx} className="rounded-lg border bg-background p-4 space-y-2 text-xs">
                    <div className="flex items-center justify-between gap-2 flex-wrap">
                      <span className="font-semibold text-sm text-foreground">{c.topic}</span>
                      <Badge tone="warning">{c.classification}</Badge>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                      <div className="rounded border p-2.5 bg-card">
                        <p className="font-semibold text-muted-foreground mb-1">Position A</p>
                        <p>{c.claim_a}</p>
                      </div>
                      <div className="rounded border p-2.5 bg-card">
                        <p className="font-semibold text-muted-foreground mb-1">Position B</p>
                        <p>{c.claim_b}</p>
                      </div>
                    </div>
                    <p className="text-muted-foreground pt-1">{c.explanation}</p>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Follow-up Q&A */}
          <Card className="p-6 space-y-4">
            <div className="flex items-center gap-2">
              <MessageSquarePlus className="h-4 w-4 text-primary" />
              <h2 className="text-base font-semibold">Ask Follow-Up Questions</h2>
            </div>
            <p className="text-xs text-muted-foreground">
              Answers are grounded strictly in the sources and evidence collected during this run.
            </p>

            {(messagesQuery.data || []).length > 0 && (
              <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
                {(messagesQuery.data || []).map((msg) => (
                  <div
                    key={msg.id}
                    className={`rounded-lg border p-3.5 text-sm ${
                      msg.role === "user" ? "bg-primary/10 border-primary/25" : "bg-background"
                    }`}
                  >
                    <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground mb-1">
                      {msg.role === "user" ? "Your Question" : "Analyst Response"}
                    </p>
                    <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                  </div>
                ))}
              </div>
            )}

            <form onSubmit={handleFollowUpSubmit} className="flex gap-2.5">
              <Input
                value={followUpInput}
                onChange={(e) => setFollowUpInput(e.target.value)}
                placeholder="Ask a follow-up question about this investigation..."
                disabled={followUpMutation.isPending}
              />
              <Button type="submit" disabled={followUpMutation.isPending || !followUpInput.trim()}>
                <Send className="h-4 w-4" />
                {followUpMutation.isPending ? "Answering..." : "Ask"}
              </Button>
            </form>
          </Card>
        </div>

        {/* Right: Citation & Evidence Inspector */}
        <aside className="xl:col-span-3 sticky top-6 space-y-4">
          <Card className="p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-primary" />
                <h2 className="font-semibold text-sm">Citation Inspector</h2>
              </div>
              {activeCitation && (
                <Badge tone="primary">[{activeCitation.citation_number}]</Badge>
              )}
            </div>

            {report.citations.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {report.citations.map((c) => (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => setSelectedCitationNum(c.citation_number)}
                    className={`px-2 py-1 rounded text-xs font-mono border transition-colors ${
                      activeCitation?.citation_number === c.citation_number
                        ? "bg-primary text-primary-foreground border-primary"
                        : "bg-background hover:bg-muted"
                    }`}
                  >
                    [{c.citation_number}]
                  </button>
                ))}
              </div>
            )}

            {activeCitation?.source ? (
              <div className="space-y-3 text-xs border-t pt-3">
                <div>
                  <p className="font-semibold text-sm text-foreground">
                    {activeCitation.source.title}
                  </p>
                  <p className="text-muted-foreground mt-0.5">
                    {activeCitation.source.publisher}
                    {activeCitation.source.author ? ` · ${activeCitation.source.author}` : ""}
                  </p>
                </div>

                <div className="flex flex-wrap gap-1.5">
                  <Badge tone="neutral">{activeCitation.source.source_type}</Badge>
                  <Badge tone="neutral">
                    Published: {activeCitation.source.published_at || "Unknown"}
                  </Badge>
                </div>

                {activeCitation.cited_claim && (
                  <div className="rounded-lg border bg-background p-3 space-y-1">
                    <p className="font-semibold text-[11px] uppercase tracking-wider text-muted-foreground">
                      Linked Claim
                    </p>
                    <p className="text-foreground leading-relaxed">{activeCitation.cited_claim}</p>
                  </div>
                )}

                {(activeCitation.evidence?.excerpt || activeCitation.source.raw_excerpt) && (
                  <div className="rounded-lg border bg-background p-3 space-y-1">
                    <p className="font-semibold text-[11px] uppercase tracking-wider text-muted-foreground">
                      Source Excerpt
                    </p>
                    <p className="text-muted-foreground leading-relaxed italic">
                      “{activeCitation.evidence?.excerpt || activeCitation.source.raw_excerpt}”
                    </p>
                  </div>
                )}

                {activeCitation.source.limitations && (
                  <div className="text-[11px] text-muted-foreground">
                    <span className="font-semibold text-foreground">Limitations:</span>{" "}
                    {activeCitation.source.limitations}
                  </div>
                )}

                <a
                  href={activeCitation.source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-primary hover:underline font-medium pt-1"
                >
                  Open original source
                  <ExternalLink className="h-3.5 w-3.5" />
                </a>
              </div>
            ) : (
              <div className="text-xs text-muted-foreground flex items-center gap-2 py-4">
                <BookOpen className="h-4 w-4" />
                Click any inline citation [n] in the report to inspect its source evidence.
              </div>
            )}
          </Card>
        </aside>
      </div>
    </div>
  );
}
