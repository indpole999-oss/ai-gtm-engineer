import { useState } from "react";
import { Link } from "@tanstack/react-router";
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
      useData<{ id: string; plan_id: string; status: string; stop_reason: string | null }[]>("/api/v1/gtm/cycles"),
    integrations = useData<{ integrations: Integration[] }>("/api/v1/integrations"),
    insights = useData<Insights>(
      `/api/v1/insights?start=${encodeURIComponent(range.start)}&end=${encodeURIComponent(range.end)}&entity_type=contact`,
    );
  const active = cycles.data?.find((c) => ["running", "paused"].includes(c.status));
  const goal = goals.data?.[0];
  const plans = useData<{ id: string; status: string }[]>(`/api/v1/gtm/goals/${goal?.id}/plans`, Boolean(goal));
  const latestPlan = plans.data?.[0];
  const goalCycle = cycles.data?.find(c => c.plan_id === latestPlan?.id);
  const published = brains.data?.versions.find((v) => v.status === "published");
  const currentBrain = brains.data?.versions.find((v) => v.id === goal?.brain_version_id);
  const next = !published
    ? {
        text: "Give your GTM work the right foundation.",
        action: "Set up Company Brain",
        to: "/settings" as const,
      }
    : !goal
      ? {
          text: "A clear goal is your next step.",
          action: "Add target accounts",
          to: "/prospects" as const,
        }
      : {
          text: active?.stop_reason
            ? "Your execution needs attention. Review the blocker below."
            : "Review your saved plan and choose the next step.",
          action: "Explore your prospects",
          to: "/prospects" as const,
        };
  return (
    <>
      <Heading
        title="Your GTM, in focus."
        description="From a clear goal to an evidence-backed conversation. A considered next step, always under your control."
      />
      {goals.isPending || brains.isPending || cycles.isPending ? (
        <Loading />
      ) : goals.isError || brains.isError || cycles.isError ? (
        <ErrorState
          retry={() => {
            void goals.refetch();
            void brains.refetch();
            void cycles.refetch();
          }}
        />
      ) : (
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
          <Panel className="bg-primary text-primary-foreground">
            <p className="text-xs tracking-widest opacity-70">LATEST GOAL</p>
            <h2 className="mt-5 max-w-2xl text-2xl font-medium leading-snug md:text-3xl">
              {goal?.objective || "Build a pipeline with purpose."}
            </h2>
            <p className="mt-5 text-sm opacity-80">
              {goal
                ? `Company Brain ${currentBrain ? `version ${currentBrain.number}` : "version unavailable"} · Review required before execution`
                : "Start with your Company Brain, choose an account, and prepare a plan."}
            </p>
            <div className="mt-7">
              <Status value={!goal ? "no_goal" : plans.isPending ? "loading" : plans.isError ? "unavailable" : goalCycle?.status || latestPlan?.status || "no_saved_plan"} />
            </div>
          </Panel>
          <Panel title="Your next move">
            <p className="text-sm leading-7 text-muted-foreground">{next.text}</p>
            <Link to={next.to} className="g-button mt-6">
              {next.action} ↗
            </Link>
            <p className="mt-5 text-xs text-muted-foreground">
              Recommendations are informational. Only explicit approvals authorize execution.
            </p>
          </Panel>
        </div>
      )}
      <div className="grid gap-4 md:grid-cols-3">
        <Panel title="Company Brain">
          <Status
            value={
              brains.isPending
                ? "loading"
                : brains.isError
                  ? "unavailable"
                  : published
                    ? "published"
                    : "setup_needed"
            }
          />
          <p className="mt-3 text-sm text-muted-foreground">
            {published
              ? `Version ${published.number} is ready for new plans.`
              : "Publish your reviewed company context to begin."}
          </p>
          <Link to="/settings" className="mt-4 block text-sm font-semibold text-primary">
            Review company context →
          </Link>
        </Panel>
        <Panel title="Connections">
          <Status
            value={
              integrations.isPending
                ? "loading"
                : integrations.isError
                  ? "unavailable"
                  : integrations.data?.integrations.some((i) => i.reconnect_required)
                    ? "reconnect_required"
                    : integrations.data?.integrations.some((i) => i.health === "healthy")
                      ? "healthy"
                      : "setup_needed"
            }
          />
          <p className="mt-3 text-sm text-muted-foreground">
            {integrations.data?.integrations.filter((i) => i.health === "healthy").length ?? "—"}{" "}
            provider-reported healthy connections
          </p>
          <Link to="/integrations" className="mt-4 block text-sm font-semibold text-primary">
            Manage integrations →
          </Link>
        </Panel>
        <Panel title="Execution">
          <Status
            value={
              cycles.isPending
                ? "loading"
                : cycles.isError
                  ? "unavailable"
                  : active?.status || cycles.data?.[0]?.status || "no_execution"
            }
          />
          <p className="mt-3 text-sm text-muted-foreground">
            {active?.stop_reason?.replaceAll("_", " ") ||
              "Review saved plans below. Approval is separate from a successful outcome."}
          </p>
        </Panel>
      </div>
      <GtmCommandCenter />
      <section className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-xl font-semibold">Measured progress</h2>
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
              <p className="text-xs text-muted-foreground">
                Last 30 days · contact pipelines discovered in this period · outcomes observed
                through {new Date(range.end).toLocaleString()}
              </p>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {[
                  ["Qualified contacts", insights.data.funnel.observed_stage_entries["qualified"]],
                  ["Confirmed sends", insights.data.metrics.outreach.sent],
                  ["Human replies", insights.data.metrics.outreach.reply.numerator],
                  ["Opportunities", insights.data.funnel.observed_stage_entries["opportunity"]],
                ].map(([label, value]) => (
                  <Panel key={label}>
                    <p className="text-sm text-muted-foreground">{label}</p>
                    <p className="mt-3 text-3xl font-semibold">{value}</p>
                  </Panel>
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
