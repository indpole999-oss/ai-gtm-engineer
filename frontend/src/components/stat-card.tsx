import { Link } from "@tanstack/react-router";
import { AlertTriangle } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";

export function StatCard({
  label,
  value,
  hint,
  icon: Icon,
  to,
  loading,
  error,
}: {
  label: string;
  value: number | string;
  hint?: string;
  icon?: LucideIcon;
  to?: string;
  loading?: boolean;
  error?: unknown;
}) {
  const status = error instanceof ApiError ? error.status : undefined;

  const body = (
    <>
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-medium text-muted-foreground">{label}</p>
        {Icon ? <Icon className="size-4 text-muted-foreground" aria-hidden /> : null}
      </div>
      {loading ? (
        <Skeleton className="mt-3 h-7 w-16" />
      ) : error ? (
        <p className="mt-2 flex items-center gap-1.5 text-sm text-warning">
          <AlertTriangle className="size-4" aria-hidden />
          {status === 0 ? "Backend offline" : status === 404 ? "Unavailable" : `HTTP ${status ?? "error"}`}
        </p>
      ) : (
        <p className="mt-2 text-2xl font-semibold tabular-nums">{value}</p>
      )}
      {hint && !loading && !error ? (
        <p className="mt-1 text-xs text-muted-foreground">{hint}</p>
      ) : null}
    </>
  );

  const className =
    "block rounded-lg border bg-card p-4 shadow-xs transition-colors" +
    (to ? " hover:border-primary/40" : "");

  return to ? (
    <Link to={to} className={className}>
      {body}
    </Link>
  ) : (
    <div className={className}>{body}</div>
  );
}
