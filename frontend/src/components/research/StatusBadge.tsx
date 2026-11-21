import { CheckCircle2, Clock, Loader2, ShieldAlert, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/primitives";

export function StatusBadge({ status }: { status: string }) {
  switch (status) {
    case "completed":
    case "validated":
    case "extracted":
      return (
        <Badge tone="success">
          <CheckCircle2 className="h-3 w-3" />
          {status}
        </Badge>
      );
    case "running":
    case "queued":
    case "pending":
      return (
        <Badge tone="primary">
          <Loader2 className="h-3 w-3 animate-spin" />
          {status}
        </Badge>
      );
    case "warning":
      return (
        <Badge tone="warning">
          <ShieldAlert className="h-3 w-3" />
          warning
        </Badge>
      );
    case "failed":
    case "cancelled":
      return (
        <Badge tone="danger">
          <XCircle className="h-3 w-3" />
          {status}
        </Badge>
      );
    default:
      return (
        <Badge tone="neutral">
          <Clock className="h-3 w-3" />
          {status}
        </Badge>
      );
  }
}
