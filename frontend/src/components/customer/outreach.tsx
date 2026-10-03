import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace";
import {
  Heading,
  Panel,
  Status,
  Loading,
  ErrorState,
  Empty,
  Feedback,
  Field,
  friendlyError,
  useData,
  time,
} from "./ui";
import { sendLabel, type Contact, type Integration } from "./contracts";
import { PlanReview, type ReviewedPlan } from "./plan-review";

type Named = { id: string; name: string; status?: string; campaign_id?: string };
type Version = {
  id: string;
  sequence_id: string;
  number: number;
  definition: { steps: { delay_seconds: number; purpose: string }[] };
};
type Enrollment = { id: string; contact_id: string; version_id: string; status: string };
type Scheduled = { id: string; enrollment_id: string; sequence_step_id: string; due_at: string };
type Draft = {
  id: string;
  scheduled_id: string;
  content_hash: string;
  envelope: {
    recipient: string;
    sender: string;
    subject: string;
    body: string;
    brain_version_id: string;
    research_job_id: string;
    evidence_id: string;
    sequence_version_id: string;
    contact_id: string;
    due_at: string;
  };
};
type Message = {
  id: string;
  draft_id: string;
  scheduled_id: string;
  state: string;
  provider_message_id: string | null;
  accepted_at: string | null;
  plan_id: string;
};
const base = "/api/v1/outreach";
export function OutreachPage() {
  const { canEdit, canApprove } = useWorkspace();
  const cache = useQueryClient();
  const campaigns = useData<Named[]>(base + "/campaigns"),
    sequences = useData<Named[]>(base + "/sequences"),
    versions = useData<Version[]>(base + "/versions"),
    enrollments = useData<Enrollment[]>(base + "/enrollments"),
    scheduled = useData<Scheduled[]>(base + "/scheduled"),
    drafts = useData<Draft[]>(base + "/drafts"),
    messages = useData<Message[]>(base + "/messages"),
    suppressions = useData<{ id: string; email: string; reason: string }[]>(base + "/suppressions"),
    senders = useData<{ id: string; email: string; status: string }[]>(base + "/senders"),
    contacts = useData<Contact[]>("/api/v1/contacts/"),
    jobs = useData<{ id: string; company_id: string; status: string }[]>("/api/v1/research/jobs"),
    delivery = useData<{ id: string; message_id: string; kind: string; created_at: string }[]>(
      base + "/delivery-events",
    );
  const [tab, setTab] = useState("Messages"),
    [selected, setSelected] = useState<Draft | null>(null),
    [reviewed, setReviewed] = useState(false),
    [plan, setPlan] = useState<ReviewedPlan | null>(null),
    [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false);
  const connections = useData<{ integrations: Integration[] }>("/api/v1/integrations");
  const queries = [
    connections,
    campaigns,
    sequences,
    versions,
    enrollments,
    scheduled,
    drafts,
    messages,
    suppressions,
    senders,
    contacts,
    jobs,
    delivery,
  ];
  const suppressed = (email: string) =>
    suppressions.data?.some((s) => s.email.toLowerCase() === email.toLowerCase()) || false;
  async function act(path: string, body?: unknown, after?: (value: unknown) => void) {
    setBusy(true);
    setMessage("");
    try {
      const result = await apiFetch(base + path, {
        method: "POST",
        body: body === undefined ? null : JSON.stringify(body),
      });
      await cache.invalidateQueries({ queryKey: ["customer"] });
      after?.(result);
      setMessage("Saved. No send is inferred from this action.");
    } catch (e) {
      setMessage(friendlyError(e));
    } finally {
      setBusy(false);
    }
  }
  function formData(form: HTMLFormElement) {
    return Object.fromEntries(new FormData(form));
  }
  return (
    <>
      <Heading
        title="Outreach"
        description="Thoughtful outreach, with a deliberate review at every step. Drafting, approval and provider confirmation stay separate."
        action={
          <button
            className="g-button g-button-secondary"
            onClick={() => queries.forEach((q) => void q.refetch())}
          >
            Refresh states
          </button>
        }
      />
      <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
        {["Draft", "Review", "Approved", "Scheduled", "Provider-confirmed sent"].map((s, i) => (
          <span key={s} className="rounded-full border bg-card px-3 py-2">
            {i + 1}. {s}
          </span>
        ))}
      </div>
      <Feedback message={message} />
      <nav aria-label="Outreach views" className="flex flex-wrap gap-2">
        {["Messages", "Campaigns & sequences", "Enrollments", "Safety"].map((t) => (
          <button
            key={t}
            aria-pressed={tab === t}
            className={`g-button ${tab === t ? "" : "g-button-secondary"}`}
            onClick={() => setTab(t)}
          >
            {t}
          </button>
        ))}
      </nav>
      {queries.some((q) => q.isPending) ? (
        <Loading />
      ) : queries.some((q) => q.isError) ? (
        <ErrorState retry={() => queries.forEach((q) => void q.refetch())} />
      ) : (
        <>
          {tab === "Messages" && (
            <>
              {!scheduled.data?.length ? (
                <Empty title="A considered first impression">
                  Create a campaign and sequence, then enroll a researched contact. Scheduled steps
                  become drafts for your review.
                </Empty>
              ) : (
                <div className="grid gap-4 lg:grid-cols-2">
                  {scheduled.data.map((s) => {
                    const enrollment = enrollments.data?.find((e) => e.id === s.enrollment_id);
                    const contact = contacts.data?.find((c) => c.id === enrollment?.contact_id);
                    const draft = drafts.data?.find((d) => d.scheduled_id === s.id);
                    const sent = messages.data?.find((m) => m.scheduled_id === s.id);
                    const blocked = contact?.email ? suppressed(contact.email) : false;
                    return (
                      <Panel key={s.id}>
                        <div className="flex flex-wrap justify-between gap-3">
                          <h2 className="font-semibold">
                            {contact ? `${contact.first_name} ${contact.last_name}` : "Contact"}
                          </h2>
                          <Status
                            value={
                              blocked
                                ? "suppressed"
                                : (sent ? sendLabel(sent) : undefined) ||
                                  (draft ? "draft" : "scheduled")
                            }
                          />
                        </div>
                        <p className="mt-2 text-sm text-muted-foreground">
                          {contact?.email || "Email unknown"}
                        </p>
                        <p className="mt-4 text-sm">Due {time(s.due_at)}</p>
                        <p className="mt-2 text-sm">
                          {blocked
                            ? "Do not contact — suppression blocks outreach."
                            : sent
                              ? sendLabel(sent)
                              : "Not sent. Review and approval required."}
                        </p>
                        {sent && (
                          <div className="mt-3 text-xs text-muted-foreground">
                            {delivery.data
                              ?.filter((d) => d.message_id === sent.id)
                              .map((d) => (
                                <p key={d.id}>
                                  Delivery: {d.kind.replaceAll("_", " ")} · {time(d.created_at)}
                                </p>
                              ))}
                          </div>
                        )}
                        <div className="mt-5 flex flex-wrap gap-2">
                          {draft ? (
                            <button
                              className="g-button g-button-secondary"
                              onClick={() => {
                                setSelected(draft);
                                setReviewed(false);
                                setPlan(null);
                              }}
                            >
                              Review message
                            </button>
                          ) : (
                            canEdit && (
                              <button
                                className="g-button"
                                disabled={busy || blocked || enrollment?.status !== "active"}
                                onClick={() =>
                                  void act(`/scheduled/${s.id}/drafts`, undefined, (v) => {
                                    setSelected(v as Draft);
                                    setReviewed(false);
                                    setPlan(null);
                                  })
                                }
                              >
                                Prepare draft
                              </button>
                            )
                          )}
                          {sent?.state === "failed" && canApprove && (
                            <button
                              className="g-button g-button-secondary"
                              disabled={busy || blocked}
                              onClick={() => void act(`/messages/${sent.id}/retry`)}
                            >
                              Retry approved send
                            </button>
                          )}
                        </div>
                      </Panel>
                    );
                  })}
                </div>
              )}
              {selected && (
                <Panel title="Review the exact message">
                  <p className="text-sm">
                    From {selected.envelope.sender} → {selected.envelope.recipient}
                  </p>
                  <h3 className="mt-5 font-semibold">{selected.envelope.subject}</h3>
                  <p className="my-5 whitespace-pre-wrap text-sm leading-7">
                    {selected.envelope.body}
                  </p>
                  <details className="my-4 text-xs">
                    <summary>Evidence & immutable versions</summary>
                    <div className="mt-3 space-y-2 break-all">
                      <p>
                        Research {selected.envelope.research_job_id} · Evidence{" "}
                        {selected.envelope.evidence_id}
                      </p>
                      <p>
                        Brain {selected.envelope.brain_version_id} · Sequence version{" "}
                        {selected.envelope.sequence_version_id}
                      </p>
                      <p>Earliest send: {time(selected.envelope.due_at)}</p>
                    </div>
                  </details>
                  {suppressed(selected.envelope.recipient) ? (
                    <p className="font-medium text-destructive">
                      Suppressed — this message cannot be sent.
                    </p>
                  ) : (
                    canApprove && (
                      <>
                        <label className="flex items-start gap-3 text-sm">
                          <input
                            type="checkbox"
                            checked={reviewed}
                            onChange={(e) => setReviewed(e.target.checked)}
                          />
                          I reviewed the recipient, message and supporting evidence.
                        </label>
                        <button
                          className="g-button mt-4"
                          disabled={!reviewed || busy}
                          onClick={() =>
                            void act(
                              `/drafts/${selected.id}/approve`,
                              { content_hash: selected.content_hash, reviewed: true },
                              (v) => setPlan((v as { plan: ReviewedPlan }).plan),
                            )
                          }
                        >
                          Approve message & review execution plan
                        </button>
                      </>
                    )
                  )}
                  {!canApprove && (
                    <p className="text-sm">An owner or admin must approve outbound messages.</p>
                  )}
                </Panel>
              )}
              {plan && (
                <PlanReview
                  key={plan.id}
                  plan={plan}
                  onApproved={() => void cache.invalidateQueries({ queryKey: ["customer"] })}
                />
              )}
            </>
          )}
          {tab === "Campaigns & sequences" && (
            <>
              <div className="grid gap-4 lg:grid-cols-2">
                {campaigns.data?.map((c) => (
                  <Panel key={c.id} title={c.name}>
                    <Status value={c.status} />
                    {sequences.data
                      ?.filter((s) => s.campaign_id === c.id)
                      .map((s) => (
                        <div key={s.id} className="mt-5 border-t pt-4">
                          <h3 className="font-semibold">{s.name}</h3>
                          {versions.data
                            ?.filter((v) => v.sequence_id === s.id)
                            .map((v) => (
                              <details key={v.id} className="mt-3 text-sm">
                                <summary>Version {v.number} · immutable</summary>
                                <ol className="mt-3 list-inside list-decimal">
                                  {v.definition.steps.map((step, i) => (
                                    <li key={i}>
                                      {step.purpose} · wait {step.delay_seconds / 3600} hours
                                    </li>
                                  ))}
                                </ol>
                              </details>
                            ))}
                        </div>
                      ))}
                    {canApprove && c.status !== "cancelled" && (
                      <button
                        className="g-button g-button-secondary mt-5"
                        disabled={busy}
                        onClick={() =>
                          void act(`/campaigns/${c.id}/control`, {
                            status: c.status === "active" ? "paused" : "active",
                          })
                        }
                      >
                        {c.status === "active" ? "Pause campaign" : "Resume campaign"}
                      </button>
                    )}
                  </Panel>
                ))}
              </div>
              {canEdit && (
                <div className="grid gap-4 lg:grid-cols-3">
                  <Panel title="Create campaign">
                    <form
                      className="space-y-4"
                      onSubmit={(e) => {
                        e.preventDefault();
                        void act("/campaigns", formData(e.currentTarget));
                      }}
                    >
                      <Field label="Campaign name">
                        <input name="name" className="g-input" required maxLength={200} />
                      </Field>
                      <button className="g-button" disabled={busy}>
                        Create campaign
                      </button>
                    </form>
                  </Panel>
                  <Panel title="Create sequence">
                    <form
                      className="space-y-4"
                      onSubmit={(e) => {
                        e.preventDefault();
                        void act("/sequences", formData(e.currentTarget));
                      }}
                    >
                      <Field label="Campaign">
                        <select name="campaign_id" className="g-input" required>
                          <option value="">Choose campaign</option>
                          {campaigns.data?.map((c) => (
                            <option key={c.id} value={c.id}>
                              {c.name}
                            </option>
                          ))}
                        </select>
                      </Field>
                      <Field label="Sequence name">
                        <input name="name" className="g-input" required maxLength={200} />
                      </Field>
                      <button className="g-button" disabled={busy}>
                        Create sequence
                      </button>
                    </form>
                  </Panel>
                  <Panel title="Publish new sequence version">
                    <form
                      className="space-y-4"
                      onSubmit={(e) => {
                        e.preventDefault();
                        const f = formData(e.currentTarget);
                        void act(`/sequences/${f["sequence"]}/versions`, {
                          steps: String(f["steps"])
                            .split("\n")
                            .filter((s) => s.trim())
                            .map((purpose, i) => ({ purpose, delay_seconds: i ? 86400 : 0 })),
                        });
                      }}
                    >
                      <Field label="Sequence">
                        <select name="sequence" className="g-input" required>
                          <option value="">Choose sequence</option>
                          {sequences.data?.map((s) => (
                            <option key={s.id} value={s.id}>
                              {s.name}
                            </option>
                          ))}
                        </select>
                      </Field>
                      <Field label="Step purposes (one per line, up to ten)">
                        <textarea name="steps" className="g-input" required rows={4} />
                      </Field>
                      <p className="text-xs text-muted-foreground">
                        First step is immediate; later steps wait one day each. Existing versions
                        and enrollments remain unchanged.
                      </p>
                      <button className="g-button" disabled={busy}>
                        Create immutable version
                      </button>
                    </form>
                  </Panel>
                </div>
              )}
            </>
          )}
          {tab === "Enrollments" && (
            <>
              <div className="grid gap-4 lg:grid-cols-2">
                {enrollments.data?.map((e) => (
                  <Panel key={e.id}>
                    <p className="font-medium">
                      {contacts.data?.find((c) => c.id === e.contact_id)?.email || "Contact"}
                    </p>
                    <p className="mt-2 text-sm">
                      Sequence version{" "}
                      {versions.data?.find((v) => v.id === e.version_id)?.number || "unknown"}
                    </p>
                    <Status value={e.status} />
                    {canApprove && e.status !== "cancelled" && (
                      <button
                        className="g-button g-button-secondary ml-3"
                        disabled={busy}
                        onClick={() =>
                          void act(`/enrollments/${e.id}/control`, {
                            status: e.status === "active" ? "paused" : "active",
                          })
                        }
                      >
                        {e.status === "active" ? "Pause" : "Request resume"}
                      </button>
                    )}
                  </Panel>
                ))}
              </div>
              {canEdit && (
                <Panel title="Enroll a researched contact">
                  <form
                    className="grid gap-4 md:grid-cols-2"
                    onSubmit={(e) => {
                      e.preventDefault();
                      void act("/enrollments", formData(e.currentTarget));
                    }}
                  >
                    <Field label="Contact">
                      <select className="g-input" name="contact_id" required>
                        <option value="">Select contact</option>
                        {contacts.data?.map((c) => (
                          <option
                            disabled={Boolean(c.email && suppressed(c.email))}
                            key={c.id}
                            value={c.id}
                          >
                            {c.first_name} {c.last_name} · {c.email}
                            {c.email && suppressed(c.email) ? " · Suppressed" : ""}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field label="Sequence version">
                      <select className="g-input" name="version_id" required>
                        <option value="">Select version</option>
                        {versions.data?.map((v) => (
                          <option key={v.id} value={v.id}>
                            {sequences.data?.find((s) => s.id === v.sequence_id)?.name} · v
                            {v.number}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field label="Sender">
                      <select className="g-input" name="sender_id" required>
                        <option value="">Select sender</option>
                        {senders.data?.map((s) => (
                          <option key={s.id} value={s.id}>
                            {s.email} · {s.status}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field label="Completed research for this account">
                      <select className="g-input" name="research_job_id" required>
                        <option value="">Select research</option>
                        {jobs.data
                          ?.filter((j) => j.status === "completed")
                          .map((j) => (
                            <option key={j.id} value={j.id}>
                              Account {j.company_id} · Research {j.id.slice(0, 8)}
                            </option>
                          ))}
                      </select>
                    </Field>
                    <p className="text-xs text-muted-foreground">
                      The account, research, sender, consent and sequence are checked again by the
                      server. Enrollment does not send.
                    </p>
                    <button disabled={busy} className="g-button">
                      Enroll contact
                    </button>
                  </form>
                </Panel>
              )}
            </>
          )}
          {tab === "Safety" && (
            <>
              <Panel title="Suppression & unsubscribe">
                <p className="mb-4 text-sm text-muted-foreground">
                  Suppressed contacts cannot be contacted. Suppression is retained even when a reply
                  classification changes.
                </p>
                {suppressions.data?.map((s) => (
                  <p key={s.id} className="my-3 text-sm">
                    {s.email} <Status value={s.reason} />
                  </p>
                ))}
                {!suppressions.data?.length && (
                  <p className="text-sm">No suppressed contacts recorded.</p>
                )}
                {canEdit && (
                  <form
                    className="mt-5 flex flex-wrap items-end gap-4"
                    onSubmit={(e) => {
                      e.preventDefault();
                      void act("/suppressions", {
                        ...formData(e.currentTarget),
                        reason: "suppressed",
                      });
                    }}
                  >
                    <Field label="Email to suppress">
                      <input name="email" type="email" className="g-input" required />
                    </Field>
                    <button disabled={busy} className="g-button">
                      Block outreach to this address
                    </button>
                  </form>
                )}
              </Panel>
              <Panel title="Sender identities">
                {canApprove && (
                  <form
                    className="mb-5 grid gap-4 md:grid-cols-2"
                    onSubmit={(e) => {
                      e.preventDefault();
                      const data = formData(e.currentTarget);
                      const connection = connections.data?.integrations.find(
                        (i) => i.id === data["integration_id"],
                      );
                      if (connection)
                        void act("/senders", {
                          email: data["email"],
                          integration_id: connection.id,
                          provider: connection.provider,
                        });
                    }}
                  >
                    <Field label="Sending address">
                      <input type="email" name="email" className="g-input" required />
                    </Field>
                    <Field label="Email connection">
                      <select name="integration_id" className="g-input" required>
                        <option value="">Select connection</option>
                        {connections.data?.integrations
                          .filter(
                            (i) =>
                              i.category === "email" && ["gmail", "outlook"].includes(i.provider),
                          )
                          .map((i) => (
                            <option key={i.id} value={i.id}>
                              {i.provider} � {i.health}
                            </option>
                          ))}
                      </select>
                    </Field>
                    <button className="g-button" disabled={busy}>
                      Save sender identity
                    </button>
                  </form>
                )}
                {senders.data?.map((s) => (
                  <p key={s.id} className="my-3 text-sm">
                    {s.email} <Status value={s.status} />
                  </p>
                ))}
                <p className="mt-4 text-sm text-muted-foreground">
                  Live sending is disabled at this checkpoint. Sender connection does not imply
                  permission to send.
                </p>
              </Panel>
            </>
          )}
          <p className="text-xs text-muted-foreground">
            Showing up to 100 records per collection. Refresh to retrieve confirmed changes.
          </p>
        </>
      )}
    </>
  );
}
