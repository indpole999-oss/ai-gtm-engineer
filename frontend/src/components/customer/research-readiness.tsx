import { ErrorState } from "./ui";

import { useResearchReadiness } from "./research-provider";

export function ResearchReadinessNotice() {
  const readiness = useResearchReadiness();
  return (
    <div className="g-panel-subtle space-y-2" aria-label="Research provider availability">
      <p className="text-sm font-medium">Research provider</p>
      {readiness.isPending ? (
        <p>Checking availability…</p>
      ) : readiness.isError ? (
        <ErrorState error={readiness.error} retry={() => void readiness.refetch()} />
      ) : (
        <p className="text-sm">
          {readiness.data?.message} Guided plans can still be saved for review. Approval queues work
          for a durable worker; it does not start or enable a provider.
        </p>
      )}
      <button
        className="text-sm text-primary underline"
        disabled={readiness.isFetching}
        onClick={() => void readiness.refetch()}
      >
        Refresh provider check
      </button>
    </div>
  );
}
