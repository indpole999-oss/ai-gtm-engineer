import { createFileRoute } from "@tanstack/react-router";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { Bot, Loader2, Play, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/page-header";
import { StatusBadge } from "@/components/status-badge";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "@/components/state-block";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { normalizeState, runAgent, type Json } from "@/lib/gtm-api";
import { useAgents } from "@/lib/gtm-queries";

export const Route = createFileRoute("/_authenticated/agents")({
  head: () => ({
    meta: [
      { title: "AI Agents — AI GTM Engineer" },
      { name: "description", content: "Research, enrichment, email, CRM and calendar agents registered on your backend." },
      { property: "og:title", content: "AI Agents — AI GTM Engineer" },
      { property: "og:description", content: "Research, enrichment, email, CRM and calendar agents." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: AgentsPage,
});

function AgentsPage() {
  const agents = useAgents();
  const [results, setResults] = useState<Record<string, { state: ReturnType<typeof normalizeState>; payload: Json; at: string }>>({});
  const [tasks, setTasks] = useState<Record<string, string>>({});

  const run = useMutation({
    mutationFn: async ({ agent, task }: { agent: string; task: string }) =>
      ({ agent, payload: (await runAgent({ agent, task })) as Json }),
    onSuccess: ({ agent, payload }) => {
      const state = normalizeState(payload["status"]);
      setResults((prev) => ({ ...prev, [agent]: { state, payload, at: new Date().toISOString() } }));
      if (state === "error") toast.error(`${agent} agent returned an error`);
      else if (state === "not_configured") toast.warning(`${agent} agent is not fully configured`);
      else toast.success(`${agent} agent finished`);
    },
    onError: (error: Error) => toast.error("Agent run failed", { description: error.message }),
  });

  const entries = Object.entries(agents.data?.agents ?? {});

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI Agents"
        description="Each agent is registered by the backend. Run one with a task to see exactly what it returns."
        actions={
          <Button variant="outline" size="sm" onClick={() => agents.refetch()} disabled={agents.isFetching}>
            <RefreshCw className={agents.isFetching ? "size-4 animate-spin" : "size-4"} aria-hidden />
            Refresh
          </Button>
        }
      />

      {agents.isPending ? (
        <div className="rounded-lg border bg-card">
          <LoadingBlock rows={4} />
        </div>
      ) : agents.isError ? (
        <div className="rounded-lg border bg-card">
          <ErrorBlock error={agents.error} resourceLabel="agents" onRetry={() => agents.refetch()} />
        </div>
      ) : entries.length === 0 ? (
        <div className="rounded-lg border bg-card">
          <EmptyBlock title="No agents registered" description="The backend returned an empty agent registry." />
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {entries.map(([name, description]) => {
            const result = results[name];
            return (
              <article key={name} className="rounded-lg border bg-card p-5 shadow-xs">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-3">
                    <span className="mt-0.5 flex size-8 items-center justify-center rounded-md bg-accent text-accent-foreground">
                      <Bot className="size-4" aria-hidden />
                    </span>
                    <div className="min-w-0">
                      <h2 className="text-sm font-semibold capitalize">{name.replace(/_/g, " ")} agent</h2>
                      <p className="mt-1 text-sm text-muted-foreground">{description}</p>
                    </div>
                  </div>
                  <StatusBadge state={result ? result.state : "success"} />
                </div>

                <div className="mt-4 space-y-1.5">
                  <Label htmlFor={`task-${name}`}>Task</Label>
                  <Textarea
                    id={`task-${name}`}
                    rows={2}
                    placeholder="Describe what this agent should do"
                    value={tasks[name] ?? ""}
                    onChange={(e) => setTasks((prev) => ({ ...prev, [name]: e.target.value }))}
                  />
                </div>

                <Button
                  size="sm"
                  className="mt-3"
                  disabled={!(tasks[name] ?? "").trim() || run.isPending}
                  onClick={() => run.mutate({ agent: name, task: tasks[name] ?? "" })}
                >
                  {run.isPending && run.variables?.agent === name ? (
                    <Loader2 className="size-4 animate-spin" aria-hidden />
                  ) : (
                    <Play className="size-4" aria-hidden />
                  )}
                  Run agent
                </Button>

                {result ? (
                  <div className="mt-4 rounded-md border bg-muted/40 p-3">
                    <p className="text-xs text-muted-foreground">
                      Last result ·{" "}
                      {new Date(result.at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}
                    </p>
                    <pre className="mt-2 max-h-56 overflow-auto font-mono text-xs">
                      {JSON.stringify(result.payload, null, 2)}
                    </pre>
                  </div>
                ) : (
                  <p className="mt-3 text-xs text-muted-foreground">No result yet in this session.</p>
                )}
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
