import { Link } from "react-router-dom";
import {
  ArrowRight,
  CheckCircle2,
  Compass,
  FileCheck2,
  GitBranch,
  Layers,
  Scale,
  SearchCheck,
  ShieldCheck,
} from "lucide-react";
import { Badge, Button, Card } from "@/components/ui/primitives";
import { useAuth } from "@/context/AuthContext";

const PIPELINE_STEPS = [
  {
    step: "01",
    title: "Decompose & Plan",
    desc: "Breaks broad research questions into 3–8 non-redundant subquestions and targeted search angles.",
    icon: Layers,
  },
  {
    step: "02",
    title: "Search & Deduplicate",
    desc: "Executes multi-query discovery via pluggable providers, canonicalizes URLs, and enforces SSRF checks.",
    icon: SearchCheck,
  },
  {
    step: "03",
    title: "Extract & Isolate",
    desc: "Fetches readable content with Trafilatura & BeautifulSoup while isolating untrusted HTML from instructions.",
    icon: ShieldCheck,
  },
  {
    step: "04",
    title: "Cross-Check Claims",
    desc: "Distinguishes verified facts, single-source claims, interpretations, and conflicting evidence.",
    icon: Scale,
  },
  {
    step: "05",
    title: "Validate Citations",
    desc: "Verifies every inline [n] citation against collected sources before finalizing and exporting.",
    icon: FileCheck2,
  },
];

export function LandingPage() {
  const { user } = useAuth();

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col">
      {/* Navbar */}
      <header className="border-b bg-card/60 backdrop-blur sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2.5 font-semibold">
            <div className="h-8 w-8 rounded-lg bg-primary/15 border border-primary/30 flex items-center justify-center">
              <Compass className="h-4 w-4 text-primary" />
            </div>
            <span>Vellum Research</span>
          </Link>
          <div className="flex items-center gap-3">
            <a
              href="https://github.com/TahmidZ68/vellum-research"
              target="_blank"
              rel="noopener noreferrer"
              className="hidden sm:inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
            >
              <GitBranch className="h-4 w-4" />
              GitHub
            </a>
            {user ? (
              <Link to="/dashboard">
                <Button size="sm">Open Workspace</Button>
              </Link>
            ) : (
              <>
                <Link to="/login">
                  <Button variant="ghost" size="sm">
                    Sign in
                  </Button>
                </Link>
                <Link to="/register">
                  <Button size="sm">Try Application</Button>
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 pt-16 pb-14">
        <div className="max-w-3xl space-y-6">
          <Badge tone="primary">Open-Source Research Workspace · MIT License</Badge>
          <h1 className="text-4xl sm:text-5xl font-bold tracking-tight leading-tight">
            Turn complex questions into evidence-backed reports with traceable sources.
          </h1>
          <p className="text-lg text-muted-foreground leading-relaxed">
            Built for researchers, founders, analysts, and developers. Vellum Research plans an
            investigation, extracts readable evidence, cross-checks conflicting claims, and validates
            every inline citation against collected sources.
          </p>
          <div className="flex flex-wrap items-center gap-3 pt-2">
            <Link to={user ? "/research/new" : "/register"}>
              <Button size="lg">
                Start Investigating
                <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
            <a
              href="https://github.com/TahmidZ68/vellum-research"
              target="_blank"
              rel="noopener noreferrer"
            >
              <Button variant="outline" size="lg">
                <GitBranch className="h-4 w-4" />
                View Repository
              </Button>
            </a>
          </div>
        </div>
      </section>

      {/* Pipeline Overview */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 py-10 w-full">
        <div className="mb-8">
          <h2 className="text-2xl font-semibold tracking-tight">Controlled Research Workflow</h2>
          <p className="text-sm text-muted-foreground mt-1">
            A deterministic LangGraph pipeline rather than an unconstrained agent loop.
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          {PIPELINE_STEPS.map((item) => {
            const Icon = item.icon;
            return (
              <Card key={item.step} className="p-5 space-y-3 bg-card/70">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono text-primary font-semibold">{item.step}</span>
                  <Icon className="h-4 w-4 text-primary" />
                </div>
                <h3 className="font-semibold text-sm">{item.title}</h3>
                <p className="text-xs text-muted-foreground leading-relaxed">{item.desc}</p>
              </Card>
            );
          })}
        </div>
      </section>

      {/* Example Report Preview */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 py-12 w-full">
        <Card className="p-6 sm:p-8 border-primary/25 bg-card/80">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b">
            <div>
              <Badge tone="success" className="mb-2">
                <CheckCircle2 className="h-3 w-3" />
                Sample Output Preview
              </Badge>
              <h3 className="text-xl font-semibold">
                AI Automation Market in Bangladesh — Evidence & Competitor Synthesis
              </h3>
            </div>
            <Badge tone="neutral">Citations Validated</Badge>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 pt-6">
            <div className="lg:col-span-2 space-y-4 text-sm leading-relaxed">
              <p>
                <strong className="text-foreground">Verified Finding:</strong> Enterprise workflow
                adoption has grown in export-oriented services and fintech, whereas verifiable
                small-business adoption metrics remain sparse{" "}
                <span className="px-1.5 py-0.5 rounded bg-primary/15 text-primary font-mono text-xs">
                  [1]
                </span>
                .
              </p>
              <p>
                <strong className="text-foreground">Contradiction Detected:</strong> Commercial
                agency pages advertise up to 70% cost savings{" "}
                <span className="px-1.5 py-0.5 rounded bg-primary/15 text-primary font-mono text-xs">
                  [2]
                </span>
                , whereas controlled regional pilots measure 25–30% net efficiency gains once
                onboarding overhead is included{" "}
                <span className="px-1.5 py-0.5 rounded bg-primary/15 text-primary font-mono text-xs">
                  [3]
                </span>
                .
              </p>
              <p className="text-muted-foreground italic">
                Interpretation: Standardized onboarding packages for mid-market firms represent an
                under-served wedge, though pricing sensitivity requires primary validation.
              </p>
            </div>
            <div className="rounded-lg border bg-background/60 p-4 space-y-3 text-xs">
              <p className="font-semibold text-foreground uppercase tracking-wider text-[11px]">
                Traceable Source Library
              </p>
              <div className="space-y-2">
                <div className="p-2.5 rounded border bg-card">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-primary font-semibold">[1] Primary</span>
                    <span className="text-muted-foreground">2025-11</span>
                  </div>
                  <p className="font-medium mt-1">Digital Enterprise Adoption Brief</p>
                </div>
                <div className="p-2.5 rounded border bg-card">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-primary font-semibold">[2] Promotional</span>
                    <span className="text-muted-foreground">2025-08</span>
                  </div>
                  <p className="font-medium mt-1">Commercial Case Study (Unverified ROI)</p>
                </div>
                <div className="p-2.5 rounded border bg-card">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-primary font-semibold">[3] Academic</span>
                    <span className="text-muted-foreground">2026-01</span>
                  </div>
                  <p className="font-medium mt-1">Controlled Pilot Productivity Benchmark</p>
                </div>
              </div>
            </div>
          </div>
        </Card>
      </section>

      {/* Footer */}
      <footer className="mt-auto border-t bg-card/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-muted-foreground">
          <p>Vellum Research · MIT Licensed Open-Source Software</p>
          <div className="flex items-center gap-5">
            <a
              href="/docs"
              onClick={(e) => {
                e.preventDefault();
              }}
              className="hover:text-foreground"
            >
              Documentation (see /docs)
            </a>
            <a
              href="https://github.com/TahmidZ68/vellum-research"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-foreground"
            >
              GitHub
            </a>
            <span>MIT License</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
