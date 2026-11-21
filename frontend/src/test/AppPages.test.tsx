import React from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DashboardPage } from "@/pages/DashboardPage";
import { NewResearchPage } from "@/pages/NewResearchPage";
import { LiveResearchPage } from "@/pages/LiveResearchPage";
import { ReportReaderPage } from "@/pages/ReportReaderPage";
import { api } from "@/services/api";

vi.mock("@/context/AuthContext", () => ({
  useAuth: () => ({
    user: {
      id: "user-1",
      email: "researcher@example.com",
      full_name: "Ada Lovelace",
      preferred_language: "en",
      preferred_theme: "dark",
      created_at: "2026-11-21T00:00:00Z",
    },
    loading: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    refreshUser: vi.fn(),
  }),
}));

class MockEventSource {
  url: string;
  listeners: Record<string, Array<(ev: MessageEvent) => void>> = {};
  onmessage: ((ev: MessageEvent) => void) | null = null;
  constructor(url: string) {
    this.url = url;
    setTimeout(() => {
      const payload = JSON.stringify({
        run_id: "run-1",
        event: "plan_created",
        stage: "create_research_plan",
        message: "Created research plan with 3 subquestions",
        data: {},
        timestamp: "2026-11-21T12:00:00Z",
      });
      (this.listeners["plan_created"] || []).forEach((fn) =>
        fn({ data: payload } as MessageEvent)
      );
    }, 10);
  }
  addEventListener(name: string, cb: (ev: MessageEvent) => void) {
    this.listeners[name] = this.listeners[name] || [];
    this.listeners[name].push(cb);
  }
  close() {}
}

