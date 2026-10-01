import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { Activity, Brain, Plug, Sparkles } from "lucide-react";
import { GtmCommandCenter } from "@/components/gtm-command-center";
import { Heading, Panel, Status, Loading, ErrorState, useData } from "./ui";
import type { Insights, Integration } from "./contracts";
import { RecommendationCard } from "./insights";

export function DashboardPage() {
  const [range] = useState(() => ({
    start: new Date(Date.now() - 30 * 86400000).toISOString(),
    end: new Date().toISOString(),
  }));

  const goals =
      useData<{ id: string; objective: string; brain_version_id: string }[]>("/api/v1/gtm/goals"),
    brains = useData<{ versions: { id: string; number: number; status: string }[] }>(
      "/api/v1/company-brain",
    ),
    cycles =
      useData<{ id: string; plan_id: string; status: string; stop_reason: string | null }[]>(
        "/api/v1/gtm/cycles",
      ),
    integrations = useData<{ integrations: Integration[] }>("/api/v1/integrations"),
    insights = useData<Insights>(
      `/api/v1/insights?start=${encodeURIComponent(range.start)}&end=${encodeURIComponent(range.end)}&entity_type=contact`,
    );

  const active = cycles.data?.find((c) => ["running", "paused"].includes(c.status));
  const goal = goals.data?.[0];
  const plans = useData<{ id: string; status: string }[]>(
    `/api/v1/gtm/goals/${goal?.id}/plans`,
    Boolean(goal),
  );
  const latestPlan = plans.data?.[0];
  const goalCycle = cycles.data?.find((c) => c.plan_id === latestPlan?.id);
  const published = brains.data?.versions.find((v) => v.status === "published");
  const currentBrain = brains.data?.versions.find((v) => v.id === goal?.brain_version_id);
  const healthyConnections =
    integrations.data?.integrations.filter((i) => i.health === "healthy").length ?? 0;

  const next = !published
    ? {
        text: "Your AI GTM employee needs your business context before it can plan safely.",
        action: "Set up Company Brain",
        to: "/settings" as const,
      }
    : !goal
      ? {
          text: "Give your AI GTM employee one clear GTM goal to work toward.",
          action: "Add target accounts",
          to: "/prospects" as const,
        }
      : {
          text: active?.stop_reason
            ? "Execution needs your attention before the next step can continue."
            : "Your plan is ready for review. You stay in control before anything external happens.",
          action: "Review prospects",
          to: "/prospects" as const,
        };

  const isLoading = goals.isPending || brains.isPending || cycles.isPending;
  const hasError = goals.isError || brains.isError || cycles.isError;

  return (
    <>
      <Heading
        eyebrow="AI EMPLOYEE ACTIVE"
        title="Good afternoon, Anil"
        description="Direct your AI GTM employee, review what it plans, and keep control over every customer-facing action."
      />

      {isLoading ? (
        <Loading />
      ) : hasError ? (
        <ErrorState
          retry={() => {
            void goals.refetch();
            void brains.refetch();
            void cycles.refetch();
          }}
        />
      ) : (
        <>
          <section className="g-command-surface p-3 sm:p-4">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
              <div className="flex size-9 shrink-0 items-center justify-center rounded-[10px] border border-primary/10 bg-primary/10 text-primary">
                <Sparkles className="size-[17px]" strokeWidth={1.8} />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-[11px] font-semibold uppercase tracking-[.08em] text-muted-foreground">
                  Current goal
                </p>
                <p className="mt-1 text-[15px] font-medium text-foreground">
                  {goal?.objective || "What should your AI GTM employee do next?"}
                </p>
              </div>
              <Link to="/prospects" className="g-button shrink-0">
                {goal ? "Review goal" : "Create goal"}
              </Link>
            </div>
          </section>

          <section className="g-quiet-strip">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[.08em] text-muted-foreground">
                Company Brain
              </p>
              <p className="mt-1 text-xs font-medium text-foreground">
                {published ? `Version ${published.number} published` : "Setup needed"}
              </p>
            </div>
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[.08em] text-muted-foreground">
                Active goal
              </p>
              <p className="mt-1 truncate text-xs font-medium text-foreground">
                {goal?.objective || "No goal yet"}
              </p>
            </div>
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[.08em] text-muted-foreground">
                AI status
              </p>
              <p className="mt-1 text-xs font-medium text-primary">
                {active?.status || goalCycle?.status || latestPlan?.status || "Ready for direction"}
              </p>
            </div>
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[.08em] text-muted-foreground">
                Integrations
              </p>
              <p className="mt-1 text-xs font-medium text-foreground">
                {integrations.isPending
                  ? "Checking…"
                  : integrations.isError
                    ? "Unavailable"
                    : `${healthyConnections} healthy`}
              </p>
            </div>
          </section>

          <div className="grid gap-8 xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,.85fr)]">
            <section>
              <div className="mb-4 flex items-center gap-2">
                <Activity className="size-4 text-primary" />
                <h2 className="text-lg font-semibold">Today</h2>
              </div>
              <div className="divide-y divide-border border-y border-border">
                {[
                  [
                    "Company context",
                    published
                      ? `Company Brain version ${published.number} is ready for planning.`
                      : "Company Brain still needs to be published.",
                    published ? "Ready" : "Review",
                  ],
                  [
                    "Goal and plan",
                    goal
                      ? currentBrain
                        ? `Goal is anchored to Company Brain version ${currentBrain.number}.`
                        : "Goal exists, but the linked Company Brain version is unavailable."
                      : "No active GTM goal has been created yet.",
                    goal ? latestPlan?.status || "Goal saved" : "Next",
                  ],
                  [
                    "Execution",
                    active?.stop_reason
                      ? active.stop_reason.replaceAll("_", " ")
                      : active
                        ? "An execution cycle is currently active."
                        : "No active execution cycle. Review a plan when you are ready.",
                    active?.status || "Idle",
                  ],
                  [
                    "Connected tools",
                    integrations.isError
                      ? "Integration health is temporarily unavailable."
                      : `${healthyConnections} provider-reported healthy connections.`,
                    integrations.isError ? "Check" : "Connected",
                  ],
                ].map(([title, body, state]) => (
                  <div key={title} className="g-list-row grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
                    <div>
                      <p className="text-sm font-medium text-foreground">{title}</p>
                      <p className="mt-1 text-xs leading-5 text-muted-foreground">{body}</p>
                    </div>
                    <Status value={state} />
                  </div>
                ))}
              </div>
            </section>

            <section className="space-y-5">
              <Panel title="Current goal">
                <p className="text-[10px] font-semibold uppercase tracking-[.09em] text-muted-foreground">
                  GOAL
                </p>
                <p className="mt-3 text-[15px] font-medium leading-6 text-foreground">
                  {goal?.objective || "No goal has been created yet."}
                </p>
                <div className="mt-5 h-1 overflow-hidden rounded-full bg-secondary">
                  <div
                    className="h-full rounded-full bg-primary"
                    style={{ width: goal ? (latestPlan ? "68%" : "34%") : "8%" }}
                  />
                </div>
                <p className="mt-4 text-xs leading-5 text-muted-foreground">{next.text}</p>
                <Link to={next.to} className="g-button mt-5 w-full">
                  {next.action}
                </Link>
              </Panel>

              <div>
                <h2 className="text-lg font-semibold">Attention</h2>
                <div className="mt-3 divide-y divide-border border-y border-border">
                  <Link to="/settings" className="g-list-row flex items-center gap-3">
                    <Brain className="size-4 shrink-0 text-muted-foreground" />
                    <span className="min-w-0 flex-1 text-sm">
                      {published ? "Company Brain is published" : "Publish Company Brain"}
                    </span>
                    <span className="text-xs font-semibold text-primary">Review</span>
                  </Link>
                  <Link to="/integrations" className="g-list-row flex items-center gap-3">
                    <Plug className="size-4 shrink-0 text-muted-foreground" />
                    <span className="min-w-0 flex-1 text-sm">
                      {healthyConnections
                        ? `${healthyConnections} healthy integrations`
                        : "Connect your GTM tools"}
                    </span>
                    <span className="text-xs font-semibold text-primary">Review</span>
                  </Link>
                </div>
              </div>
            </section>
          </div>
        </>
      )}

      <GtmCommandCenter />

      <section className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="eyebrow">MEASURED PROGRESS</p>
            <h2 className="mt-2 text-xl font-semibold">What your GTM system is learning</h2>
          </div>
          <Link to="/insights" className="text-sm font-semibold text-primary">
            Explore insights →
          </Link>
        </div>

        {insights.isPending ? (
          <Loading />
        ) : insights.isError ? (
          <ErrorState error={insights.error} retry={() => void insights.refetch()} />
        ) : (
          insights.data && (
            <>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {[
                  ["Qualified contacts", insights.data.funnel.observed_stage_entries["qualified"]],
                  ["Confirmed sends", insights.data.metrics.outreach.sent],
                  ["Human replies", insights.data.metrics.outreach.reply.numerator],
                  ["Opportunities", insights.data.funnel.observed_stage_entries["opportunity"]],
                ].map(([label, value]) => (
                  <div key={label} className="g-kpi py-2 first:border-l-0 first:pl-0">
                    <p className="text-[10px] font-semibold uppercase tracking-[.08em] text-muted-foreground">
                      {label}
                    </p>
                    <p className="mt-2 text-2xl font-semibold text-foreground">{value}</p>
                  </div>
                ))}
              </div>

              {insights.data.recommendations[0] && (
                <RecommendationCard
                  item={
                    insights.data.recommendations.find((r) => r.status === "observed_gap") ||
                    insights.data.recommendations[0]
                  }
                />
              )}
            </>
          )
        )}
      </section>
    </>
  );
}
