import { Link } from "@tanstack/react-router";
import { ErrorState, Loading, Panel, time, useData } from "./ui";

type Operations = {
  as_of: string;
  plans: Record<string, number>;
  commands: Record<string, number>;
  alerts: string[];
  oldest_pending_approval_age_seconds: number | null;
  oldest_queued_age_seconds: number | null;
};
type Retention = {
  datasets: Record<string, { records: number; retention_days: number | null }>;
};
const alertLabels: Record<string, string> = {
  expired_leases:
    "Work stopped reporting progress. Ask your operator to inspect recovery before retrying.",
  failed_execution: "Some execution attempts failed. Review their saved status in Command Center.",
  queue_wait_exceeds_5_minutes:
    "Work has been queued for more than five minutes. Check worker availability.",
};
function age(seconds: number | null) {
  if (seconds === null) return "None waiting";
  const minutes = Math.floor(seconds / 60);
  return minutes < 1 ? "Less than a minute" : `${minutes} min`;
}

// Only mounted for owners/admins. The APIs independently enforce that boundary.
export function WorkspaceStatus() {
  const operations = useData<Operations>("/api/v1/operations");
  const retention = useData<Retention>("/api/v1/retention");
  return (
    <>
      <Panel title="Workspace activity">
        <p className="mb-4 text-sm text-muted-foreground">
          Saved execution and approval records for this workspace. This snapshot does not confirm
          worker availability, live delivery or provider health.
        </p>
        {operations.isPending ? (
          <Loading />
        ) : operations.isError ? (
          <ErrorState error={operations.error} retry={() => void operations.refetch()} />
        ) : (
          operations.data && (
            <>
              <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {[
                  ["Draft plans awaiting review", operations.data.plans["draft"] ?? 0],
                  ["Queued actions", operations.data.commands["queued"] ?? 0],
                  ["Running actions", operations.data.commands["running"] ?? 0],
                  ["Failed actions", operations.data.commands["failed"] ?? 0],
                  [
                    "Oldest draft awaiting review",
                    age(operations.data.oldest_pending_approval_age_seconds),
                  ],
                  ["Oldest queued action", age(operations.data.oldest_queued_age_seconds)],
                ].map(([label, value]) => (
                  <div key={label}>
                    <dt className="text-xs text-muted-foreground">{label}</dt>
                    <dd className="mt-1 text-lg font-medium">{value}</dd>
                  </div>
                ))}
              </dl>
              {operations.data.alerts.length > 0 && (
                <ul
                  className="mt-5 list-inside list-disc space-y-2 text-sm"
                  aria-label="Execution alerts"
                >
                  {operations.data.alerts.map((alert) => (
                    <li key={alert}>
                      {alertLabels[alert] ?? "An execution alert needs operator review."}
                    </li>
                  ))}
                </ul>
              )}
              <p className="mt-5 text-xs text-muted-foreground">
                Snapshot: {time(operations.data.as_of)}
              </p>
              <p className="mt-2 text-sm">
                Provider spend: unavailable. No billing ledger is connected.
              </p>
              <div className="mt-4 flex flex-wrap gap-3">
                <button
                  className="g-button g-button-secondary"
                  disabled={operations.isFetching}
                  onClick={() => void operations.refetch()}
                >
                  {operations.isFetching ? "Refreshing…" : "Refresh activity"}
                </button>
                <Link to="/dashboard" className="g-button">
                  Review plans and executions
                </Link>
              </div>
            </>
          )
        )}
      </Panel>
      <Panel title="Data retention decisions">
        <p className="text-sm">
          Retention durations for customer evidence, inbox content, audit records and backups
          require approval before release. No automatic purge is enabled. Deletion is blocked when
          it would break evidence, audit history or required relationships.
        </p>
        {retention.isPending ? (
          <Loading />
        ) : retention.isError ? (
          <ErrorState error={retention.error} retry={() => void retention.refetch()} />
        ) : (
          retention.data && (
            <dl className="mt-4 grid gap-4 sm:grid-cols-2">
              {[
                ["customer_evidence", "Evidence records"],
                ["inbox_content", "Inbox records"],
                ["execution_audit", "Execution audit records"],
                ["suppression", "Suppression records"],
              ].map(([key, label]) => (
                <div key={key}>
                  <dt className="text-xs text-muted-foreground">{label}</dt>
                  <dd className="mt-1">
                    {retention.data?.datasets[key!]?.records ?? "Unavailable"}
                  </dd>
                </div>
              ))}
            </dl>
          )
        )}
        <p className="mt-4 text-xs text-muted-foreground">
          Backup inventory is managed separately by the operator. These counts are not proof of
          backup recovery or legal compliance.
        </p>
      </Panel>
    </>
  );
}
