import { StatusBadge } from "@/components/status-badge";
import { deriveStages, type StageResult } from "@/lib/gtm-api";

export function StageResults({ payload }: { payload: unknown }) {
  const stages = deriveStages(payload);
  if (stages.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        The response contained no recognizable stage results.
      </p>
    );
  }
  return (
    <ul className="space-y-2">
      {stages.map((stage) => (
        <StageRow key={stage.key} stage={stage} />
      ))}
    </ul>
  );
}

function StageRow({ stage }: { stage: StageResult }) {
  return (
    <li className="rounded-md border bg-card p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-medium">{stage.label}</p>
        <StatusBadge state={stage.state} />
      </div>
      {stage.message ? <p className="mt-1 text-sm text-muted-foreground">{stage.message}</p> : null}
      {stage.raw !== null && typeof stage.raw === "object" ? (
        <details className="mt-2">
          <summary className="cursor-pointer text-xs text-muted-foreground">Raw result</summary>
          <pre className="mt-2 max-h-64 overflow-auto rounded-md bg-muted p-3 font-mono text-xs">
            {JSON.stringify(stage.raw, null, 2)}
          </pre>
        </details>
      ) : null}
    </li>
  );
}

export function NotConfiguredCard({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div
      role="status"
      className="rounded-lg border border-warning/40 bg-warning/5 p-6"
    >
      <p className="text-base font-semibold text-warning">{title}</p>
      <p className="mt-1 max-w-xl text-sm text-muted-foreground">{description}</p>
    </div>
  );
}
