import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Loader2, Plus, RefreshCw, Search } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/page-header";
import { DataTable, type Column } from "@/components/data-table";
import { DetailPanel } from "@/components/detail-panel";
import { ErrorBlock, LoadingBlock } from "@/components/state-block";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { createCompany, getCompany, researchCompany } from "@/lib/gtm-api";
import { rows, text, useCompanies, useContacts, useLeads } from "@/lib/gtm-queries";

export const Route = createFileRoute("/_authenticated/companies")({
  head: () => ({
    meta: [
      { title: "Companies — AI GTM Engineer" },
      { name: "description", content: "Target accounts, firmographics and AI research from your GTM backend." },
      { property: "og:title", content: "Companies — AI GTM Engineer" },
      { property: "og:description", content: "Target accounts and AI research." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: CompaniesPage,
});

type Row = Record<string, unknown>;

function CompaniesPage() {
  const companies = useCompanies();
  const contacts = useContacts();
  const leads = useLeads();
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState({ name: "", domain: "", industry: "", location: "" });

  const companyRows = rows(companies.data);
  const contactRows = rows(contacts.data);
  const leadRows = rows(leads.data);

  const detail = useQuery({
    queryKey: ["company", selectedId],
    queryFn: () => getCompany(selectedId!),
    enabled: Boolean(selectedId),
  });

  const create = useMutation({
    mutationFn: () =>
      createCompany({
        name: form.name,
        domain: form.domain || null,
        industry: form.industry || null,
        location: form.location || null,
      }),
    onSuccess: () => {
      toast.success("Company created");
      setCreateOpen(false);
      setForm({ name: "", domain: "", industry: "", location: "" });
      void queryClient.invalidateQueries({ queryKey: ["companies"] });
    },
    onError: (error: Error) => toast.error("Could not create company", { description: error.message }),
  });

  const research = useMutation({
    mutationFn: (row: Row) => researchCompany(text(row, ["name"], ""), text(row, ["domain"], "") || undefined),
    onSuccess: () => {
      toast.success("Research agent finished", { description: "Open the company to review the result." });
      void queryClient.invalidateQueries({ queryKey: ["companies"] });
      if (selectedId) void queryClient.invalidateQueries({ queryKey: ["company", selectedId] });
    },
    onError: (error: Error) => toast.error("Research failed", { description: error.message }),
  });

  const related = useMemo(() => {
    if (!selectedId) return { contacts: [] as Row[], leads: [] as Row[] };
    const relatedContacts = contactRows.filter((c) => String(c["company_id"]) === selectedId);
    const contactIds = new Set(relatedContacts.map((c) => String(c["id"])));
    return {
      contacts: relatedContacts,
      leads: leadRows.filter(
        (l) => String(l["company_id"]) === selectedId || contactIds.has(String(l["contact_id"])),
      ),
    };
  }, [selectedId, contactRows, leadRows]);

  const columns: Column<Row>[] = [
    {
      key: "name",
      header: "Company",
      render: (r) => <span className="font-medium">{text(r, ["name"])}</span>,
      value: (r) => text(r, ["name"]),
    },
    { key: "domain", header: "Domain", value: (r) => text(r, ["domain"]) },
    { key: "industry", header: "Industry", value: (r) => text(r, ["industry"]) },
    { key: "employee_count", header: "Employees", value: (r) => Number(r["employee_count"] ?? 0) },
    { key: "location", header: "Location", value: (r) => text(r, ["location"]) },
    {
      key: "actions",
      header: "Actions",
      sortable: false,
      render: (r) => (
        <Button
          variant="outline"
          size="sm"
          disabled={research.isPending}
          onClick={(e) => {
            e.stopPropagation();
            research.mutate(r);
          }}
        >
          {research.isPending && research.variables === r ? (
            <Loader2 className="size-3.5 animate-spin" aria-hidden />
          ) : (
            <Search className="size-3.5" aria-hidden />
          )}
          Research
        </Button>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Companies"
        description="Accounts in your GTM database, with AI research on demand."
        actions={
          <>
            <Button variant="outline" size="sm" onClick={() => companies.refetch()} disabled={companies.isFetching}>
              <RefreshCw className={companies.isFetching ? "size-4 animate-spin" : "size-4"} aria-hidden />
              Refresh
            </Button>
            <Dialog open={createOpen} onOpenChange={setCreateOpen}>
              <DialogTrigger asChild>
                <Button size="sm">
                  <Plus className="size-4" aria-hidden /> New company
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Create company</DialogTitle>
                  <DialogDescription>Saved through the backend companies endpoint.</DialogDescription>
                </DialogHeader>
                <div className="space-y-3">
                  {(
                    [
                      ["name", "Name", true],
                      ["domain", "Domain", false],
                      ["industry", "Industry", false],
                      ["location", "Location", false],
                    ] as const
                  ).map(([key, label, required]) => (
                    <div key={key} className="space-y-1.5">
                      <Label htmlFor={key}>
                        {label}
                        {required ? " *" : ""}
                      </Label>
                      <Input
                        id={key}
                        value={form[key]}
                        onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                      />
                    </div>
                  ))}
                </div>
                <DialogFooter>
                  <Button onClick={() => create.mutate()} disabled={!form.name.trim() || create.isPending}>
                    {create.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
                    Create
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </>
        }
      />

      {companies.isPending ? (
        <div className="rounded-lg border bg-card">
          <LoadingBlock />
        </div>
      ) : companies.isError ? (
        <div className="rounded-lg border bg-card">
          <ErrorBlock error={companies.error} resourceLabel="companies" onRetry={() => companies.refetch()} />
        </div>
      ) : (
        <DataTable
          rows={companyRows}
          columns={columns}
          onRowClick={(r) => setSelectedId(String(r["id"] ?? ""))}
          searchPlaceholder="Search companies"
          emptyTitle="No companies yet"
          emptyDescription="Create a company or let the research agent add accounts."
        />
      )}

      <DetailPanel
        open={Boolean(selectedId)}
        onOpenChange={(open) => !open && setSelectedId(null)}
        title={detail.data ? text(detail.data, ["name"], "Company") : "Company"}
        record={detail.data ?? null}
      >
        {detail.isPending && selectedId ? <LoadingBlock rows={3} /> : null}
        {detail.isError ? (
          <ErrorBlock error={detail.error} resourceLabel="company" onRetry={() => detail.refetch()} />
        ) : null}
        {detail.data ? (
          <div className="grid gap-4 sm:grid-cols-2">
            <RelatedList title="Contacts" items={related.contacts.map((c) => text(c, ["email", "first_name", "id"]))} />
            <RelatedList title="Leads" items={related.leads.map((l) => text(l, ["status", "id"]))} />
          </div>
        ) : null}
      </DetailPanel>
    </div>
  );
}

function RelatedList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-md border p-3">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{title}</p>
      {items.length === 0 ? (
        <p className="mt-2 text-sm text-muted-foreground">None linked in the backend.</p>
      ) : (
        <ul className="mt-2 space-y-1 text-sm">
          {items.slice(0, 8).map((item, i) => (
            <li key={i} className="truncate">
              {item}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
