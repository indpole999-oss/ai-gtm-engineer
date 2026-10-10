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
import { STAGES, type Pipeline, type Company, type Contact } from "./contracts";
type Outcome = {
  id: string;
  pipeline_id: string;
  kind: string;
  state: string;
  confirmed_at: string | null;
  external_id: string | null;
  meeting?: { title: string; start_at: string; timezone: string; status: string };
};
export function PipelinePage() {
  const { canApprove } = useWorkspace();
  const cache = useQueryClient();
  const [offset, setOffset] = useState(0),
    [selected, setSelected] = useState(""),
    [filter, setFilter] = useState("all"),
    [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false);
  const rows = useData<Pipeline[]>(`/api/v1/outcomes/pipeline?limit=100&offset=${offset}`),
    companies = useData<Company[]>("/api/v1/companies/"),
    contacts = useData<Contact[]>("/api/v1/contacts/"),
    meetings = useData<Outcome[]>("/api/v1/outcomes/calendar/meetings"),
    mappings = useData<
      { id: string; pipeline_id: string; sync_state: string; last_success_at: string | null }[]
    >("/api/v1/outcomes/crm/mappings"),
    detail = useData<Pipeline>(`/api/v1/outcomes/pipeline/${selected}`, Boolean(selected));
  const queries = [rows, companies, contacts, meetings, mappings];
  function name(p: Pipeline) {
    const c = contacts.data?.find((c) => c.id === p.contact_id);
    return c
      ? `${c.first_name} ${c.last_name}`
      : companies.data?.find((c) => c.id === p.company_id)?.name || "Account";
  }
  async function correct(form: HTMLFormElement) {
    if (!detail.data) return;
    setBusy(true);
    try {
      const f = new FormData(form);
      await apiFetch(`/api/v1/outcomes/pipeline/${selected}/stage`, {
        method: "POST",
        body: JSON.stringify({
          stage: f.get("stage"),
          expected_revision: detail.data.revision,
          reason: f.get("reason"),
          evidence_kind: "explicit_user",
          reviewed: true,
        }),
      });
      await cache.invalidateQueries({ queryKey: ["customer"] });
      setMessage("Reviewed outcome saved. The original history is retained.");
    } catch (e) {
      setMessage(friendlyError(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Heading
        title="Pipeline"
        description="A clear view of progress, with the evidence behind every transition. Meetings require provider confirmation; business outcomes require explicit review."
      />
      <Feedback message={message} />
      <div className="flex flex-wrap gap-2" aria-label="Pipeline stages">
        <button
          className="g-button g-button-secondary"
          aria-pressed={filter === "all"}
          onClick={() => setFilter("all")}
        >
          All stages
        </button>
        {STAGES.map((s) => (
          <button
            key={s}
            aria-pressed={filter === s}
            onClick={() => setFilter(s)}
            className={`g-button capitalize ${filter === s ? "" : "g-button-secondary"}`}
          >
            {s}
          </button>
        ))}
      </div>
      {queries.some((q) => q.isPending) ? (
        <Loading />
      ) : queries.some((q) => q.isError) ? (
        <ErrorState retry={() => queries.forEach((q) => void q.refetch())} />
      ) : !rows.data?.length ? (
        <Empty title="Progress starts with a prospect">
          Add an account in Prospects. Research, conversations and confirmed outcomes build its
          evidence-backed history.
        </Empty>
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {rows.data
              .filter((p) => filter === "all" || p.stage === filter)
              .map((p) => (
                <Panel key={p.id}>
                  <Status value={p.stage} />
                  <h2 className="mt-4 text-lg font-semibold">{name(p)}</h2>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {p.contact_id ? "Contact" : "Account"} ·{" "}
                    {companies.data?.find((c) => c.id === p.company_id)?.name}
                  </p>
                  <div className="mt-4 space-y-2 text-sm">
                    {meetings.data
                      ?.filter((m) => m.pipeline_id === p.id)
                      .map((m) => (
                        <p key={m.id}>
                          {m.meeting?.title || "Meeting"}:{" "}
                          {m.state === "confirmed" && m.external_id
                            ? "Provider-confirmed scheduling"
                            : m.state.replaceAll("_", " ")}{" "}
                          · {time(m.meeting?.start_at)}
                        </p>
                      ))}
                    {mappings.data
                      ?.filter((m) => m.pipeline_id === p.id)
                      .map((m) => (
                        <p key={m.id}>
                          CRM <Status value={m.sync_state} /> · Last confirmed{" "}
                          {time(m.last_success_at)}
                        </p>
                      ))}
                  </div>
                  <button
                    className="mt-5 text-sm font-semibold text-primary"
                    onClick={() => setSelected(p.id)}
                  >
                    View stage history →
                  </button>
                </Panel>
              ))}
          </div>
          <div className="flex gap-4 text-sm">
            <button disabled={!offset} onClick={() => setOffset(Math.max(0, offset - 100))}>
              Previous
            </button>
            <button disabled={rows.data.length < 100} onClick={() => setOffset(offset + 100)}>
              Next
            </button>
            <span className="text-muted-foreground">
              Filters apply to this page of up to 100 records.
            </span>
          </div>
        </>
      )}
      {selected &&
        (detail.isPending ? (
          <Loading />
        ) : detail.isError ? (
          <ErrorState error={detail.error} retry={() => void detail.refetch()} />
        ) : (
          detail.data && (
            <Panel title={`${name(detail.data)} · Stage history`}>
              <ol className="space-y-5">
                {detail.data.history?.map((h) => (
                  <li key={h.id} className="border-l-2 pl-5">
                    <div className="flex flex-wrap items-center gap-3">
                      <Status value={h.to_stage} />
                      <span className="text-xs text-muted-foreground">
                        {time(h.created_at)} · {h.applied ? "Applied" : "Recorded, not applied"}
                      </span>
                    </div>
                    <p className="mt-2 text-sm">{h.reason}</p>
                    <details className="mt-2 text-xs text-muted-foreground">
                      <summary>Source evidence</summary>
                      <p className="mt-2">{h.source.replaceAll("_", " ")}</p>
                      {Object.entries(h.evidence).map(([k, v]) => (
                        <p className="break-all" key={k}>
                          {k.replaceAll("_", " ")}: {String(v)}
                        </p>
                      ))}
                    </details>
                  </li>
                ))}
              </ol>
              {canApprove && (
                <details className="mt-6">
                  <summary className="text-sm font-medium">
                    Record a reviewed business outcome
                  </summary>
                  <form
                    className="mt-4 space-y-4"
                    onSubmit={(e) => {
                      e.preventDefault();
                      void correct(e.currentTarget);
                    }}
                  >
                    <Field label="Outcome">
                      <select name="stage" className="g-input">
                        {["opportunity", "won", "lost"].map((s) => (
                          <option key={s} value={s}>
                            {s}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field label="Business evidence and reason">
                      <textarea
                        className="g-input"
                        name="reason"
                        minLength={10}
                        maxLength={3000}
                        required
                      />
                    </Field>
                    <label className="flex gap-3 text-sm">
                      <input type="checkbox" required />I reviewed this outcome. Previous history
                      will remain visible; this does not establish revenue.
                    </label>
                    <button disabled={busy} className="g-button">
                      Record reviewed outcome
                    </button>
                  </form>
                </details>
              )}
            </Panel>
          )
        ))}
    </>
  );
}
