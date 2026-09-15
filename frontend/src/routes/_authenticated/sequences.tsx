import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Loader2, Mail, RefreshCw, Send, Sparkles } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/page-header";
import { DataTable, type Column } from "@/components/data-table";
import { StatusBadge } from "@/components/status-badge";
import { DetailPanel } from "@/components/detail-panel";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { StageResults } from "@/components/stage-results";
import { SequenceTimeline, type StepDraft } from "@/components/sequence-timeline";
import { parseSequenceSteps } from "@/lib/sequence";

import { ErrorBlock, LoadingBlock } from "@/components/state-block";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { formatValue } from "@/lib/format";
import { normalizeState, runWorkflow, sendEmail, type Json } from "@/lib/gtm-api";
import { rows, text, useContacts, useEmails } from "@/lib/gtm-queries";

export const Route = createFileRoute("/_authenticated/sequences")({
  head: () => ({
    meta: [
      { title: "Email Sequences — AI GTM Engineer" },
      {
        name: "description",
        content: "Generate, preview and send AI-written outreach sequences backed by your GTM API.",
      },
      { property: "og:title", content: "Email Sequences — AI GTM Engineer" },
      { property: "og:description", content: "Generate, preview and send AI outreach sequences." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: SequencesPage,
});

type Row = Record<string, unknown>;

function SequencesPage() {
  const emails = useEmails();
  const contacts = useContacts();
  const queryClient = useQueryClient();

  const [contactId, setContactId] = useState("");
  const [generated, setGenerated] = useState<Json | null>(null);
  const [selected, setSelected] = useState<Row | null>(null);
  const [sendTarget, setSendTarget] = useState<
    { contact_id: string; subject: string; body: string; stepIndex?: number } | null
  >(null);
  const [sendingIndex, setSendingIndex] = useState<number | null>(null);
  const [draft, setDraft] = useState({ subject: "", body: "" });
  const [drafts, setDrafts] = useState<Record<number, StepDraft>>({});

  const emailRows = rows(emails.data);
  const contactRows = rows(contacts.data);
  const steps = parseSequenceSteps(generated);


  const generate = useMutation({
    mutationFn: (id: string) => runWorkflow("email_sequence", { contact_id: id }),
    onSuccess: (data) => {
      setGenerated(data);
      setDrafts({});
      toast.success("Sequence generation finished", {
        description: "Review each step below — nothing is sent until you choose to send it.",
      });

      void queryClient.invalidateQueries({ queryKey: ["emails"] });
    },
    onError: (error: Error) => toast.error("Generation failed", { description: error.message }),
  });

  const send = useMutation({
    mutationFn: (payload: { contact_id: string; subject: string; body: string }) => sendEmail(payload),
    onSuccess: (data) => {
      const state = normalizeState((data as Json)?.["status"]);
      if (state === "error" || state === "not_configured") {
        toast.warning("Backend did not send the email", {
          description: JSON.stringify(data).slice(0, 200),
        });
      } else {
        toast.success("Send request accepted by the backend");
      }
      void queryClient.invalidateQueries({ queryKey: ["emails"] });
    },
    onError: (error: Error) => toast.error("Send failed", { description: error.message }),
    onSettled: () => setSendingIndex(null),
  });


  const columns: Column<Row>[] = [
    {
      key: "subject",
      header: "Subject",
      value: (r) => text(r, ["subject", "title", "name"]),
      render: (r) => <span className="font-medium">{text(r, ["subject", "title", "name"])}</span>,
    },
    { key: "recipient", header: "Recipient", value: (r) => text(r, ["to_email", "recipient", "email", "contact_id"]) },
    {
      key: "status",
      header: "Status",
      value: (r) => text(r, ["status", "state"]),
      render: (r) => <StatusBadge value={text(r, ["status", "state"], "unknown")} />,
    },
    {
      key: "created_at",
      header: "Created",
      value: (r) => text(r, ["created_at", "sent_at", "updated_at"]),
      render: (r) => formatValue("created_at", r["created_at"] ?? r["sent_at"] ?? null),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Email Sequences"
        description="Generate personalized outreach with the email workflow, review every step, then send explicitly."
      />

      <section className="rounded-lg border bg-card p-5 shadow-xs">
        <div className="flex items-center gap-2">
          <Sparkles className="size-4 text-primary" aria-hidden />
          <h2 className="text-sm font-semibold">Generate a sequence</h2>
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          Runs the <span className="font-mono text-xs">email_sequence</span> workflow for one contact. Nothing is
          sent automatically.
        </p>
        <div className="mt-4 flex flex-wrap items-end gap-3">
          <div className="min-w-64 flex-1 space-y-1.5">
            <Label htmlFor="contact">Contact ID</Label>
            <Input
              id="contact"
              list="contact-ids"
              value={contactId}
              onChange={(e) => setContactId(e.target.value)}
              placeholder="Paste or pick a contact ID"
            />
            <datalist id="contact-ids">
              {contactRows.map((c, i) => (
                <option key={i} value={String(c["id"] ?? "")}>
                  {text(c, ["email", "first_name"])}
                </option>
              ))}
            </datalist>
          </div>
          <Button
            onClick={() => generate.mutate(contactId)}
            disabled={!contactId.trim() || generate.isPending}
          >
            {generate.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
            Generate sequence
          </Button>
        </div>

        {generate.isError ? (
          <p role="alert" className="mt-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {(generate.error as Error).message}
          </p>
        ) : null}

        {generated ? (
          <div className="mt-6 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-sm font-semibold">Generated sequence</h3>
              <Button
                variant="outline"
                size="sm"
                disabled={!contactId.trim() || generate.isPending}
                onClick={() => generate.mutate(contactId)}
              >
                {generate.isPending ? (
                  <Loader2 className="size-4 animate-spin" aria-hidden />
                ) : (
                  <RefreshCw className="size-4" aria-hidden />
                )}
                Regenerate sequence
              </Button>
            </div>

            {steps.length > 0 ? (
              <SequenceTimeline
                steps={steps}
                drafts={drafts}
                onDraftChange={(index, draft) => setDrafts((prev) => ({ ...prev, [index]: draft }))}
                onSend={(step, draft) =>
                  setSendTarget({
                    contact_id: contactId,
                    subject: draft.subject,
                    body: draft.body,
                    stepIndex: step.index,
                  })
                }
                sendingIndex={send.isPending ? sendingIndex : null}
                canSend={Boolean(contactId.trim())}
              />
            ) : (
              <p className="text-sm text-muted-foreground">
                The workflow response contained no email steps. Check the stage results and raw response below.
              </p>
            )}

            <div className="space-y-3">
              <h3 className="text-sm font-semibold">Stage results</h3>
              <StageResults payload={generated} />
            </div>

            <details>
              <summary className="cursor-pointer text-xs text-muted-foreground">View raw response</summary>
              <pre className="mt-2 max-h-72 overflow-auto rounded-md bg-muted p-3 font-mono text-xs">
                {JSON.stringify(generated, null, 2)}
              </pre>
            </details>
          </div>
        ) : null}

      </section>

      <section className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Mail className="size-4 text-muted-foreground" aria-hidden />
            <h2 className="text-sm font-semibold">Email activity</h2>
          </div>
          <Button variant="outline" size="sm" onClick={() => emails.refetch()} disabled={emails.isFetching}>
            Refresh
          </Button>
        </div>

        {emails.isPending ? (
          <div className="rounded-lg border bg-card">
            <LoadingBlock />
          </div>
        ) : emails.isError ? (
          <div className="rounded-lg border bg-card">
            <ErrorBlock error={emails.error} resourceLabel="emails" onRetry={() => emails.refetch()} />
          </div>
        ) : (
          <DataTable
            rows={emailRows}
            columns={columns}
            onRowClick={setSelected}
            searchPlaceholder="Search subject or recipient"
            emptyTitle="No emails yet"
            emptyDescription="Generated and sent emails from the backend will appear here."
          />
        )}
      </section>

      <section className="rounded-lg border bg-card p-5 shadow-xs">
        <div className="flex items-center gap-2">
          <Send className="size-4 text-muted-foreground" aria-hidden />
          <h2 className="text-sm font-semibold">Send an email</h2>
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          Sending is manual and always confirmed — the backend delivers via its configured provider.
        </p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="send-contact">Contact ID</Label>
            <Input
              id="send-contact"
              value={contactId}
              onChange={(e) => setContactId(e.target.value)}
              placeholder="Contact ID"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="send-subject">Subject</Label>
            <Input
              id="send-subject"
              value={draft.subject}
              onChange={(e) => setDraft({ ...draft, subject: e.target.value })}
            />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="send-body">Body</Label>
            <Textarea
              id="send-body"
              rows={6}
              value={draft.body}
              onChange={(e) => setDraft({ ...draft, body: e.target.value })}
            />
          </div>
        </div>
        <Button
          className="mt-4"
          disabled={!contactId.trim() || !draft.subject.trim() || !draft.body.trim() || send.isPending}
          onClick={() => setSendTarget({ contact_id: contactId, subject: draft.subject, body: draft.body })}
        >
          {send.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
          Send email
        </Button>
      </section>

      <ConfirmDialog
        open={sendTarget !== null}
        onOpenChange={(open) => !open && setSendTarget(null)}
        title="Send this email now?"
        description="This asks the backend to deliver a real email to the contact. This cannot be undone."
        confirmLabel="Send"
        destructive
        onConfirm={() => {
          if (sendTarget) {
            const { contact_id, subject, body, stepIndex } = sendTarget;
            setSendingIndex(stepIndex ?? null);
            send.mutate({ contact_id, subject, body });
          }
          setSendTarget(null);
        }}

      />

      <DetailPanel
        open={selected !== null}
        onOpenChange={(open) => !open && setSelected(null)}
        title={selected ? text(selected, ["subject", "id"], "Email") : "Email"}
        record={selected}
      />
    </div>
  );
}
