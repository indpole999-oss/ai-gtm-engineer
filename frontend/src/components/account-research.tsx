import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace";
import { friendlyError } from "./customer/ui";
import { Button } from "@/components/ui/button";

type Job = { id: string; status: string; error_code: string | null };
type Explanation = { reasoning: string; claim_indices: number[] };
type Claim = {
  id: string;
  text: string;
  kind: string;
  confidence: number;
  excerpt: string | null;
  url: string | null;
  title: string | null;
  publisher: string | null;
  retrieved_at: string | null;
  published_at: string | null;
  freshness: string;
  model_version: string;
};
type Report = Job & {
  claims: Claim[];
  intelligence: null | {
    fit: string;
    icp_used: string;
    brain_version_id: string;
    model_version: string;
    claim_ids: string[];
    why_company: Explanation;
    why_now: Explanation;
    buyers: (Explanation & {
      name: string;
      title: string;
      email: string | null;
      verification_status: string;
      verification_reason: string;
    })[];
  };
};

export function AccountResearch({ companyId }: { companyId: string }) {
  const cache = useQueryClient();
  const { workspace, canEdit } = useWorkspace();
  const [version, setVersion] = useState("");
  const [urls, setUrls] = useState("");
  const [selected, setSelected] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const versions = useQuery({
    queryKey: ["customer", workspace.id, "/api/v1/company-brain"],
    queryFn: ({ signal }) =>
      apiFetch<{ versions: { id: string; number: number; status: string }[] }>(
        "/api/v1/company-brain",
        { signal },
      ),
  });
  const jobs = useQuery({
    queryKey: ["research-jobs", workspace.id, companyId],
    queryFn: ({ signal }) =>
      apiFetch<Job[]>(`/api/v1/research/jobs?company_id=${companyId}`, { signal }),
  });
  const report = useQuery({
    queryKey: ["research-report", workspace.id, selected],
    queryFn: ({ signal }) => apiFetch<Report>(`/api/v1/research/jobs/${selected}`, { signal }),
    enabled: Boolean(selected),
  });
  const intelligence = report.data?.intelligence;
  async function run() {
    if (!canEdit) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const goal = await apiFetch<{ id: string }>("/api/v1/gtm/goals", {
        method: "POST",
        body: JSON.stringify({
          objective: "Research this account against our published Company Brain",
          brain_version_id: version,
          targets: [
            {
              company_id: companyId,
              source_urls: urls
                .split("\n")
                .map((s) => s.trim())
                .filter(Boolean),
            },
          ],
        }),
      });
      await cache.invalidateQueries({ queryKey: ["customer", workspace.id, "/api/v1/gtm/goals"] });
      await apiFetch(`/api/v1/gtm/goals/${goal.id}/plans`, {
        method: "POST",
        body: JSON.stringify({ mode: "research_template" }),
      });
      setMessage(
        "Research plan drafted. Review and approve it in the command center before execution.",
      );
      await cache.invalidateQueries({ queryKey: ["customer", workspace.id, "/api/v1/gtm/goals"] });
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setBusy(false);
      await cache.invalidateQueries({ queryKey: ["research-jobs", workspace.id, companyId] });
      await cache.invalidateQueries({ queryKey: ["research-report"] });
    }
  }
  function citations(explanation: Explanation) {
    return explanation.claim_indices.map((index) => {
      const id = intelligence?.claim_ids[index];
      return (
        <a key={index} href={`#claim-${id}`} className="ml-2 text-primary underline">
          Evidence {index + 1}
        </a>
      );
    });
  }
  return (
    <section className="mt-5 space-y-4 border-t pt-4" aria-labelledby="research-heading">
      <h3 id="research-heading" className="font-semibold">
        Account intelligence
      </h3>
      <p className="text-sm text-muted-foreground">
        Prepare a guided research plan using a published Company Brain. Execution requires separate
        approval and an available AI provider. Evidence-backed suggestions still require review.
      </p>
      <label className="block text-sm">
        Company Brain version
        <select
          className="mt-1 w-full rounded border bg-background p-2"
          value={version}
          onChange={(e) => setVersion(e.target.value)}
        >
          <option value="">Select a published version</option>
          {versions.data?.versions
            .filter((v) => v.status === "published")
            .map((v) => (
              <option key={v.id} value={v.id}>
                Version {v.number}
              </option>
            ))}
        </select>
      </label>
      <label className="block text-sm">
        Source URLs (up to three public HTTPS pages, one per line)
        <textarea
          className="mt-1 w-full rounded border bg-background p-2"
          rows={3}
          value={urls}
          onChange={(e) => setUrls(e.target.value)}
        />
      </label>
      <Button disabled={busy || !canEdit || !version || !urls.trim()} onClick={() => void run()}>
        {busy ? "Preparing plan…" : "Propose research plan"}
      </Button>
      {message && (
        <p role="status" className="text-sm">
          {message}{" "}
          <a href="/dashboard" className="text-primary underline">
            Open command center
          </a>
        </p>
      )}
      {(error || jobs.error || report.error || versions.error) && (
        <p role="alert" className="text-sm text-destructive">
          {error || friendlyError(jobs.error || report.error || versions.error)}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        {jobs.data?.map((job, index) => (
          <Button
            key={job.id}
            variant="outline"
            disabled={busy}
            onClick={() => setSelected(job.id)}
          >
            Research {jobs.data.length - index} · {job.status}
          </Button>
        ))}
      </div>
      {report.isFetching && selected && <p>Loading research…</p>}
      {report.data && (
        <p className="text-sm">
          Status: {report.data.status}
          {report.data.error_code ? " — no validated report was produced" : ""}
        </p>
      )}
      {intelligence && (
        <>
          <p className="text-sm font-medium">
            ICP assessment: {intelligence.fit.replaceAll("_", " ")} · model inference
          </p>
          <p className="whitespace-pre-wrap text-sm">ICP used: {intelligence.icp_used}</p>
          <article>
            <h4 className="font-medium">Why this company?</h4>
            <p className="text-sm">
              {intelligence.why_company.reasoning}
              {citations(intelligence.why_company)}
            </p>
          </article>
          <article>
            <h4 className="font-medium">Why now?</h4>
            <p className="text-sm">
              {intelligence.why_now.reasoning}
              {citations(intelligence.why_now)}
            </p>
          </article>
          <article>
            <h4 className="font-medium">Why this buyer?</h4>
            {intelligence.buyers.length === 0 && (
              <p className="text-sm">No supported buyer identified.</p>
            )}
            {intelligence.buyers.map((buyer, index) => (
              <div key={index} className="mt-2 rounded border p-3">
                <p className="font-medium">
                  {buyer.name} · {buyer.title}
                </p>
                <p className="text-sm">
                  {buyer.reasoning}
                  {citations(buyer)}
                </p>
                <p className="text-sm">{buyer.email || "Email unknown"}</p>
                <p className="text-xs text-muted-foreground">
                  Verification: {buyer.verification_status}. {buyer.verification_reason}
                </p>
              </div>
            ))}
          </article>
          <h4 className="font-medium">Supporting evidence</h4>
          {intelligence.claim_ids.map((id, index) => {
            const claim = report.data?.claims.find((c) => c.id === id);
            return claim ? (
              <article id={`claim-${id}`} key={id} className="space-y-2 rounded border p-3">
                <p className="text-xs font-medium">
                  Evidence {index + 1} · {claim.kind.replaceAll("_", " ")} · confidence{" "}
                  {Math.round(claim.confidence * 100)}%
                </p>
                <p className="text-sm">{claim.text}</p>
                {claim.excerpt && (
                  <blockquote className="max-h-48 overflow-auto border-l-2 pl-3 text-sm">
                    {claim.excerpt}
                  </blockquote>
                )}
                {claim.url && (
                  <a
                    className="break-all text-sm text-primary underline"
                    href={claim.url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {claim.title || claim.url}
                  </a>
                )}
                <p className="text-xs text-muted-foreground">
                  Publisher: {claim.publisher || "unknown"} · Published:{" "}
                  {claim.published_at || "unknown"} · Captured: {claim.retrieved_at || "unknown"} ·{" "}
                  {claim.freshness.replaceAll("_", " ")}
                </p>
              </article>
            ) : null;
          })}
        </>
      )}
    </section>
  );
}
