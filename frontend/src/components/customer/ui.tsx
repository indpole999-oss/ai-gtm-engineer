import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiFetch, ApiError } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace";

export function useData<T>(path: string, enabled = true) {
  const { workspace } = useWorkspace();
  return useQuery({
    queryKey: ["customer", workspace.id, path],
    queryFn: ({ signal }) => apiFetch<T>(path, { signal }),
    enabled,
    staleTime: 15000,
    // Only reads retry once after a transient transport/server failure. Mutations
    // retain their explicit review and server idempotency boundaries.
    retry: (failures, error) => failures < 1 && error instanceof ApiError && (error.status === 0 || error.status >= 500),
  });
}
export function Heading({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div>
        <p className="eyebrow">GAPS AI / YOUR GROWTH WORKSPACE</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight md:text-4xl">{title}</h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">{description}</p>
      </div>
      {action}
    </header>
  );
}
export function Panel({
  title,
  children,
  className = "",
}: {
  title?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`g-panel ${className}`}>
      {title && <h2 className="mb-4 text-lg font-semibold tracking-tight">{title}</h2>}
      {children}
    </section>
  );
}
export function Status({ value }: { value?: string | null | undefined }) {
  const label = value || "unknown";
  const tone = [
    "sent",
    "confirmed",
    "completed",
    "published",
    "healthy",
    "won",
    "available",
  ].includes(label)
    ? "good"
    : ["failed", "blocked", "suppressed", "unsubscribe", "lost", "conflict", "error"].includes(
          label,
        )
      ? "bad"
      : "neutral";
  return <span className={`g-status g-status-${tone}`}>{label.replaceAll("_", " ")}</span>;
}
export function Loading() {
  return (
    <div role="status" aria-label="Loading workspace data" className="grid gap-4 md:grid-cols-2">
      {[0, 1, 2, 3].map((n) => (
        <div key={n} className="g-panel h-40 animate-pulse">
          <div className="h-3 w-24 rounded bg-muted" />
          <div className="mt-6 h-6 w-3/4 rounded bg-muted" />
          <div className="mt-4 h-3 w-1/2 rounded bg-muted" />
        </div>
      ))}
      <span className="sr-only">Loading…</span>
    </div>
  );
}
export function Empty({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Panel>
      <div className="py-9 text-center">
        <div
          className="mx-auto mb-5 flex size-12 items-center justify-center rounded-2xl bg-accent text-primary"
          aria-hidden
        >
          ↗
        </div>
        <h2 className="text-xl font-semibold">{title}</h2>
        <div className="mx-auto mt-3 max-w-lg text-sm leading-6 text-muted-foreground">
          {children}
        </div>
      </div>
    </Panel>
  );
}
export function ErrorState({ retry, error }: { retry: () => void; error?: unknown }) {
  return (
    <div role="alert" className="g-panel">
      <h2 className="font-semibold">
        {error instanceof ApiError && error.status === 403
          ? "You don’t have access to this view"
          : "This view couldn’t load"}
      </h2>
      <p className="my-3 text-sm text-muted-foreground">
        Your saved work is safe. Check your access or try again.
      </p>
      <button className="g-button" onClick={retry}>
        Try again
      </button>
    </div>
  );
}
export function Feedback({ message }: { message: string }) {
  return message ? (
    <p role="status" className="rounded-xl border bg-accent p-4 text-sm">
      {message}
    </p>
  ) : null;
}
export function friendlyError(e: unknown) {
  return e instanceof ApiError && e.status < 500 && e.status > 0
    ? e.message
    : "We couldn’t complete that action. Your saved state has not been marked successful. Please try again.";
}
export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="grid gap-2 text-sm font-medium">
      {label}
      {children}
    </label>
  );
}
export function time(value?: string | null | undefined) {
  if (!value) return "Not confirmed";
  const parsed = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(value) ? value : value + "Z");
  return Number.isNaN(parsed.valueOf()) ? "Unknown date" : parsed.toLocaleString();
}
