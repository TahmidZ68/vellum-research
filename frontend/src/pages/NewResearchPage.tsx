import React, { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Sparkles } from "lucide-react";
import { api, ApiError } from "@/services/api";
import { Badge, Button, Card, Input, Textarea } from "@/components/ui/primitives";

const DEPTH_OPTIONS = [
  {
    value: "quick" as const,
    label: "Quick",
    detail: "2–3 subquestions · up to 5 sources",
  },
  {
    value: "standard" as const,
    label: "Standard",
    detail: "4–6 subquestions · up to 12 sources",
  },
  {
    value: "deep" as const,
    label: "Deep",
    detail: "6–10 subquestions · up to 25 sources",
  },
];

const SOURCE_TYPES = [
  { id: "primary", label: "Primary Docs" },
  { id: "academic", label: "Academic" },
  { id: "government", label: "Government / Institutional" },
  { id: "journalism", label: "Journalism" },
  { id: "company", label: "Company Reports" },
];

export function NewResearchPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const preselectedProjectId = searchParams.get("projectId") || "";

  const [projectId, setProjectId] = useState(preselectedProjectId);
  const [projectTitle, setProjectTitle] = useState("");
  const [query, setQuery] = useState("");
  const [context, setContext] = useState("");
  const [depth, setDepth] = useState<"quick" | "standard" | "deep">("standard");
  const [dateRange, setDateRange] = useState("any");
  const [sourcePrefs, setSourcePrefs] = useState<string[]>([]);
  const [language, setLanguage] = useState<"en" | "bn">("en");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const projectsQuery = useQuery({
    queryKey: ["projects"],
    queryFn: () => api.listProjects(false),
  });

  const settingsQuery = useQuery({
    queryKey: ["settings-overview"],
    queryFn: () => api.getSettings(),
  });

  const toggleSourcePref = (id: string) => {
    setSourcePrefs((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (query.trim().length < 5) {
      setError("Please enter a research question of at least 5 characters.");
      return;
    }

    setSubmitting(true);
    try {
      const run = await api.startResearch({
        project_id: projectId || null,
        project_title: projectId ? undefined : projectTitle.trim() || undefined,
        query: query.trim(),
        context: context.trim(),
        depth,
        date_range: dateRange,
        source_preferences: sourcePrefs,
        language,
      });
      navigate(`/research/${run.id}`);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.detail
          : "Unable to start research run. Verify API configuration."
      );
    } finally {
      setSubmitting(false);
    }
  };

  const providers = settingsQuery.data?.providers;
  const missingCredentials =
    providers && (!providers.llm_configured || !providers.search_configured);

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">New Research Investigation</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Configure scope, depth, and source preferences. Every claim in the final report is linked
          to collected evidence.
        </p>
      </div>

      {providers?.is_demo_mode && (
        <Card className="p-4 border-amber-500/40 bg-amber-500/10 flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-amber-400 shrink-0 mt-0.5" />
          <div className="text-xs space-y-1">
            <p className="font-semibold text-amber-300">Demo / Sample Provider Mode Active</p>
            <p className="text-muted-foreground">
              Outputs will be clearly labeled as sample data. Configure{" "}
              <code>GEMINI_API_KEY</code> and <code>TAVILY_API_KEY</code> in <code>.env</code> for
              live web research.
            </p>
          </div>
        </Card>
      )}

      {missingCredentials && (
        <Card className="p-4 border-destructive/40 bg-destructive/10 flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-rose-400 shrink-0 mt-0.5" />
          <div className="text-xs space-y-1">
            <p className="font-semibold text-rose-300">Provider Credentials Missing</p>
            {providers.llm_guidance && <p className="text-muted-foreground">{providers.llm_guidance}</p>}
            {providers.search_guidance && (
              <p className="text-muted-foreground">{providers.search_guidance}</p>
            )}
          </div>
        </Card>
      )}

      {error && (
        <Card className="p-4 border-destructive/40 bg-destructive/10 text-sm text-rose-300">
          {error}
        </Card>
      )}

      <Card className="p-6">
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="space-y-2">
            <label htmlFor="research-question" className="text-sm font-medium">
              Research Question <span className="text-rose-400">*</span>
            </label>
            <Textarea
              id="research-question"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g., Research the current AI automation market in Bangladesh. Identify major competitors, common services, pricing models, customer segments, and opportunities for a new entrant."
              rows={3}
              required
            />
          </div>

          <div className="space-y-2">
            <label htmlFor="research-context" className="text-sm font-medium">
              Objectives & Additional Context (optional)
            </label>
            <Textarea
              id="research-context"
              value={context}
              onChange={(e) => setContext(e.target.value)}
              placeholder="Specify target audience, comparison criteria, geographic constraints, or questions to prioritize."
              rows={2}
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label htmlFor="project-select" className="text-sm font-medium">
                Workspace Project
              </label>
              <select
                id="project-select"
                value={projectId}
                onChange={(e) => setProjectId(e.target.value)}
                className="flex h-10 w-full rounded-lg border bg-background px-3 py-2 text-sm text-foreground"
              >
                <option value="">Create new project automatically</option>
                {(projectsQuery.data || []).map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.title}
                  </option>
                ))}
              </select>
            </div>

            {!projectId && (
              <div className="space-y-2">
                <label htmlFor="project-title" className="text-sm font-medium">
                  New Project Name (optional)
                </label>
                <Input
                  id="project-title"
                  value={projectTitle}
                  onChange={(e) => setProjectTitle(e.target.value)}
                  placeholder="Auto-generated from question if blank"
                />
              </div>
            )}
          </div>

          {/* Research Depth */}
          <div className="space-y-2">
            <span className="text-sm font-medium block">Research Depth</span>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {DEPTH_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setDepth(opt.value)}
                  className={`text-left p-3.5 rounded-xl border transition-colors ${
                    depth === opt.value
                      ? "border-primary bg-primary/10"
                      : "bg-background hover:bg-muted/50"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-sm">{opt.label}</span>
                    {depth === opt.value && <Badge tone="primary">Selected</Badge>}
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">{opt.detail}</p>
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label htmlFor="date-range" className="text-sm font-medium">
                Publication Date Range
              </label>
              <select
                id="date-range"
                value={dateRange}
                onChange={(e) => setDateRange(e.target.value)}
                className="flex h-10 w-full rounded-lg border bg-background px-3 py-2 text-sm text-foreground"
              >
                <option value="any">Any time</option>
                <option value="last_week">Past week</option>
                <option value="last_month">Past month</option>
                <option value="last_year">Past year</option>
                <option value="last_5_years">Past 5 years</option>
              </select>
            </div>

            <div className="space-y-2">
              <label htmlFor="language" className="text-sm font-medium">
                Output Language
              </label>
              <select
                id="language"
                value={language}
                onChange={(e) => setLanguage(e.target.value as "en" | "bn")}
                className="flex h-10 w-full rounded-lg border bg-background px-3 py-2 text-sm text-foreground"
              >
                <option value="en">English</option>
                <option value="bn">Bengali (বাংলা)</option>
              </select>
            </div>
          </div>

          <div className="space-y-2">
            <span className="text-sm font-medium block">Preferred Source Types (optional)</span>
            <div className="flex flex-wrap gap-2">
              {SOURCE_TYPES.map((st) => {
                const active = sourcePrefs.includes(st.id);
                return (
                  <button
                    key={st.id}
                    type="button"
                    onClick={() => toggleSourcePref(st.id)}
                    className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                      active
                        ? "bg-primary text-primary-foreground border-primary"
                        : "bg-background text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {st.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="pt-2 flex items-center justify-end gap-3">
            <Button type="submit" size="lg" disabled={submitting}>
              <Sparkles className="h-4 w-4" />
              {submitting ? "Starting Investigation..." : "Start Research"}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
