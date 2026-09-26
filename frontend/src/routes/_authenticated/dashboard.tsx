import { createFileRoute, Link } from "@tanstack/react-router";
import {
  Bot,
  Building2,
  CalendarDays,
  Mail,
  RefreshCw,
  Target,
  Users,
  Workflow as WorkflowIcon,
} from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { GtmCommandCenter } from "@/components/gtm-command-center";
import { StatCard } from "@/components/stat-card";
import { StatusBadge } from "@/components/status-badge";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "@/components/state-block";
import { Button } from "@/components/ui/button";
import { formatValue } from "@/lib/format";
import { normalizeState } from "@/lib/gtm-api";
import {
  rows,
  text,
  useAgents,
  useCompanies,
  useContacts,
  useEmails,
  useHealth,
  useLeads,
  useMeetings,
  useWorkflows,
} from "@/lib/gtm-queries";

export const Route = createFileRoute("/_authenticated/dashboard")({
  head: () => ({
    meta: [
      { title: "Dashboard — AI GTM Engineer" },
      {
        name: "description",
        content: "GTM command center: leads, companies, contacts, workflows, email activity and agent status.",
      },
      { property: "og:title", content: "Dashboard — AI GTM Engineer" },
      { property: "og:description", content: "Your GTM command center powered by AI agents." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: DashboardPage,
});

type Row = Record<string, unknown>;

function isQualified(row: Row) {
  const status = String(row["status"] ?? row["stage"] ?? "").toLowerCase();
  if (status.includes("qualified") && !status.includes("un")) return true;
  const score = Number(row["score"] ?? row["lead_score"] ?? NaN);
  return Number.isFinite(score) && score >= 70;
}

function recent(list: Row[], keys: string[]) {
  const sortValue = (row: Row) => {
    for (const key of keys) {
      const v = row[key];
      if (v !== undefined && v !== null && v !== "") return String(v);
    }
    return "";
  };
  return [...list].sort((a, b) => sortValue(b).localeCompare(sortValue(a))).slice(0, 5);
}

function DashboardPage() {
  const leads = useLeads();
  const companies = useCompanies();
  const contacts = useContacts();
  const emails = useEmails();
  const workflows = useWorkflows();
  const agents = useAgents();
  const meetings = useMeetings();
  const health = useHealth();

  const leadRows = rows(leads.data);
  const emailRows = rows(emails.data);
  const workflowRows = rows(workflows.data);
  const agentEntries = Object.entries(agents.data?.agents ?? {});

  const refreshAll = () => {
    void leads.refetch();
    void companies.refetch();
    void contacts.refetch();
    void emails.refetch();
    void workflows.refetch();
    void agents.refetch();
    void meetings.refetch();
    void health.refetch();
  };

  const anyFetching =
    leads.isFetching || companies.isFetching || contacts.isFetching || emails.isFetching || workflows.isFetching;

  return (
    <div className="space-y-6">
      <GtmCommandCenter />
      <PageHeader
        title="Dashboard"
        description="Live counts and activity straight from your GTM backend. Nothing here is simulated."
        actions={
          <Button variant="outline" size="sm" onClick={refreshAll} disabled={anyFetching}>
            <RefreshCw className={anyFetching ? "size-4 animate-spin" : "size-4"} aria-hidden />
            Refresh
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Total leads"
          value={leadRows.length}
          icon={Target}
          to="/leads"
          loading={leads.isPending}
          error={leads.error}
        />
        <StatCard
          label="Qualified leads"
          value={leadRows.filter(isQualified).length}
          hint="Status qualified or score ≥ 70"
          icon={Target}
          loading={leads.isPending}
          error={leads.error}
        />
        <StatCard
          label="Companies"
          value={rows(companies.data).length}
          icon={Building2}
          to="/companies"
          loading={companies.isPending}
          error={companies.error}
        />
        <StatCard
          label="Contacts"
          value={rows(contacts.data).length}
          icon={Users}
          to="/contacts"
          loading={contacts.isPending}
          error={contacts.error}
        />
        <StatCard
          label="Workflows"
          value={workflowRows.length}
          icon={WorkflowIcon}
          to="/workflows"
          loading={workflows.isPending}
          error={workflows.error}
        />
        <StatCard
          label="Email activity"
          value={emailRows.length}
          hint="Records returned by the email API"
          icon={Mail}
          to="/sequences"
          loading={emails.isPending}
          error={emails.error}
        />
        <StatCard
          label="AI agents"
          value={agentEntries.length}
          icon={Bot}
          to="/agents"
          loading={agents.isPending}
          error={agents.error}
        />
        <StatCard
          label="Meetings"
          value={rows(meetings.data).length}
          icon={CalendarDays}
          to="/calendar"
          loading={meetings.isPending}
          error={meetings.error}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel
          title="Recent leads"
          linkTo="/leads"
          query={leads}
          resourceLabel="leads"
          items={recent(leadRows, ["created_at", "updated_at"])}
          renderItem={(row, i) => (
            <li key={i} className="flex items-center justify-between gap-3 border-b px-4 py-3 last:border-0">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">
                  {text(row, ["name", "full_name", "contact_name", "email", "id"])}
                </p>
                <p className="truncate text-xs text-muted-foreground">
                  {text(row, ["company", "company_name", "domain"], "No company")}
                </p>
              </div>
              <StatusBadge value={text(row, ["status", "stage"], "unknown")} />
            </li>
          )}
          emptyTitle="No leads yet"
          emptyDescription="Leads created through the backend will appear here."
        />

        <Panel
          title="Email activity"
          linkTo="/sequences"
          query={emails}
          resourceLabel="email activity"
          items={recent(emailRows, ["created_at", "sent_at"])}
          renderItem={(row, i) => (
            <li key={i} className="flex items-center justify-between gap-3 border-b px-4 py-3 last:border-0">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">{text(row, ["subject", "title"], "Untitled email")}</p>
                <p className="truncate text-xs text-muted-foreground">
                  {formatValue("created_at", row["created_at"] ?? row["sent_at"] ?? null)}
                </p>
              </div>
              <StatusBadge value={text(row, ["status", "state"], "unknown")} />
            </li>
          )}
          emptyTitle="No email activity"
          emptyDescription="Generated or sent emails will be listed here."
        />

        <Panel
          title="Workflows"
          linkTo="/workflows"
          query={workflows}
          resourceLabel="workflows"
          items={workflowRows.slice(0, 5)}
          renderItem={(row, i) => (
            <li key={i} className="flex items-center justify-between gap-3 border-b px-4 py-3 last:border-0">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium capitalize">
                  {text(row, ["name", "workflow_name", "id"]).replace(/_/g, " ")}
                </p>
                <p className="truncate text-xs text-muted-foreground">
                  {text(row, ["description", "summary"], "Multi-stage workflow")}
                </p>
              </div>
              <StatusBadge state={normalizeState(row["status"] ?? "available")} />
            </li>
          )}
          emptyTitle="No workflows registered"
          emptyDescription="The backend has not registered any workflows."
        />

        <Panel
          title="AI agents"
          linkTo="/agents"
          query={agents}
          resourceLabel="agents"
          items={agentEntries.map(([name, description]) => ({ name, description }))}
          renderItem={(row, i) => (
            <li key={i} className="flex items-center justify-between gap-3 border-b px-4 py-3 last:border-0">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium capitalize">{String(row["name"]).replace(/_/g, " ")}</p>
                <p className="truncate text-xs text-muted-foreground">{String(row["description"])}</p>
              </div>
              <StatusBadge state="success" />
            </li>
          )}
          emptyTitle="No agents"
          emptyDescription="The agent registry is empty."
        />
      </div>

      <section className="rounded-lg border bg-card p-5 shadow-xs">
        <h2 className="text-sm font-semibold">Backend health</h2>
        {health.isPending ? (
          <LoadingBlock rows={1} />
        ) : health.isError ? (
          <p className="mt-2 text-sm text-destructive">
            The backend health endpoint is unreachable. Check the API base URL in Settings.
          </p>
        ) : (
          <div className="mt-3 flex flex-wrap gap-2">
            {Object.entries(health.data ?? {}).map(([key, value]) =>
              value !== null && typeof value === "object" ? null : (
                <span key={key} className="inline-flex items-center gap-2 rounded-md border px-2.5 py-1 text-xs">
                  <span className="text-muted-foreground">{key.replace(/_/g, " ")}</span>
                  <StatusBadge value={value} />
                </span>
              ),
            )}
          </div>
        )}
      </section>
    </div>
  );
}

function Panel({
  title,
  linkTo,
  query,
  resourceLabel,
  items,
  renderItem,
  emptyTitle,
  emptyDescription,
}: {
  title: string;
  linkTo: string;
  query: { isPending: boolean; isError: boolean; error: unknown; refetch: () => unknown };
  resourceLabel: string;
  items: Row[];
  renderItem: (row: Row, index: number) => React.ReactNode;
  emptyTitle: string;
  emptyDescription: string;
}) {
  return (
    <section className="overflow-hidden rounded-lg border bg-card shadow-xs">
      <header className="flex items-center justify-between gap-3 border-b px-4 py-3">
        <h2 className="text-sm font-semibold">{title}</h2>
        <Link to={linkTo} className="text-xs font-medium text-primary hover:underline">
          View all
        </Link>
      </header>
      {query.isPending ? (
        <LoadingBlock rows={3} />
      ) : query.isError ? (
        <ErrorBlock error={query.error} resourceLabel={resourceLabel} onRetry={() => query.refetch()} />
      ) : items.length === 0 ? (
        <EmptyBlock title={emptyTitle} description={emptyDescription} />
      ) : (
        <ul>{items.map((row, i) => renderItem(row, i))}</ul>
      )}
    </section>
  );
}
