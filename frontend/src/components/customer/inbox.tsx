import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace";
import {
  Heading,
  Panel,
  Loading,
  ErrorState,
  Empty,
  Status,
  Feedback,
  Field,
  friendlyError,
  useData,
  time,
} from "./ui";
import { sendLabel } from "./contracts";
type Reply = {
  id: string;
  sender_email: string;
  subject: string;
  body: string;
  received_at: string;
  auto_submitted: string;
  suppressed: boolean;
  sequence_holds: { id: string; reason: string }[];
  classification: null | {
    number: number;
    category: string;
    confidence: number | null;
    reason: string;
    recommended_action: string;
  };
  suggested_replies: { id: string; subject: string; body: string; status: string }[];
};
type Thread = {
  messages: Reply[];
  outbound_messages: {
    id: string;
    state: string;
    provider_message_id: string | null;
    accepted_at: string | null;
    envelope: { subject: string; body: string; recipient: string };
  }[];
};
const categories = [
  "positive",
  "negative",
  "objection",
  "out_of_office",
  "wrong_person",
  "question",
  "meeting_intent",
  "unsubscribe",
  "other",
];
export function InboxPage() {
  const { canEdit, canApprove } = useWorkspace();
  const cache = useQueryClient();
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState("");
  const [page, setPage] = useState(0);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const threads = useData<{ id: string; created_at: string }[]>(
    `/api/v1/inbox/threads?limit=50&offset=${offset}`,
  );
  const detail = useData<Thread>(
    `/api/v1/inbox/threads/${selected}?offset=${page}&limit=100`,
    Boolean(selected),
  );
  async function act(id: string, action: string, body?: unknown) {
    setBusy(true);
    setMessage("");
    try {
      await apiFetch(`/api/v1/inbox/messages/${id}/${action}`, {
        method: "POST",
        body: body === undefined ? null : JSON.stringify(body),
      });
      await cache.invalidateQueries({ queryKey: ["customer"] });
      setMessage(
        action === "suggested-reply"
          ? "Reply draft prepared. Nothing has been sent."
          : "Reviewed classification saved. Existing suppression remains in force.",
      );
    } catch (e) {
      setMessage(friendlyError(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Heading
        title="Inbox"
        description="Every reply brings context. Read the conversation, review its meaning, and choose the next step."
        action={
          <button
            className="g-button g-button-secondary"
            onClick={() => {
              void threads.refetch();
              if (selected) void detail.refetch();
            }}
          >
            Refresh inbox
          </button>
        }
      />
      <Feedback message={message} />
      {threads.isPending ? (
        <Loading />
      ) : threads.isError ? (
        <ErrorState error={threads.error} retry={() => void threads.refetch()} />
      ) : !threads.data?.length ? (
        <Empty title="Ready for the first conversation">
          Replies linked to your outreach will appear here. Suggested responses remain drafts until
          separately reviewed.
        </Empty>
      ) : (
        <div className="grid items-start gap-5 lg:grid-cols-[260px_minmax(0,1fr)]">
          <Panel title="Conversations">
            <div className="space-y-2">
              {threads.data.map((t, i) => (
                <button
                  key={t.id}
                  aria-pressed={selected === t.id}
                  className={`w-full rounded-xl p-3 text-left ${selected === t.id ? "bg-accent" : "hover:bg-muted"}`}
                  onClick={() => {
                    setSelected(t.id);
                    setPage(0);
                  }}
                >
                  <span className="block text-sm font-semibold">Conversation {offset + i + 1}</span>
                  <span className="mt-1 block text-xs text-muted-foreground">
                    Started {time(t.created_at)}
                  </span>
                </button>
              ))}
            </div>
            <div className="mt-4 flex gap-3">
              <button
                disabled={!offset}
                className="text-sm disabled:opacity-40"
                onClick={() => setOffset(Math.max(0, offset - 50))}
              >
                Previous
              </button>
              <button
                disabled={threads.data.length < 50}
                className="text-sm disabled:opacity-40"
                onClick={() => setOffset(offset + 50)}
              >
                Next
              </button>
            </div>
          </Panel>
          <div className="space-y-4">
            {!selected ? (
              <Empty title="A little context goes a long way">
                Choose a conversation to view the original outreach, replies, classification and
                next action.
              </Empty>
            ) : detail.isPending ? (
              <Loading />
            ) : detail.isError ? (
              <ErrorState error={detail.error} retry={() => void detail.refetch()} />
            ) : (
              <>
                {detail.data?.outbound_messages.map((m) => (
                  <Panel key={m.id}>
                    <p className="eyebrow">OUTBOUND · {sendLabel(m)}</p>
                    <h2 className="mt-3 font-semibold">{m.envelope.subject}</h2>
                    <p className="mt-2 text-xs text-muted-foreground">
                      To {m.envelope.recipient} · {time(m.accepted_at)}
                    </p>
                    <p className="mt-5 whitespace-pre-wrap text-sm leading-7">{m.envelope.body}</p>
                  </Panel>
                ))}
                {detail.data?.messages.map((m) => (
                  <Panel key={m.id}>
                    <div className="flex flex-wrap justify-between gap-3">
                      <p className="eyebrow">INBOUND REPLY</p>
                      <Status value={m.classification?.category || "awaiting_classification"} />
                    </div>
                    <h2 className="mt-3 font-semibold">{m.subject}</h2>
                    <p className="mt-2 text-xs text-muted-foreground">
                      {m.sender_email} · {time(m.received_at)}
                    </p>
                    <p className="my-5 whitespace-pre-wrap text-sm leading-7">{m.body}</p>
                    {m.suppressed && (
                      <p className="mb-4 rounded-xl bg-destructive/10 p-4 text-sm font-semibold text-destructive">
                        Unsubscribed or suppressed — do not contact.
                      </p>
                    )}
                    {m.sequence_holds.length > 0 && (
                      <p className="mb-4 text-sm">
                        Sequence paused after this reply. Future steps are held for review.
                      </p>
                    )}
                    <div className="rounded-xl bg-muted p-4 text-sm">
                      <p>
                        {m.classification?.reason ||
                          "Classification is still pending. No intent is assumed."}
                      </p>
                      <p className="mt-2">
                        Confidence:{" "}
                        {m.classification?.confidence == null
                          ? "Unknown"
                          : m.classification.confidence}
                        . Next action:{" "}
                        {m.classification?.recommended_action.replaceAll("_", " ") ||
                          "Review the reply"}
                        .
                      </p>
                    </div>
                    <div className="mt-5 space-y-3">
                      {m.suggested_replies.map((d) => (
                        <article key={d.id} className="rounded-xl border p-4">
                          <Status value="draft" />
                          <h3 className="mt-3 font-medium">{d.subject}</h3>
                          <p className="mt-3 whitespace-pre-wrap text-sm">{d.body}</p>
                          <p className="mt-3 text-xs text-muted-foreground">
                            Suggested reply only. Not sent.
                          </p>
                        </article>
                      ))}
                    </div>
                    {canEdit && (
                      <button
                        disabled={busy || m.suppressed || !m.classification}
                        className="g-button g-button-secondary mt-4"
                        onClick={() => void act(m.id, "suggested-reply")}
                      >
                        Prepare suggested reply draft
                      </button>
                    )}
                    {canApprove && (
                      <details className="mt-5">
                        <summary className="text-sm font-medium">Review classification</summary>
                        <form
                          className="mt-4 space-y-4"
                          onSubmit={(e) => {
                            e.preventDefault();
                            const f = new FormData(e.currentTarget);
                            void act(m.id, "override", {
                              category: f.get("category"),
                              reason: f.get("reason"),
                              expected_number: m.classification?.number || 0,
                              reviewed: true,
                            });
                          }}
                        >
                          <Field label="Reviewed category">
                            <select
                              name="category"
                              className="g-input"
                              defaultValue={m.classification?.category || "other"}
                            >
                              {categories.map((c) => (
                                <option key={c} value={c}>
                                  {c.replaceAll("_", " ")}
                                </option>
                              ))}
                            </select>
                          </Field>
                          <Field label="Evidence and reason for correction">
                            <textarea
                              name="reason"
                              className="g-input"
                              required
                              minLength={10}
                              maxLength={3000}
                            />
                          </Field>
                          <label className="flex gap-3 text-sm">
                            <input type="checkbox" required />I reviewed the reply. This adds a new
                            classification version and does not remove suppression.
                          </label>
                          <button className="g-button" disabled={busy}>
                            Save reviewed classification
                          </button>
                        </form>
                      </details>
                    )}
                  </Panel>
                ))}
                <div className="flex gap-4 text-sm">
                  <button disabled={!page} onClick={() => setPage(Math.max(0, page - 100))}>
                    Earlier replies
                  </button>
                  <button
                    disabled={(detail.data?.messages.length || 0) < 100}
                    onClick={() => setPage(page + 100)}
                  >
                    Later replies
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}
