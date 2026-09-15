import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Loader2, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/page-header";
import { DataTable, type Column } from "@/components/data-table";
import { StatusBadge } from "@/components/status-badge";
import { DetailPanel } from "@/components/detail-panel";
import { ErrorBlock, LoadingBlock } from "@/components/state-block";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { enrichLead } from "@/lib/gtm-api";
import { rows, text, useCompanies, useContacts, useLeads } from "@/lib/gtm-queries";
import { formatValue } from "@/lib/format";

export const Route = createFileRoute("/_authenticated/leads")({
  head: () => ({
    meta: [
      { title: "Leads — AI GTM Engineer" },
      { name: "description", content: "Track, filter and enrich every lead your AI GTM engine produces." },
      { property: "og:title", content: "Leads — AI GTM Engineer" },
      { property: "og:description", content: "Track, filter and enrich AI-sourced leads." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: LeadsPage,
});

type Row = Record<string, unknown>;

function LeadsPage() {
  const leads = useLeads();
  const companies = useCompanies();
  const contacts = useContacts();
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<Row | null>(null);
  const [status, setStatus] = useState("all");

  const leadRows = rows(leads.data);
  const companyById = useMemo(() => {
    const map = new Map<string, Row>();
    for (const c of rows(companies.data)) map.set(String(c["id"]), c);
    return map;
  }, [companies.data]);
  const contactById = useMemo(() => {
    const map = new Map<string, Row>();
    for (const c of rows(contacts.data)) map.set(String(c["id"]), c);
    return map;
  }, [contacts.data]);

  const statuses = useMemo(() => {
    const set = new Set<string>();
    for (const r of leadRows) {
      const s = text(r, ["status", "state", "stage"], "");
      if (s) set.add(s);
    }
    return [...set].sort();
  }, [leadRows]);

  const filtered = status === "all" ? leadRows : leadRows.filter((r) => text(r, ["status", "state", "stage"], "") === status);

  const enrich = useMutation({
    mutationFn: (contactId: string) => enrichLead(contactId),
    onSuccess: () => {
      toast.success("Enrichment finished", { description: "Lead data refreshed from the backend." });
      void queryClient.invalidateQueries({ queryKey: ["leads"] });
      void queryClient.invalidateQueries({ queryKey: ["contacts"] });
    },
    onError: (error: Error) => toast.error("Enrichment failed", { description: error.message }),
  });

  function contactOf(row: Row): Row | undefined {
    const id = text(row, ["contact_id"], "");
    return id ? contactById.get(id) : undefined;
  }

  const columns: Column<Row>[] = [
    {
      key: "contact",
      header: "Contact",
      value: (r) => {
        const c = contactOf(r);
        return c ? `${text(c, ["first_name"], "")} ${text(c, ["last_name"], "")}`.trim() : text(r, ["name", "contact_id"]);
      },
      render: (r) => {
        const c = contactOf(r);
        const name = c ? `${text(c, ["first_name"], "")} ${text(c, ["last_name"], "")}`.trim() : text(r, ["name"], "");
        return <span className="font-medium">{name || text(r, ["contact_id"], "—")}</span>;
      },
    },
    {
      key: "email",
      header: "Email",
      value: (r) => text(r, ["email"]) !== "—" ? text(r, ["email"]) : text(contactOf(r) ?? {}, ["email"]),
      render: (r) => {
        const email = r["email"] ?? contactOf(r)?.["email"];
        return <span className="text-muted-foreground">{email ? String(email) : "—"}</span>;
      },
    },
    {
      key: "company",
      header: "Company",
      value: (r) => {
        const c = contactOf(r);
        const companyId = text(r, ["company_id"], "") || text(c ?? {}, ["company_id"], "");
        return companyId ? text(companyById.get(companyId) ?? {}, ["name"], companyId) : "—";
      },
      render: (r) => {
        const c = contactOf(r);
        const companyId = text(r, ["company_id"], "") || text(c ?? {}, ["company_id"], "");
        return <span>{companyId ? text(companyById.get(companyId) ?? {}, ["name"], companyId) : "—"}</span>;
      },
    },
    {
      key: "score",
      header: "Score",
      value: (r) => Number(r["score"] ?? r["lead_score"] ?? 0),
      render: (r) => <span className="tabular-nums">{text(r, ["score", "lead_score"])}</span>,
    },
    {
      key: "status",
      header: "Status",
      value: (r) => text(r, ["status", "state", "stage"]),
      render: (r) => <StatusBadge value={text(r, ["status", "state", "stage"], "unknown")} />,
    },
    {
      key: "created_at",
      header: "Created",
      value: (r) => text(r, ["created_at", "updated_at"]),
      render: (r) => formatValue("created_at", r["created_at"] ?? null),
    },
    {
      key: "actions",
      header: "Actions",
      sortable: false,
      render: (r) => {
        const contactId = text(r, ["contact_id"], "");
        return (
          <Button
            variant="outline"
            size="sm"
            disabled={!contactId || enrich.isPending}
            onClick={(e) => {
              e.stopPropagation();
              enrich.mutate(contactId);
            }}
          >
            {enrich.isPending && enrich.variables === contactId ? (
              <Loader2 className="size-3.5 animate-spin" aria-hidden />
            ) : null}
            Enrich
          </Button>
        );
      },
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Leads"
        description="Every lead the backend has produced, with live status and enrichment actions."
        actions={
          <Button variant="outline" size="sm" onClick={() => leads.refetch()} disabled={leads.isFetching}>
            <RefreshCw className={leads.isFetching ? "size-4 animate-spin" : "size-4"} aria-hidden />
            Refresh
          </Button>
        }
      />

      {leads.isPending ? (
        <div className="rounded-lg border bg-card">
          <LoadingBlock />
        </div>
      ) : leads.isError ? (
        <div className="rounded-lg border bg-card">
          <ErrorBlock error={leads.error} resourceLabel="leads" onRetry={() => leads.refetch()} />
        </div>
      ) : (
        <DataTable
          rows={filtered}
          columns={columns}
          onRowClick={setSelected}
          searchPlaceholder="Search leads"
          emptyTitle="No leads yet"
          emptyDescription="Run the lead pipeline workflow to generate leads."
          filters={
            statuses.length > 0 ? (
              <Select value={status} onValueChange={setStatus}>
                <SelectTrigger className="w-44">
                  <SelectValue placeholder="All statuses" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All statuses</SelectItem>
                  {statuses.map((s) => (
                    <SelectItem key={s} value={s}>
                      {s.replace(/_/g, " ")}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : null
          }
        />
      )}

      <DetailPanel
        open={selected !== null}
        onOpenChange={(open) => !open && setSelected(null)}
        title="Lead detail"
        record={selected}
      />
    </div>
  );
}