function renderWithQuery(ui: React.ReactElement, initialEntries = ["/"]) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={initialEntries}>{ui}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe("Vellum Research Frontend", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    (globalThis as unknown as { EventSource: typeof EventSource }).EventSource =
      MockEventSource as unknown as typeof EventSource;
    (globalThis as unknown as { ResizeObserver: unknown }).ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    };
  });

  it("renders Dashboard with projects and completed runs", async () => {
    vi.spyOn(api, "listProjects").mockResolvedValue([
      {
        id: "proj-1",
        user_id: "user-1",
        title: "Bangladesh AI Market",
        description: "Competitor landscape",
        is_archived: false,
        created_at: "2026-11-21T00:00:00Z",
        updated_at: "2026-11-21T00:00:00Z",
        run_count: 1,
        latest_run_status: "completed",
        latest_run_id: "run-1",
      },
    ]);
    vi.spyOn(api, "listResearchRuns").mockResolvedValue([
      {
        id: "run-1",
        project_id: "proj-1",
        user_id: "user-1",
        query: "Research AI automation in Bangladesh",
        context: "",
        depth: "standard",
        date_range: "any",
        source_preferences: [],
        language: "en",
        status: "completed",
        current_stage: "completed",
        retry_count: 0,
        cancel_requested: false,
        is_demo_mode: false,
        error_message: null,
        started_at: null,
        completed_at: null,
        created_at: "2026-11-21T00:00:00Z",
        plan: null,
        source_count: 5,
        extracted_source_count: 5,
        evidence_count: 8,
        has_report: true,
      },
    ]);

    renderWithQuery(<DashboardPage />);
    expect(await screen.findByText("Bangladesh AI Market")).toBeInTheDocument();
    expect(screen.getByText("Research AI automation in Bangladesh")).toBeInTheDocument();
    expect(screen.getByText("Open Report")).toBeInTheDocument();
  });

  it("validates short query on NewResearchPage before submitting", async () => {
    vi.spyOn(api, "listProjects").mockResolvedValue([]);
    vi.spyOn(api, "getSettings").mockResolvedValue({
      user: {
        id: "user-1",
        email: "researcher@example.com",
        full_name: "Ada",
        preferred_language: "en",
        preferred_theme: "dark",
        created_at: "2026-11-21T00:00:00Z",
      },
      providers: {
        llm_provider: "mock",
        llm_model: "mock-analyst-v1",
        llm_configured: true,
        llm_guidance: "",
        search_provider: "mock",
        search_configured: true,
        search_guidance: "",
        allow_mock_providers: true,
        is_demo_mode: true,
      },
      usage: { total_projects: 0, total_runs: 0, runs_last_24h: 0, daily_limit: 30 },
    });
    const startSpy = vi.spyOn(api, "startResearch");

    renderWithQuery(<NewResearchPage />);
    const input = await screen.findByLabelText(/Research Question/i);
    await userEvent.type(input, "AI");
    await userEvent.click(screen.getByRole("button", { name: /Start Research/i }));

    expect(
      await screen.findByText(/at least 5 characters/i)
    ).toBeInTheDocument();
    expect(startSpy).not.toHaveBeenCalled();
  });

  it("displays live SSE progress events on LiveResearchPage", async () => {
    vi.spyOn(api, "getResearchRun").mockResolvedValue({
      id: "run-1",
      project_id: "proj-1",
      user_id: "user-1",
      query: "Compare AI agent frameworks",
      context: "",
      depth: "quick",
      date_range: "any",
      source_preferences: [],
      language: "en",
      status: "running",
      current_stage: "create_research_plan",
      retry_count: 0,
      cancel_requested: false,
      is_demo_mode: false,
      error_message: null,
      started_at: null,
      completed_at: null,
      created_at: "2026-11-21T00:00:00Z",
      plan: {
        id: "plan-1",
        objective: "Compare open-source agent frameworks",
        scope: "Architecture & deployment",
        subquestions: [{ id: "sq-1", question: "How do graphs differ from loops?" }],
        search_strategy: {},
        created_at: "2026-11-21T00:00:00Z",
      },
      source_count: 0,
      extracted_source_count: 0,
      evidence_count: 0,
      has_report: false,
    });

    renderWithQuery(
      <Routes>
        <Route path="/research/:runId" element={<LiveResearchPage />} />
      </Routes>,
      ["/research/run-1"]
    );

    expect(await screen.findByText("Compare AI agent frameworks")).toBeInTheDocument();
    expect(await screen.findByText(/Created research plan with 3 subquestions/i)).toBeInTheDocument();
    expect(screen.getByText(/How do graphs differ from loops/i)).toBeInTheDocument();
  });

  it("renders ReportReaderPage, navigates citations, and triggers exports", async () => {
    vi.spyOn(api, "getResearchRun").mockResolvedValue({
      id: "run-1",
      project_id: "proj-1",
      user_id: "user-1",
      query: "Agent frameworks comparison",
      context: "",
      depth: "standard",
      date_range: "any",
      source_preferences: [],
      language: "en",
      status: "completed",
      current_stage: "completed",
      retry_count: 0,
      cancel_requested: false,
      is_demo_mode: false,
      error_message: null,
      started_at: null,
      completed_at: null,
      created_at: "2026-11-21T00:00:00Z",
      plan: null,
      source_count: 2,
      extracted_source_count: 2,
      evidence_count: 2,
      has_report: true,
    });

    vi.spyOn(api, "getResearchMessages").mockResolvedValue([]);
    vi.spyOn(api, "getResearchReport").mockResolvedValue({
      id: "rep-1",
      run_id: "run-1",
      version: 1,
      title: "Open-Source Agent Frameworks Report",
      summary: "Evidence-backed comparison.",
      content: "## Key Findings\nLangGraph supports stateful graphs [1]. Benchmark caveats exist [2].",
      structured_data: {
        contradictions: [
          {
            topic: "Latency overhead",
            claim_a: "Low overhead in benchmarks [1]",
            claim_b: "Higher state persistence latency in large graphs [2]",
            classification: "difference_in_measurement",
            explanation: "Different workload sizes tested.",
          },
        ],
      },
      citation_validation: {
        is_valid: true,
        cited_numbers: [1, 2],
        invalid_numbers: [],
        ungrounded_urls: [],
        errors: [],
        warnings: [],
      },
      status: "validated",
      created_at: "2026-11-21T00:00:00Z",
      citations: [
        {
          id: "cit-1",
          citation_number: 1,
          source_id: "src-1",
          evidence_id: "ev-1",
          cited_claim: "LangGraph supports stateful workflows.",
          source: {
            id: "src-1",
            run_id: "run-1",
            url: "https://docs.example.org/langgraph",
            canonical_url: "https://docs.example.org/langgraph",
            title: "LangGraph Official Documentation",
            publisher: "docs.example.org",
            author: null,
            published_at: "2026-01-10",
            retrieved_at: "2026-11-21T00:00:00Z",
            source_type: "primary",
            extraction_status: "extracted",
            relevance_score: 0.95,
            relevance_note: "Primary docs",
            limitations: "None",
            raw_excerpt: "Stateful graph execution.",
            error_detail: null,
          },
          evidence: null,
        },
        {
          id: "cit-2",
          citation_number: 2,
          source_id: "src-2",
          evidence_id: "ev-2",
          cited_claim: "Benchmarks vary by state size.",
          source: {
            id: "src-2",
            run_id: "run-1",
            url: "https://research.example.edu/eval",
            canonical_url: "https://research.example.edu/eval",
            title: "Independent Agent Runtime Benchmark",
            publisher: "research.example.edu",
            author: "J. Researcher",
            published_at: "2026-02-01",
            retrieved_at: "2026-11-21T00:00:00Z",
            source_type: "academic",
            extraction_status: "extracted",
            relevance_score: 0.89,
            relevance_note: "Academic paper",
            limitations: "Small cluster sample",
            raw_excerpt: "Checkpoint overhead depends on payload size.",
            error_detail: null,
          },
          evidence: null,
        },
      ],
    });

    const exportSpy = vi.spyOn(api, "downloadExport").mockResolvedValue();

    renderWithQuery(
      <Routes>
        <Route path="/research/:runId/report" element={<ReportReaderPage />} />
      </Routes>,
      ["/research/run-1/report"]
    );

    expect(
      await screen.findByText("Open-Source Agent Frameworks Report")
    ).toBeInTheDocument();

    // Click inline citation [2] and confirm Inspector updates to Source 2
    const cite2Buttons = await screen.findAllByRole("button", { name: "[2]" });
    await userEvent.click(cite2Buttons[0]);
    expect(
      await screen.findByText("Independent Agent Runtime Benchmark")
    ).toBeInTheDocument();

    // Trigger Markdown & PDF exports
    await userEvent.click(screen.getByRole("button", { name: /Export Markdown/i }));
    await userEvent.click(screen.getByRole("button", { name: /Export PDF/i }));
    await waitFor(() => {
      expect(exportSpy).toHaveBeenCalledWith("run-1", "markdown");
      expect(exportSpy).toHaveBeenCalledWith("run-1", "pdf");
    });
  });
});
