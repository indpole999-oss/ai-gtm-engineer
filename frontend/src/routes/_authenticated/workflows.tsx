
import { createFileRoute } from "@tanstack/react-router";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { Loader2, Play, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/page-header";
import { StatusBadge } from "@/components/status-badge";
import { StageResults } from "@/components/stage-results";
import { ConfirmDialog } from "@/components/confirm-dialog";
import {
  EmptyBlock,
  ErrorBlock,
  LoadingBlock,
} from "@/components/state-block";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  deriveStages,
  normalizeState,
  runWorkflow,
  type Json,
} from "@/lib/gtm-api";
import { rows, text, useWorkflows } from "@/lib/gtm-queries";

export const Route = createFileRoute("/_authenticated/workflows")({
  head: () => ({
    meta: [
      { title: "Workflows — AI GTM Engineer" },
      {
        name: "description",
        content:
          "Run the lead pipeline and email sequence workflows and inspect every stage.",
      },
      {
        property: "og:title",
        content: "Workflows — AI GTM Engineer",
      },
      {
        property: "og:description",
        content: "Run GTM workflows and inspect every stage.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: WorkflowsPage,
});

type Row = Record<string, unknown>;

interface RunRecord {
  workflow: string;
  finishedAt: string;
  payload: Json;
  overall: ReturnType<typeof normalizeState>;
}

function overallState(payload: Json) {
  const stages = deriveStages(payload);

  if (stages.some((s) => s.state === "error")) {
    return "error" as const;
  }

  const explicit = normalizeState(payload["status"]);

  if (explicit === "error") {
    return "error" as const;
  }

  if (stages.some((s) => s.state === "not_configured")) {
    return "warning" as const;
  }

  if (
    stages.some(
      (s) => s.state === "skipped" || s.state === "warning",
    )
  ) {
    return "warning" as const;
  }

  if (stages.length === 0 && explicit === "unknown") {
    return "unknown" as const;
  }

  return explicit === "unknown"
    ? ("success" as const)
    : explicit;
}

function WorkflowsPage() {
  const workflows = useWorkflows();

  const [companyName, setCompanyName] = useState("");
  const [domain, setDomain] = useState("");
  const [recipientEmail, setRecipientEmail] = useState("");
  const [startTime, setStartTime] = useState("");

  const [pendingRun, setPendingRun] = useState<string | null>(null);
  const [history, setHistory] = useState<RunRecord[]>(() => { if (typeof window === "undefined") return []; try { const saved = localStorage.getItem("gtm_workflow_history"); return saved ? (JSON.parse(saved) as RunRecord[]) : []; } catch { return []; } });

  const workflowRows = rows(workflows.data);

  const names =
    workflowRows.length > 0
      ? workflowRows.map((r) =>
          text(r, ["name", "workflow_name", "id"], ""),
        )
      : workflows.data &&
          typeof workflows.data === "object"
        ? Object.keys(
            (workflows.data as Json)["workflows"] &&
              typeof (workflows.data as Json)["workflows"] ===
                "object"
              ? ((workflows.data as Json)["workflows"] as Json)
              : {},
          )
        : [];

  const run = useMutation({
    mutationFn: async (name: string) => {
      const normalizedCompany = companyName.trim();
      const normalizedDomain = domain.trim();
      const normalizedEmail = recipientEmail.trim();
      const normalizedStartTime = startTime.trim();

      if (!normalizedCompany) {
        throw new Error("Company name is required.");
      }

      if (!normalizedDomain) {
        throw new Error("Domain is required.");
      }

      if (name === "email_sequence" && !normalizedEmail) {
        throw new Error(
          "Recipient email is required for email sequence.",
        );
      }

      if (name === "lead_pipeline" && !normalizedStartTime) {
        throw new Error(
          "Meeting start time is required for the lead pipeline.",
        );
      }

      const parsed: Json = {
        company_name: normalizedCompany,
        domain: normalizedDomain,
        ...(normalizedEmail
          ? { email: normalizedEmail }
          : {}),
        ...(normalizedStartTime
          ? { start_time: normalizedStartTime }
          : {}),
      };

      const payload = (await runWorkflow(name, parsed)) as Json;

      return {
        name,
        payload,
      };
    },

    onSuccess: ({ name, payload }) => {
      const overall = overallState(payload);

      setHistory((prev) => [
        {
          workflow: name,
          finishedAt: new Date().toISOString(),
          payload,
          overall,
        },
        ...prev,
      ].slice(0, 10));

      if (overall === "error") {
        toast.error(`${name} finished with errors`);
      } else if (overall === "warning") {
        toast.warning(
          `${name} finished with warnings or skipped stages`,
        );
      } else {
        toast.success(`${name} completed`);
      }
    },

    onError: (error: Error) => {
      toast.error("Workflow run failed", {
        description: error.message,
      });
    },
  });

  const workflowCards: Row[] =
    workflowRows.length > 0
      ? workflowRows
      : names.map((name) => ({ name }));

  return (
    <div className="space-y-6">
      <PageHeader
        title="Workflows"
        description="Orchestrated multi-agent runs. HTTP 200 does not mean every stage succeeded — check each stage below."
        actions={
          <Button
            variant="outline"
            size="sm"
            onClick={() => workflows.refetch()}
            disabled={workflows.isFetching}
          >
            <RefreshCw
              className={
                workflows.isFetching
                  ? "size-4 animate-spin"
                  : "size-4"
              }
              aria-hidden
            />
            Refresh
          </Button>
        }
      />

      <section className="rounded-lg border bg-card p-5 shadow-xs">
        <div className="grid gap-4 md:grid-cols-4">
          <div>
            <Label htmlFor="company-name">
              Company Name *
            </Label>

            <Input
              id="company-name"
              className="mt-1.5"
              value={companyName}
              onChange={(e) =>
                setCompanyName(e.target.value)
              }
              placeholder="OpenAI"
            />
          </div>

          <div>
            <Label htmlFor="domain">
              Domain *
            </Label>

            <Input
              id="domain"
              className="mt-1.5"
              value={domain}
              onChange={(e) =>
                setDomain(e.target.value)
              }
              placeholder="openai.com"
            />
          </div>

          <div>
            <Label htmlFor="recipient-email">
              Recipient Email
            </Label>

            <Input
              id="recipient-email"
              type="email"
              className="mt-1.5"
              value={recipientEmail}
              onChange={(e) =>
                setRecipientEmail(e.target.value)
              }
              placeholder="prospect@company.com"
            />
          </div>

          <div>
            <Label htmlFor="start-time">
              Meeting Start Time *
            </Label>

            <Input
              id="start-time"
              type="datetime-local"
              className="mt-1.5"
              value={startTime}
              onChange={(e) =>
                setStartTime(e.target.value)
              }
            />
          </div>
        </div>

        <p className="mt-2 text-xs text-muted-foreground">
          Company name and domain are used for research and
          enrichment. Recipient email is optional for the lead
          pipeline because enrichment can discover a contact
          email. Email sequence requires a recipient email.
          Meeting start time is required for Calendar booking.
        </p>
      </section>

      {workflows.isPending ? (
        <div className="rounded-lg border bg-card">
          <LoadingBlock rows={3} />
        </div>
      ) : workflows.isError ? (
        <div className="rounded-lg border bg-card">
          <ErrorBlock
            error={workflows.error}
            resourceLabel="workflows"
            onRetry={() => workflows.refetch()}
          />
        </div>
      ) : workflowCards.length === 0 ? (
        <div className="rounded-lg border bg-card">
          <EmptyBlock
            title="No workflows registered"
            description="The backend did not return any workflow definitions."
          />
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {workflowCards.map((wf, i) => {
            const name = text(
              wf,
              ["name", "workflow_name", "id"],
              `workflow-${i}`,
            );

            const last = history.find(
              (h) => h.workflow === name,
            );

            return (
              <article
                key={name}
                className="rounded-lg border bg-card p-5 shadow-xs"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h2 className="truncate text-sm font-semibold capitalize">
                      {name.replace(/_/g, " ")}
                    </h2>

                    <p className="mt-1 text-sm text-muted-foreground">
                      {text(
                        wf,
                        ["description", "summary"],
                        "Multi-stage GTM workflow.",
                      )}
                    </p>
                  </div>

                  <StatusBadge
                    state={
                      last
                        ? last.overall
                        : "unknown"
                    }
                  />
                </div>

                <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  <span>
                    Last run:{" "}
                    {last
                      ? new Date(
                          last.finishedAt,
                        ).toLocaleString(
                          undefined,
                          {
                            dateStyle: "medium",
                            timeStyle: "short",
                          },
                        )
                      : "Not run in this session"}
                  </span>
                </div>

                <Button
                  className="mt-4"
                  size="sm"
                  disabled={run.isPending}
                  onClick={() =>
                    setPendingRun(name)
                  }
                >
                  {run.isPending &&
                  run.variables === name ? (
                    <Loader2
                      className="size-4 animate-spin"
                      aria-hidden
                    />
                  ) : (
                    <Play
                      className="size-4"
                      aria-hidden
                    />
                  )}

                  Run workflow
                </Button>

                {last ? (
                  <div className="mt-4 space-y-2">
                    <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      Stage results
                    </p>

                    <StageResults
                      payload={last.payload}
                    />
                  </div>
                ) : null}
              </article>
            );
          })}
        </div>
      )}

      <section className="space-y-3">
        <h2 className="text-sm font-semibold">
          Recent runs (this session)
        </h2>

        {history.length === 0 ? (
          <div className="rounded-lg border bg-card">
            <EmptyBlock
              title="No runs yet"
              description="Workflow executions you trigger here are listed with their per-stage outcome."
            />
          </div>
        ) : (
          <ul className="space-y-2">
            {history.map((h, i) => (
              <li
                key={i}
                className="flex flex-wrap items-center justify-between gap-2 rounded-lg border bg-card px-4 py-3"
              >
                <div>
                  <p className="text-sm font-medium capitalize">
                    {h.workflow.replace(
                      /_/g,
                      " ",
                    )}
                  </p>

                  <p className="text-xs text-muted-foreground">
                    {new Date(
                      h.finishedAt,
                    ).toLocaleString(
                      undefined,
                      {
                        dateStyle: "medium",
                        timeStyle: "short",
                      },
                    )}
                  </p>
                </div>

                <StatusBadge state={h.overall} />
              </li>
            ))}
          </ul>
        )}
      </section>

      <ConfirmDialog
        open={pendingRun !== null}
        onOpenChange={(open) =>
          !open && setPendingRun(null)
        }
        title="Run this workflow?"
        description="The workflow executes live agents on your backend and may contact external systems."
        confirmLabel="Run"
        onConfirm={() => {
          if (pendingRun) {
            run.mutate(pendingRun);
          }

          setPendingRun(null);
        }}
      />
    </div>
  );
}
