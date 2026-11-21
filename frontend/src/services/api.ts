import type {
  AuthResponse,
  EvidenceItem,
  ReportData,
  ResearchMessage,
  ResearchProject,
  ResearchRun,
  SettingsOverview,
  SourceItem,
  User,
} from "@/types/api";

const API_BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") || "";

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

export function getStoredToken(): string | null {
  return localStorage.getItem("ora_token");
}

export function setStoredToken(token: string | null): void {
  if (token) {
    localStorage.setItem("ora_token", token);
  } else {
    localStorage.removeItem("ora_token");
  }
}

async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getStoredToken();
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const res = await fetch(`${API_BASE}/api/v1${path}`, {
    ...init,
    headers,
  });

  if (res.status === 204) {
    return undefined as T;
  }

  const isJson = res.headers.get("content-type")?.includes("application/json");
  const payload = isJson ? await res.json() : await res.text();

  if (!res.ok) {
    const detail =
      typeof payload === "object" && payload && "detail" in payload
        ? String((payload as { detail: unknown }).detail)
        : `Request failed with status ${res.status}`;
    throw new ApiError(res.status, detail);
  }
  return payload as T;
}

export const api = {
  register: (data: { email: string; password: string; full_name: string }) =>
    apiRequest<AuthResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  login: (data: { email: string; password: string }) =>
    apiRequest<AuthResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  me: () => apiRequest<User>("/auth/me"),

  getSettings: () => apiRequest<SettingsOverview>("/settings"),

  updateSettings: (data: {
    full_name?: string;
    preferred_language?: string;
    preferred_theme?: string;
  }) =>
    apiRequest<User>("/settings", {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  listProjects: (includeArchived = false) =>
    apiRequest<ResearchProject[]>(`/projects?include_archived=${includeArchived}`),

  createProject: (data: { title: string; description: string }) =>
    apiRequest<ResearchProject>("/projects", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getProject: (projectId: string) =>
    apiRequest<ResearchProject>(`/projects/${projectId}`),

  getProjectRuns: (projectId: string) =>
    apiRequest<ResearchRun[]>(`/projects/${projectId}/runs`),

  updateProject: (
    projectId: string,
    data: { title?: string; description?: string; is_archived?: boolean }
  ) =>
    apiRequest<ResearchProject>(`/projects/${projectId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  deleteProject: (projectId: string) =>
    apiRequest<void>(`/projects/${projectId}`, { method: "DELETE" }),

  listResearchRuns: (limit = 20) =>
    apiRequest<ResearchRun[]>(`/research?limit=${limit}`),

  startResearch: (data: {
    project_id?: string | null;
    project_title?: string;
    query: string;
    context: string;
    depth: "quick" | "standard" | "deep";
    date_range: string;
    source_preferences: string[];
    language: "en" | "bn";
  }) =>
    apiRequest<ResearchRun>("/research", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getResearchRun: (runId: string) =>
    apiRequest<ResearchRun>(`/research/${runId}`),

  cancelResearchRun: (runId: string) =>
    apiRequest<ResearchRun>(`/research/${runId}/cancel`, { method: "POST" }),

  getResearchSources: (runId: string) =>
    apiRequest<SourceItem[]>(`/research/${runId}/sources`),

  getResearchEvidence: (runId: string) =>
    apiRequest<EvidenceItem[]>(`/research/${runId}/evidence`),

  getResearchReport: (runId: string) =>
    apiRequest<ReportData>(`/research/${runId}/report`),

  getResearchMessages: (runId: string) =>
    apiRequest<ResearchMessage[]>(`/research/${runId}/messages`),

  askFollowUp: (runId: string, question: string) =>
    apiRequest<{ user_message: ResearchMessage; assistant_message: ResearchMessage }>(
      `/research/${runId}/follow-up`,
      {
        method: "POST",
        body: JSON.stringify({ question }),
      }
    ),

  getEventsStreamUrl: (runId: string) => {
    const token = getStoredToken() || "";
    return `${API_BASE}/api/v1/research/${runId}/events?token=${encodeURIComponent(token)}`;
  },

  downloadExport: async (runId: string, format: "markdown" | "pdf") => {
    const token = getStoredToken();
    const res = await fetch(`${API_BASE}/api/v1/research/${runId}/export?format=${format}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) {
      throw new ApiError(res.status, "Failed to export report.");
    }
    const blob = await res.blob();
    const disposition = res.headers.get("content-disposition") || "";
    const match = /filename="([^"]+)"/.exec(disposition);
    const filename = match?.[1] || `research-report.${format === "pdf" ? "pdf" : "md"}`;
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  },
};
