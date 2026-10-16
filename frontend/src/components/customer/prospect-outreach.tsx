import { useRef, useState } from "react";
import { Link } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace";
import { Field, Feedback, Loading, ErrorState, useData, friendlyError, time } from "./ui";
import { DraftReview } from "./draft-review";
import type { DraftSnapshot } from "./outreach-review-client";

export function ProspectOutreach({ contactId }: { contactId: string }) {
  const { canEdit, workspace } = useWorkspace();
  const cache = useQueryClient();
  const jobs = useData<{ id: string; completed_at: string }[]>("/api/v1/outreach/prospects/" + contactId + "/eligibility");
  const versions = useData<{ id: string; sequence_id: string; number: number }[]>("/api/v1/outreach/versions");
  const sequences = useData<{ id: string; name: string }[]>("/api/v1/outreach/sequences");
  const senders = useData<{ id: string; email: string; status: string }[]>("/api/v1/outreach/senders");
  const [selected, setSelected] = useState<DraftSnapshot | null>(null);
  const [feedback, setFeedback] = useState("");
  const [busy, setBusy] = useState(false);
  const pending = useRef(false);
  const queries = [jobs, versions, sequences, senders];
  if (queries.some(query => query.isPending)) return <Loading />;
  if (queries.some(query => query.isError)) return <ErrorState retry={() => queries.forEach(query => void query.refetch())} />;
  return <div className="mt-5 space-y-4">
    <Feedback message={feedback} />
    {!jobs.data?.length ? <p className="text-sm">Drafting requires persisted potential-fit research with a matching source-backed buyer. No eligible research is available for this contact.</p> :
      !versions.data?.length || !senders.data?.length ? <p className="text-sm">Configure a sequence and sender identity in <Link to="/outreach" className="underline">Outreach</Link> before drafting. Sender setup does not enable sending.</p> :
      canEdit && <form className="grid gap-4 md:grid-cols-2" onSubmit={async event => {
        event.preventDefault();
        if (pending.current) return;
        const fields = Object.fromEntries(new FormData(event.currentTarget));
        pending.current = true; setBusy(true); setFeedback("");
        try {
          const draft = await apiFetch<DraftSnapshot>("/api/v1/outreach/prospects/" + contactId + "/draft", { method: "POST", body: JSON.stringify(fields) });
          setSelected(draft);
          await cache.invalidateQueries({ queryKey: ["customer", workspace.id] });
          setFeedback("Grounded draft retrieved. No AI call or email delivery was started.");
        } catch (error) { setFeedback(friendlyError(error)); }
        finally { pending.current = false; setBusy(false); }
      }}>
        <Field label="Qualified research"><select className="g-input" name="research_job_id" required>
          {jobs.data.map(job => <option key={job.id} value={job.id}>{time(job.completed_at)} · {job.id.slice(0, 8)}</option>)}
        </select></Field>
        <Field label="Sequence version"><select className="g-input" name="version_id" required>
          <option value="">Select sequence</option>
          {versions.data.map(version => <option key={version.id} value={version.id}>{sequences.data?.find(sequence => sequence.id === version.sequence_id)?.name} · v{version.number}</option>)}
        </select></Field>
        <Field label="Sender identity"><select className="g-input" name="sender_id" required>
          <option value="">Select sender</option>
          {senders.data.map(sender => <option key={sender.id} value={sender.id}>{sender.email} · {sender.status}</option>)}
        </select></Field>
        <button className="g-button self-end" disabled={busy}>Generate or retrieve outreach draft</button>
      </form>}
    {selected && <DraftReview key={selected.id} draft={selected} onDraft={setSelected} />}
  </div>;
}
