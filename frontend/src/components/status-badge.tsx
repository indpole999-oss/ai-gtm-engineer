import { cn } from "@/lib/utils";
import { normalizeState, STATE_LABEL, type BackendState } from "@/lib/gtm-api";

const TONE: Record<BackendState, string> = {
  success: "border-success/30 bg-success/10 text-success",
  warning: "border-warning/40 bg-warning/10 text-warning",
  generated: "border-info/30 bg-info/10 text-info",
  pending: "border-info/30 bg-info/10 text-info",
  skipped: "border-border bg-muted text-muted-foreground",
  not_configured: "border-warning/40 bg-warning/10 text-warning",
  error: "border-destructive/30 bg-destructive/10 text-destructive",
  unknown: "border-border bg-muted text-muted-foreground",
};

const DOT: Record<BackendState, string> = {
  success: "bg-success",
  warning: "bg-warning",
  generated: "bg-info",
  pending: "bg-info",
  skipped: "bg-muted-foreground",
  not_configured: "bg-warning",
  error: "bg-destructive",
  unknown: "bg-muted-foreground",
};

export function StatusBadge({
  value,
  state,
  className,
}: {
  value?: unknown;
  state?: BackendState;
  className?: string;
}) {
  const resolved = state ?? normalizeState(value);
  const raw =
    typeof value === "string" && value.trim()
      ? value.replace(/_/g, " ")
      : typeof value === "boolean"
        ? value
          ? "active"
          : "inactive"
        : STATE_LABEL[resolved];

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2 py-0.5 text-xs font-medium capitalize",
        TONE[resolved],
        className,
      )}
    >
      <span className={cn("size-1.5 rounded-full", DOT[resolved])} aria-hidden />
      {raw}
    </span>
  );
}
