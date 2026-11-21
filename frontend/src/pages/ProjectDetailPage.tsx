import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, FileText, Plus } from "lucide-react";
import { api } from "@/services/api";
import { formatDate } from "@/lib/utils";
import { Badge, Button, Card } from "@/components/ui/primitives";
import { StatusBadge } from "@/components/research/StatusBadge";

export function ProjectDetailPage() {
  const { projectId = "" } = useParams();

  const projectQuery = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => api.getProject(projectId),
    enabled: Boolean(projectId),
  });

  const runsQuery = useQuery({
    queryKey: ["project-runs", projectId],
    queryFn: () => api.getProjectRuns(projectId),
    enabled: Boolean(projectId),
  });

  if (projectQuery.isLoading) {
    return <Card className="p-8 text-center text-sm text-muted-foreground">Loading project...</Card>;
  }

  if (projectQuery.isError || !projectQuery.data) {
    return (
      <Card className="p-6 border-destructive/40 bg-destructive/10 text-sm text-rose-300">
        Project not found or inaccessible.
      </Card>
    );
  }

  const project = projectQuery.data;
  const runs = runsQuery.data || [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="space-y-1">
          <Link
            to="/dashboard"
            className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to Dashboard
          </Link>
          <h1 className="text-2xl font-bold tracking-tight">{project.title}</h1>
          {project.description && (
            <p className="text-sm text-muted-foreground">{project.description}</p>
          )}
        </div>
        <Link to={`/research/new?projectId=${project.id}`}>
          <Button>
            <Plus className="h-4 w-4" />
            New Run in Project
          </Button>
        </Link>
      </div>

      <Card className="divide-y">
        {runs.length === 0 ? (
          <div className="p-8 text-center text-sm text-muted-foreground">
            No research runs in this project yet.
          </div>
        ) : (
          runs.map((run) => (
            <div
              key={run.id}
              className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
            >
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <StatusBadge status={run.status} />
                  <Badge tone="neutral">{run.depth}</Badge>
                  <span className="text-xs text-muted-foreground">
                    {formatDate(run.created_at)}
                  </span>
                </div>
                <p className="text-sm font-medium">{run.query}</p>
              </div>
              <div className="flex items-center gap-2">
                <Link to={`/research/${run.id}`}>
                  <Button variant="outline" size="sm">
                    Workspace
                  </Button>
                </Link>
                <Link to={`/research/${run.id}/report`}>
                  <Button size="sm">
                    <FileText className="h-3.5 w-3.5" />
                    Report
                  </Button>
                </Link>
              </div>
            </div>
          ))
        )}
      </Card>
    </div>
  );
}
