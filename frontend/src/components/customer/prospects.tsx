import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { apiFetch } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace";
import {
  Heading,
  Panel,
  Loading,
  ErrorState,
  Empty,
  Status,
  Field,
  Feedback,
  friendlyError,
  useData,
} from "./ui";
import type { Company, Contact, Pipeline } from "./contracts";

type Research = { id: string; company_id: string; status: string };
type Report = {
  intelligence: {
    fit: string;
    why_company: { reasoning: string };
    why_now: { reasoning: string };
    buyers: {
      name: string;
      title: string;
      email: string | null;
      reasoning: string;
      verification_status: string;
    }[];
    brain_version_id: string;
  } | null;
  claims: {
    id: string;
    text: string;
    excerpt: string;
    confidence: number | null;
    url: string | null;
    kind: string;
    freshness: string;
  }[];
};
function Evidence({ job }: { job: Research }) {
  const q = useData<Report>(`/api/v1/research/jobs/${job.id}`);
  if (q.isPending) return <Loading />;
  if (q.isError) return <ErrorState error={q.error} retry={() => void q.refetch()} />;
  const r = q.data;
  return (
    <div className="mt-5 space-y-5">
      {r?.intelligence ? (
        <>
          <div className="grid gap-5 md:grid-cols-2">
            <div>
              <h3 className="font-semibold">Why this company</h3>
              <p className="mt-2 text-sm leading-6">{r.intelligence.why_company.reasoning}</p>
            </div>
            <div>
              <h3 className="font-semibold">Why now</h3>
              <p className="mt-2 text-sm leading-6">{r.intelligence.why_now.reasoning}</p>
            </div>
          </div>
          <h3 className="font-semibold">Recommended buyers</h3>
          {r.intelligence.buyers.map((b, i) => (
            <div key={i} className="rounded-xl bg-muted p-4">
              <p className="font-medium">
                {b.name} · {b.title}
              </p>
              <p className="mt-2 text-sm">{b.reasoning}</p>
              <p className="mt-2 text-xs">
                {b.email || "Email unknown"} · Verification: {b.verification_status}
              </p>
            </div>
          ))}
          <p className="break-all text-xs text-muted-foreground">
            Company Brain version: {r.intelligence.brain_version_id}
          </p>
        </>
      ) : (
        <p>Research is not complete. No qualification or buyer information is inferred.</p>
      )}
      <details>
        <summary className="text-sm font-medium">Supporting evidence</summary>
        <div className="mt-4 space-y-4">
          {r?.claims.map((c) => (
            <article key={c.id} className="border-t pt-4">
              <p className="text-sm">{c.text}</p>
              <blockquote className="my-3 border-l-2 pl-4 text-sm text-muted-foreground">
                {c.excerpt || "No source excerpt"}
              </blockquote>
              <p className="text-xs">
                {c.kind.replaceAll("_", " ")} · Confidence{" "}
                {c.confidence === null ? "unknown" : c.confidence} ·{" "}
                {c.freshness.replaceAll("_", " ")}
              </p>
              {c.url && /^https?:\/\//i.test(c.url) && (
                <a
                  className="mt-2 block break-all text-sm text-primary underline"
                  href={c.url}
                  target="_blank"
                  rel="noreferrer"
                >
                  View source
                </a>
              )}
            </article>
          ))}
        </div>
      </details>
    </div>
  );
}
export function ProspectsPage() {
  const { canEdit } = useWorkspace();
  const cache = useQueryClient();
  const accounts = useData<Company[]>("/api/v1/companies/");
  const contacts = useData<Contact[]>("/api/v1/contacts/");
  const pipelines = useData<Pipeline[]>("/api/v1/outcomes/pipeline?limit=100");
  const jobs = useData<Research[]>("/api/v1/research/jobs");
  const [expanded, setExpanded] = useState("");
  const [search, setSearch] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const queries = [accounts, contacts, pipelines, jobs];
  const matchingAccounts = accounts.data?.filter((account) =>
    `${account.name} ${account.domain || ""}`.toLowerCase().includes(search.trim().toLowerCase()),
  );
  async function add(form: HTMLFormElement) {
    setBusy(true);
    try {
      const data = new FormData(form);
      await apiFetch("/api/v1/companies/", {
        method: "POST",
        body: JSON.stringify({ name: data.get("name"), domain: data.get("domain") || null }),
      });
      await cache.invalidateQueries({ queryKey: ["customer"] });
      form.reset();
      setMessage("Account added. Create a reviewed research plan in AI GTM to assess fit.");
    } catch (e) {
      setMessage(friendlyError(e));
    } finally {
      setBusy(false);
    }
  }
  async function addContact(form: HTMLFormElement, companyId: string) {
    if (!canEdit) return;
    setBusy(true);
    try {
      await apiFetch("/api/v1/contacts/", {
        method: "POST",
        body: JSON.stringify({ ...Object.fromEntries(new FormData(form)), company_id: companyId }),
      });
      await cache.invalidateQueries({ queryKey: ["customer"] });
      form.reset();
      setMessage("Contact saved as supplied. Research and email verification remain separate.");
    } catch (e) {
      setMessage(friendlyError(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Heading
        title="Prospects"
        description="Know who to reach, why they fit, and what supports the decision. Research observations remain visibly distinct from verified facts."
        action={
          <Link to="/dashboard" className="g-button">
            Plan account research ↗
          </Link>
        }
      />
      <Feedback message={message} />
      <div className="flex flex-wrap items-center gap-4">
        <input
          aria-label="Search accounts"
          className="g-input max-w-md"
          placeholder="Search accounts…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        {canEdit && (
          <details className="w-full">
            <summary className="text-sm font-medium">Add an account</summary>
            <form
              className="g-panel mt-3 grid gap-4 md:grid-cols-3"
              onSubmit={(e) => {
                e.preventDefault();
                void add(e.currentTarget);
              }}
            >
              <Field label="Company name">
                <input className="g-input" name="name" required maxLength={255} />
              </Field>
              <Field label="Domain">
                <input
                  className="g-input"
                  name="domain"
                  placeholder="example.com"
                  maxLength={255}
                />
              </Field>
              <button disabled={busy} className="g-button self-end">
                Add account
              </button>
            </form>
          </details>
        )}
      </div>
      {queries.some((q) => q.isPending) ? (
        <Loading />
      ) : queries.some((q) => q.isError) ? (
        <ErrorState retry={() => queries.forEach((q) => void q.refetch())} />
      ) : !accounts.data?.length ? (
        <Empty title="Your next opportunity starts with an account">
          Add an account, then prepare a research plan in AI GTM. Qualified prospects will appear
          here with supporting evidence.
        </Empty>
      ) : !matchingAccounts?.length ? (
        <Empty title="No accounts match your search">
          <p>Try a different company name or domain.</p>
          <button className="g-button g-button-secondary mt-4" onClick={() => setSearch("")}>
            Clear search
          </button>
        </Empty>
      ) : (
        <div className="space-y-4">
          {matchingAccounts.map((a) => {
            const p = pipelines.data?.find((p) => p.company_id === a.id && !p.contact_id);
            const job = jobs.data?.find((j) => j.company_id === a.id && j.status === "completed");
            return (
              <Panel key={a.id}>
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <p className="eyebrow">ACCOUNT</p>
                    <h2 className="mt-2 text-xl font-semibold">{a.name}</h2>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {a.domain || "Domain unknown"}
                    </p>
                  </div>
                  <Status value={p?.stage || "unknown"} />
                </div>
                <p className="mt-4 text-sm text-muted-foreground">
                  {job
                    ? "Research evidence is available for review."
                    : "Qualification is not yet supported by completed research."}
                </p>
                <div className="mt-5 flex flex-wrap gap-2">
                  {contacts.data
                    ?.filter((c) => c.company_id === a.id)
                    .map((c) => (
                      <span key={c.id} className="g-status">
                        {c.first_name} {c.last_name} · {c.title || "Role unknown"}
                      </span>
                    ))}
                </div>
                <button
                  aria-expanded={expanded === a.id}
                  className="mt-6 text-sm font-semibold text-primary"
                  onClick={() => setExpanded(expanded === a.id ? "" : a.id)}
                >
                  {expanded === a.id ? "Close details" : "Explore account & evidence →"}
                </button>
                {expanded === a.id && canEdit && (
                  <details className="mt-5">
                    <summary className="text-sm font-medium">Add a contact</summary>
                    <form
                      className="mt-4 grid gap-4 md:grid-cols-2"
                      onSubmit={(e) => {
                        e.preventDefault();
                        void addContact(e.currentTarget, a.id);
                      }}
                    >
                      <Field label="First name">
                        <input name="first_name" className="g-input" required maxLength={100} />
                      </Field>
                      <Field label="Last name">
                        <input name="last_name" className="g-input" required maxLength={100} />
                      </Field>
                      <Field label="Email">
                        <input name="email" type="email" className="g-input" required />
                      </Field>
                      <Field label="Job title">
                        <input name="title" className="g-input" maxLength={255} />
                      </Field>
                      <p className="text-xs text-muted-foreground">
                        Manually entered contact details are not independently verified.
                      </p>
                      <button className="g-button" disabled={busy}>
                        Save contact
                      </button>
                    </form>
                  </details>
                )}
                {expanded === a.id &&
                  (job ? (
                    <Evidence job={job} />
                  ) : (
                    <p className="mt-4 text-sm">
                      No completed research. Use AI GTM to review and approve a research plan.
                    </p>
                  ))}
              </Panel>
            );
          })}
        </div>
      )}
    </>
  );
}
