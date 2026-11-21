export interface User {
  id: string;
  email: string;
  full_name: string;
  preferred_language: "en" | "bn" | string;
  preferred_theme: "dark" | "light" | string;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface ProviderDiagnostics {
  llm_provider: string;
  llm_model: string;
  llm_configured: boolean;
  llm_guidance: string;
  search_provider: string;
  search_configured: boolean;
  search_guidance: string;
  allow_mock_providers: boolean;
  is_demo_mode: boolean;
}

export interface SettingsOverview {
  user: User;
  providers: ProviderDiagnostics;
  usage: {
    total_projects: number;
    total_runs: number;
    runs_last_24h: number;
    daily_limit: number;
  };
}

export interface ResearchProject {
  id: string;
  user_id: string;
  title: string;
  description: string;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
  run_count: number;
  latest_run_status: string | null;
  latest_run_id: string | null;
}

export interface ResearchPlan {
  id: string;
  objective: string;
  scope: string;
  subquestions: Array<{ id: string; question: string; angle?: string }>;
  search_strategy: Record<string, unknown>;
  created_at: string;
}

export interface ResearchRun {
  id: string;
  project_id: string;
  user_id: string;
  query: string;
  context: string;
  depth: "quick" | "standard" | "deep";
  date_range: string;
  source_preferences: string[];
  language: "en" | "bn";
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  current_stage: string;
  retry_count: number;
  cancel_requested: boolean;
  is_demo_mode: boolean;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  plan: ResearchPlan | null;
  source_count: number;
  extracted_source_count: number;
  evidence_count: number;
  has_report: boolean;
}

export interface SourceItem {
  id: string;
  run_id: string;
  url: string;
  canonical_url: string;
  title: string;
  publisher: string;
  author: string | null;
  published_at: string | null;
  retrieved_at: string;
  source_type: string;
  extraction_status: string;
  relevance_score: number;
  relevance_note: string;
  limitations: string;
  raw_excerpt: string;
  error_detail: string | null;
}

export interface EvidenceItem {
  id: string;
  run_id: string;
  source_id: string;
  claim: string;
  excerpt: string;
  evidence_type: string;
  claim_category: string;
  relevance: string;
  date_context: string;
  limitations: string;
  corroboration_status: string;
  created_at: string;
}

export interface ReportCitation {
  id: string;
  citation_number: number;
  source_id: string;
  evidence_id: string | null;
  cited_claim: string;
  source: SourceItem | null;
  evidence: EvidenceItem | null;
}

export interface ContradictionItem {
  topic: string;
  claim_a: string;
  claim_b: string;
  classification: string;
  explanation: string;
  source_refs?: number[];
}

export interface ReportData {
  id: string;
  run_id: string;
  version: number;
  title: string;
  summary: string;
  content: string;
  structured_data: {
    key_findings?: string[];
    contradictions?: ContradictionItem[];
    research_gaps?: string[];
    subquestions?: Array<{ id: string; question: string; angle?: string }>;
    analytics?: {
      source_types?: Array<{ name: string; count: number }>;
      claim_categories?: Array<{ name: string; count: number }>;
      extraction_statuses?: Array<{ name: string; count: number }>;
    };
  };
  citation_validation: {
    is_valid: boolean;
    cited_numbers: number[];
    invalid_numbers: number[];
    ungrounded_urls: string[];
    errors: string[];
    warnings: string[];
  };
  status: "draft" | "validated" | "warning";
  created_at: string;
  citations: ReportCitation[];
}

export interface ResearchMessage {
  id: string;
  run_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  citations: Array<{ citation_number: number; title: string; url: string; source_id: string }>;
  created_at: string;
}

export interface ResearchProgressEvent {
  run_id: string;
  event: string;
  stage: string;
  message: string;
  data: Record<string, unknown>;
  timestamp: string;
}
