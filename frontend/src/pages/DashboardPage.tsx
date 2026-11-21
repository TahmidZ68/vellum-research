import React, { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Archive,
  ArrowRight,
  FileText,
  FolderKanban,
  Plus,
  Search,
  Trash2,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/services/api";
import { formatDate } from "@/lib/utils";
import { Badge, Button, Card, Input } from "@/components/ui/primitives";
import { StatusBadge } from "@/components/research/StatusBadge";

export function DashboardPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [newTitle, setNewTitle] = useState("");
  const [showNewProject, setShowNewProject] = useState(false);

  const projectsQuery = useQuery({
    queryKey: ["projects"],
    queryFn: () => api.listProjects(false),
  });

  const runsQuery = useQuery({
    queryKey: ["research-runs"],
    queryFn: () => api.listResearchRuns(12),
  });

  const createProjectMutation = useMutation({
    mutationFn: (title: string) => api.createProject({ title, description: "" }),
    onSuccess: () => {
      setNewTitle("");
      setShowNewProject(false);
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });

  const archiveMutation = useMutation({
    mutationFn: (id: string) => api.updateProject(id, { is_archived: true }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteProject(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
      void queryClient.invalidateQueries({ queryKey: ["research-runs"] });
    },
  });

  const handleCreateProject = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim()) return;
    createProjectMutation.mutate(newTitle.trim());
  };

  const projects = projectsQuery.data || [];
  const runs = runsQuery.data || [];

  return (
    <div className="space-y-8">
      {/* Welcome Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            Welcome back, {user?.full_name || "Researcher"}
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Launch new evidence-backed investigations or revisit saved research reports.
          </p>
        </div>
        <div className="flex items-center gap-2.5">
          <Button variant="outline" onClick={() => setShowNewProject((v) => !v)}>
            <FolderKanban className="h-4 w-4" />
            New Project
          </Button>
          <Link to="/research/new">
            <Button>
              <Plus className="h-4 w-4" />
              New Research
            </Button>
          </Link>
        </div>
      </div>

      {showNewProject && (
        <Card className="p-4">
          <form onSubmit={handleCreateProject} className="flex flex-col sm:flex-row gap-3">
            <Input
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              placeholder="Project title (e.g., Bangladesh AI Automation Market)"
              required
            />
            <Button type="submit" disabled={createProjectMutation.isPending}>
              {createProjectMutation.isPending ? "Creating..." : "Create Project"}
            </Button>
          </form>
        </Card>
      )}

      {/* Summary Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="p-5">
          <p className="text-xs font-medium text-muted-foreground">Active Projects</p>
          <p className="text-2xl font-bold mt-1">{projects.length}</p>
        </Card>
        <Card className="p-5">
          <p className="text-xs font-medium text-muted-foreground">Recent Investigations</p>
          <p className="text-2xl font-bold mt-1">{runs.length}</p>
        </Card>
        <Card className="p-5">
          <p className="text-xs font-medium text-muted-foreground">Completed Reports</p>
          <p className="text-2xl font-bold mt-1">
            {runs.filter((r) => r.status === "completed" && r.has_report).length}
          </p>
        </Card>
      </div>

      {/* Loading / Error */}
      {(projectsQuery.isLoading || runsQuery.isLoading) && (
        <Card className="p-8 text-center text-sm text-muted-foreground">
          Loading your research workspace...
        </Card>
      )}

      {(projectsQuery.isError || runsQuery.isError) && (
        <Card className="p-6 border-destructive/40 bg-destructive/10 text-sm text-rose-300">
          Failed to load workspace data. Please verify the backend API is reachable.
        </Card>
      )}

      {/* Empty State */}
      {!projectsQuery.isLoading && !runsQuery.isLoading && projects.length === 0 && runs.length === 0 && (
        <Card className="p-10 text-center space-y-4">
          <div className="mx-auto h-12 w-12 rounded-xl bg-primary/15 flex items-center justify-center">
            <Search className="h-6 w-6 text-primary" />
          </div>
          <div className="space-y-1 max-w-md mx-auto">
            <h2 className="text-lg font-semibold">No research investigations yet</h2>
            <p className="text-sm text-muted-foreground">
              Start your first investigation to generate a structured plan, evaluate web sources,
              and read a fully cited report.
            </p>
          </div>
          <Link to="/research/new" className="inline-block">
            <Button>
              <Plus className="h-4 w-4" />
              Start First Investigation
            </Button>
          </Link>
        </Card>
      )}

      {/* Projects & Recent Runs */}
      {projects.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-lg font-semibold tracking-tight">Research Projects</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {projects.map((project) => (
              <Card key={project.id} className="p-5 flex flex-col justify-between gap-4">
                <div className="space-y-2">
                  <div className="flex items-start justify-between gap-2">
                    <Link
                      to={`/projects/${project.id}`}
                      className="font-semibold text-sm hover:text-primary transition-colors line-clamp-2"
                    >
                      {project.title}
                    </Link>
                    {project.latest_run_status && (
                      <StatusBadge status={project.latest_run_status} />
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground line-clamp-2">
                    {project.description || "No description provided."}
                  </p>
                </div>
                <div className="flex items-center justify-between pt-3 border-t text-xs text-muted-foreground">
                  <span>
                    {project.run_count} {project.run_count === 1 ? "run" : "runs"} ·{" "}
                    {formatDate(project.updated_at)}
                  </span>
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      title="Archive project"
                      onClick={() => archiveMutation.mutate(project.id)}
                    >
                      <Archive className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      title="Delete project"
                      onClick={() => deleteMutation.mutate(project.id)}
                    >
                      <Trash2 className="h-3.5 w-3.5 text-rose-400" />
                    </Button>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </section>
      )}

      {runs.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-lg font-semibold tracking-tight">Recent Investigations & Reports</h2>
          <Card className="divide-y">
            {runs.map((run) => (
              <div
                key={run.id}
                className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
              >
                <div className="space-y-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <StatusBadge status={run.status} />
                    <Badge tone="neutral">{run.depth}</Badge>
                    {run.is_demo_mode && <Badge tone="warning">Demo Sample</Badge>}
                    <span className="text-xs text-muted-foreground">
                      {formatDate(run.created_at)}
                    </span>
                  </div>
                  <p className="text-sm font-medium truncate">{run.query}</p>
                  <p className="text-xs text-muted-foreground">
                    Stage: {run.current_stage} · {run.source_count} sources · {run.evidence_count}{" "}
                    evidence records
                  </p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <Link to={`/research/${run.id}`}>
                    <Button variant="outline" size="sm">
                      Live View
                    </Button>
                  </Link>
                  {run.has_report && (
                    <Link to={`/research/${run.id}/report`}>
                      <Button size="sm">
                        <FileText className="h-3.5 w-3.5" />
                        Open Report
                        <ArrowRight className="h-3.5 w-3.5" />
                      </Button>
                    </Link>
                  )}
                </div>
              </div>
            ))}
          </Card>
        </section>
      )}
    </div>
  );
}
