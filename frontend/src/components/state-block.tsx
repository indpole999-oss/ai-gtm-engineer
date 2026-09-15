import { AlertTriangle, Inbox, Loader2, PlugZap, ShieldAlert } from "lucide-react";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

export function LoadingBlock({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-2 p-4" aria-busy="true" aria-live="polite">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </div>
  );
}

export function InlineSpinner({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm text-muted-foreground">
      <Loader2 className="size-4 animate-spin" aria-hidden />
      {label}
    </span>
  );
}

export function EmptyBlock({ title, description }: { title: string; description: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-16 text-center">
      <Inbox className="size-6 text-muted-foreground" aria-hidden />
      <p className="font-display text-base font-semibold">{title}</p>
      <p className="max-w-sm text-sm text-muted-foreground">{description}</p>
    </div>
  );
}

export function ErrorBlock({
  error,
  onRetry,
  resourceLabel,
}: {
  error: unknown;
  onRetry?: () => void;
  resourceLabel: string;
}) {
  const status = error instanceof ApiError ? error.status : undefined;
  const message = error instanceof Error ? error.message : "Unexpected error.";

  const Icon = status === 0 ? PlugZap : status === 403 || status === 401 ? ShieldAlert : AlertTriangle;

  const heading =
    status === 0
      ? "Backend unreachable"
      : status === 404
        ? `No ${resourceLabel} endpoint on the backend`
        : status === 403
          ? "Not authorized"
          : status === 422
            ? "The backend rejected the request"
            : status && status >= 500
              ? "Backend error"
              : `Could not load ${resourceLabel}`;

  return (
    <div
      role="alert"
      className="flex flex-col items-center justify-center gap-3 px-6 py-14 text-center"
    >
      <Icon className="size-6 text-destructive" aria-hidden />
      <div>
        <p className="font-display text-base font-semibold">{heading}</p>
        <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">{message}</p>
        {status ? <p className="mt-2 label-mono">HTTP {status}</p> : null}
      </div>
      {onRetry ? (
        <Button variant="outline" size="sm" onClick={onRetry}>
          Retry
        </Button>
      ) : null}
    </div>
  );
}
