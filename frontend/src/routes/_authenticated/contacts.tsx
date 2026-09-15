import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Loader2, Plus, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/page-header";
import { DataTable, type Column } from "@/components/data-table";
import { DetailPanel } from "@/components/detail-panel";
import { StatusBadge } from "@/components/status-badge";
import { ErrorBlock, LoadingBlock } from "@/components/state-block";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { createContact, enrichLead } from "@/lib/gtm-api";
import { rows, text, useCompanies, useContacts, useLeads } from "@/lib/gtm-queries";

export const Route = createFileRoute("/_authenticated/contacts")({
  head: () => ({
    meta: [
      { title: "Contacts — AI GTM Engineer" },
      { name: "description", content: "People at your target accounts, enriched by the AI enrichment agent." },
      { property: "og:title", content: "Contacts — AI GTM Engineer" },
      { property: "og:description", content: "People at your target accounts." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: ContactsPage,
});

type Row = Record<string, unknown>;

function ContactsPage() {
  const contacts = useContacts();
  const companies = useCompanies();
  const leads = useLeads();
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<Row | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState({
    company_id: "",
    first_name: "",
    last_name: "",
    email: "",
    title: "",
  });

  const contactRows = rows(contacts.data);
  const leadRows = rows(leads.data);
  const companyById = useMemo(() => {
    const map = new Map<string, Row>();
    for (const c of rows(companies.data)) map.set(String(c["id"]), c);
    return map;
  }, [companies.data]);

  const leadByContact = useMemo(() => {
    const map = new Map<string, Row>();
    for (const l of leadRows) map.set(String(l["contact_id"]), l);
    return map;
  }, [leadRows]);

  const create = useMutation({
    mutationFn: () =>
      createContact({
        company_id: form.company_id,
        first_name: form.first_name,
        last_name: form.last_name,
        email: form.email,
        title: form.title || null,
      }),
    onSuccess: () => {
      toast.success("Contact created");
      setCreateOpen(false);
      setForm({ company_id: "", first_name: "", last_name: "", email: "", title: "" });
      void queryClient.invalidateQueries({ queryKey: ["contacts"] });
    },
    onError: (error: Error) => toast.error("Could not create contact", { description: error.message }),
  });

  const enrich = useMutation({
    mutationFn: (id: string) => enrichLead(id),
    onSuccess: () => {
      toast.success("Enrichment finished");
      void queryClient.invalidateQueries({ queryKey: ["contacts"] });
      void queryClient.invalidateQueries({ queryKey: ["leads"] });
    },
    onError: (error: Error) => toast.error("Enrichment failed", { description: error.message }),
  });

  const columns: Column<Row>[] = [
    {
      key: "name",
      header: "Name",
      value: (r) => `${text(r, ["first_name"], "")} ${text(r, ["last_name"], "")}`.trim(),
      render: (r) => (
        <span className="font-medium">
          {`${text(r, ["first_name"], "")} ${text(r, ["last_name"], "")}`.trim() || "—"}
        </span>
      ),
    },
    { key: "title", header: "Role", value: (r) => text(r, ["title", "role"]) },
    { key: "email", header: "Email", value: (r) => text(r, ["email"]) },
    {
      key: "company",
      header: "Company",
      value: (r) => text(companyById.get(String(r["company_id"])) ?? {}, ["name"], text(r, ["company_id"])),
      render: (r) => (
        <span>{text(companyById.get(String(r["company_id"])) ?? {}, ["name"], text(r, ["company_id"]))}</span>
      ),
    },
    {
      key: "lead",
      header: "Lead status",
      sortable: false,
      render: (r) => {
        const lead = leadByContact.get(String(r["id"]));
        return lead ? (
          <StatusBadge value={text(lead, ["status", "state"], "unknown")} />
        ) : (
          <span className="text-sm text-muted-foreground">No lead</span>
        );
      },
    },
    {
      key: "actions",
      header: "Actions",
      sortable: false,
      render: (r) => (
        <Button
          variant="outline"
          size="sm"
          disabled={enrich.isPending}
          onClick={(e) => {
            e.stopPropagation();
            enrich.mutate(String(r["id"]));
          }}
        >
          {enrich.isPending && enrich.variables === String(r["id"]) ? (
            <Loader2 className="size-3.5 animate-spin" aria-hidden />
          ) : null}
          Enrich
        </Button>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Contacts"
        description="Every person the backend knows about, linked to their account and lead."
        actions={
          <>
            <Button variant="outline" size="sm" onClick={() => contacts.refetch()} disabled={contacts.isFetching}>
              <RefreshCw className={contacts.isFetching ? "size-4 animate-spin" : "size-4"} aria-hidden />
              Refresh
            </Button>
            <Dialog open={createOpen} onOpenChange={setCreateOpen}>
              <DialogTrigger asChild>
                <Button size="sm">
                  <Plus className="size-4" aria-hidden /> New contact
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Create contact</DialogTitle>
                  <DialogDescription>Company, name and email are required by the backend.</DialogDescription>
                </DialogHeader>
                <div className="space-y-3">
                  {(
                    [
                      ["company_id", "Company ID *"],
                      ["first_name", "First name *"],
                      ["last_name", "Last name *"],
                      ["email", "Email *"],
                      ["title", "Title"],
                    ] as const
                  ).map(([key, label]) => (
                    <div key={key} className="space-y-1.5">
                      <Label htmlFor={key}>{label}</Label>
                      <Input
                        id={key}
                        value={form[key]}
                        onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                      />
                    </div>
                  ))}
                </div>
                <DialogFooter>
                  <Button
                    onClick={() => create.mutate()}
                    disabled={
                      create.isPending ||
                      !form.company_id.trim() ||
                      !form.first_name.trim() ||
                      !form.last_name.trim() ||
                      !form.email.trim()
                    }
                  >
                    {create.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
                    Create
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </>
        }
      />

      {contacts.isPending ? (
        <div className="rounded-lg border bg-card">
          <LoadingBlock />
        </div>
      ) : contacts.isError ? (
        <div className="rounded-lg border bg-card">
          <ErrorBlock error={contacts.error} resourceLabel="contacts" onRetry={() => contacts.refetch()} />
        </div>
      ) : (
        <DataTable
          rows={contactRows}
          columns={columns}
          onRowClick={setSelected}
          searchPlaceholder="Search contacts"
          emptyTitle="No contacts yet"
          emptyDescription="Add a contact or let the enrichment agent discover people."
        />
      )}

      <DetailPanel
        open={selected !== null}
        onOpenChange={(open) => !open && setSelected(null)}
        title={
          selected ? `${text(selected, ["first_name"], "")} ${text(selected, ["last_name"], "")}`.trim() || "Contact" : "Contact"
        }
        record={selected}
      />
    </div>
  );
}
