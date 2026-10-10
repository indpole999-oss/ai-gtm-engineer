import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace";
import { Panel, Field, Feedback, Status, Loading, ErrorState, useData, friendlyError, time } from "./ui";
import { createReviewClient, reviewPermissions, type DraftSnapshot, type ReviewState, type ReviewAction } from "./outreach-review-client";

export function DraftReview({ draft, onDraft }: { draft: DraftSnapshot; onDraft: (draft: DraftSnapshot) => void }) {
  const { workspace } = useWorkspace();
  const cache = useQueryClient();
  const review = useData<ReviewState>("/api/v1/outreach/drafts/" + draft.id + "/review");
  const client = useRef(createReviewClient(apiFetch));
  const [subject, setSubject] = useState(draft.envelope.subject);
  const [body, setBody] = useState(draft.envelope.body);
  const [reason, setReason] = useState("");
  const [reviewed, setReviewed] = useState(false);
  const [acknowledge, setAcknowledge] = useState(false);
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState("");
  const dirty = subject !== draft.envelope.subject || body !== draft.envelope.body;
  const state = review.data;
  const permissions = reviewPermissions(workspace.role, state?.status || "", state?.current_draft_id === draft.id, dirty);
  async function act(action: ReviewAction) {
    if (!state) return;
    setBusy(true); setFeedback("");
    try {
      const result = await client.current.run(draft, state.revision, action, { subject, body, reason, acknowledge });
      if (action === "revisions") onDraft(result as DraftSnapshot);
      setReviewed(false); setAcknowledge(false);
      await cache.invalidateQueries({ queryKey: ["customer", workspace.id] });
      setFeedback(action === "approve" ? "Message approved. No email was sent or queued; delivery requires separate authorization." :
        action === "submit" ? "Submitted for approval. No email was sent or queued." :
        action === "revisions" ? "Draft revision saved." :
        action === "rejected" ? "Draft rejected. Decision saved." : "Changes requested. Review feedback saved.");
    } catch (error) {
      setFeedback(friendlyError(error));
      await review.refetch();
    } finally { setBusy(false); }
  }
  if (review.isPending) return <Loading />;
  if (review.isError || !state) return <ErrorState retry={() => void review.refetch()} />;
  return <Panel title="Draft review">
    <Feedback message={feedback} />
    <Status value={state.status} />
    <p className="my-3 text-sm">From {draft.envelope.sender} → {draft.envelope.recipient}</p>
    <p className="mb-4 text-sm text-muted-foreground">Editing and review never send or schedule email delivery.</p>
    {state.current_draft_id !== draft.id && <button className="g-button" disabled={busy} onClick={async () => {
      setBusy(true);
      try { onDraft(await apiFetch<DraftSnapshot>("/api/v1/outreach/drafts/" + state.current_draft_id)); }
      catch (error) { setFeedback(friendlyError(error)); }
      finally { setBusy(false); }
    }}>Open the current draft</button>}
    <div className="space-y-4">
      <Field label="Subject"><input className="g-input" value={subject} maxLength={300} readOnly={!permissions.edit || busy}
        onChange={event => { setSubject(event.target.value); setReviewed(false); }} /></Field>
      <Field label="Message"><textarea className="g-input" rows={12} maxLength={20000} value={body} readOnly={!permissions.edit || busy}
        onChange={event => { setBody(event.target.value); setReviewed(false); }} /></Field>
      {(dirty || state.warnings.length > 0) && <p role="alert" className="text-sm text-amber-700">
        Edited wording outside the source quotation and approved Company Brain claim is not verified. Review every added assertion. Keep both quoted claims intact.
      </p>}
      {permissions.edit && <button className="g-button" disabled={busy || !dirty || !subject.trim() || !body.trim()} onClick={() => void act("revisions")}>Save draft revision</button>}
      {permissions.submit && <button className="g-button" disabled={busy} onClick={() => void act("submit")}>Submit for approval</button>}
    </div>
    <details className="my-5 text-sm" open>
      <summary>Supporting evidence</summary>
      <blockquote className="my-3 whitespace-pre-wrap border-l-2 pl-3">{state.evidence.excerpt}</blockquote>
      <p className="break-all">{state.evidence.source_url}</p>
      <p className="mt-3">Approved Company Brain claim: {state.evidence.brain_claim}</p>
      <p className="mt-2 text-xs break-all">Research {draft.envelope.research_job_id} · Evidence {draft.envelope.evidence_id}</p>
    </details>
    {permissions.decide && <div className="space-y-4">
      <label className="flex gap-3 text-sm"><input type="checkbox" checked={reviewed} onChange={event => setReviewed(event.target.checked)} />
        I reviewed this recipient, exact message and supporting evidence.</label>
      {state.warnings.length > 0 && <label className="flex gap-3 text-sm"><input type="checkbox" checked={acknowledge} onChange={event => setAcknowledge(event.target.checked)} />
        I reviewed the added wording and acknowledge that it is not verified by the cited evidence.</label>}
      <button className="g-button" disabled={busy || !reviewed || (state.warnings.length > 0 && !acknowledge)} onClick={() => void act("approve")}>Approve message only</button>
      <Field label="Review reason (required to reject or request changes)"><textarea className="g-input" rows={3} maxLength={2000} value={reason} onChange={event => setReason(event.target.value)} /></Field>
      <div className="flex flex-wrap gap-3">
        <button className="g-button g-button-secondary" disabled={busy || !reason.trim()} onClick={() => void act("rejected")}>Reject</button>
        <button className="g-button g-button-secondary" disabled={busy || !reason.trim()} onClick={() => void act("changes_requested")}>Request changes</button>
      </div>
    </div>}
    {state.status === "submitted" && !permissions.decide && <p className="text-sm">An owner or admin must review this submission.</p>}
    <details className="mt-6">
      <summary>Review history · {state.history.length} events</summary>
      <ol className="mt-3 space-y-3 text-sm">{state.history.map(event => <li key={event.id}>
        Revision {event.revision} · {event.action.replaceAll("_", " ")} · {time(event.created_at)}
        <p className="text-xs break-all">Actor {event.actor_id} · Draft {event.draft_id}</p>
        {event.reason && <p>{event.reason}</p>}
      </li>)}</ol>
    </details>
  </Panel>;
}
