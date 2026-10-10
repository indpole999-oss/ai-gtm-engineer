import { useState } from "react";
import { apiFetch } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace";
import { Panel, Feedback, friendlyError, Status } from "./ui";
export type ReviewedPlan = {
  id: string;
  content_hash: string;
  status: string;
  number: number;
  document: {
    brain_version_id: string;
    targets: { company_id: string; source_urls: string[] }[];
    plan: {
      objective: string;
      target_segment: string;
      success_metrics: string[];
      constraints: string[];
      assumptions: string[];
      risks: string[];
      stop_conditions: string[];
      review_checkpoint: string;
      steps: { action: string; rationale: string; expected_output: string }[];
    };
  };
};
export function PlanReview({ plan, onApproved }: { plan: ReviewedPlan; onApproved: () => void }) {
  const { canApprove } = useWorkspace();
  const [reviewed, setReviewed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [done, setDone] = useState(plan.status === "approved");
  const doc = plan.document.plan;
  async function approve() {
    if (!reviewed || !canApprove || done) return;
    setBusy(true);
    try {
      await apiFetch(`/api/v1/gtm/plans/${plan.id}/approve`, {
        method: "POST",
        body: JSON.stringify({ content_hash: plan.content_hash, reviewed: true }),
      });
      setDone(true);
      setMessage("Plan approved. Execution is queued; provider confirmation is still required.");
      onApproved();
    } catch (e) {
      setMessage(friendlyError(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Panel title={`Review execution plan · Version ${plan.number}`}>
      <Status value={done ? "approved" : plan.status} />
      <p className="mt-4 font-medium">{doc.objective}</p>
      <p className="mt-3 text-sm">Target: {doc.target_segment}</p>
      <ol className="my-5 space-y-3">
        {doc.steps.map((s, i) => (
          <li key={i} className="rounded-xl bg-muted p-4">
            <p className="font-medium">
              {i + 1}. {s.action.replaceAll("_", " ")}
            </p>
            <p className="mt-2 text-sm">{s.rationale}</p>
            <p className="mt-2 text-sm text-muted-foreground">Expected: {s.expected_output}</p>
          </li>
        ))}
      </ol>
      {(["success_metrics", "constraints", "assumptions", "risks", "stop_conditions"] as const).map(
        (k) => (
          <div key={k} className="my-3 text-sm">
            <h3 className="font-semibold capitalize">{k.replaceAll("_", " ")}</h3>
            <ul className="list-inside list-disc">
              {doc[k].map((v, i) => (
                <li key={i}>{v}</li>
              ))}
            </ul>
          </div>
        ),
      )}
      <p className="my-3 text-sm">{doc.review_checkpoint}</p>
      <details className="my-4 text-sm">
        <summary>Version and target evidence</summary>
        <p className="mt-2 break-all">Brain version {plan.document.brain_version_id}</p>
        {plan.document.targets.map((t) => (
          <p key={t.company_id} className="mt-2 break-all">
            Account {t.company_id} · {t.source_urls.join(", ")}
          </p>
        ))}
      </details>
      <Feedback message={message} />
      {!done && canApprove && (
        <div className="mt-5 space-y-4">
          <label className="flex items-start gap-3 text-sm">
            <input
              type="checkbox"
              checked={reviewed}
              onChange={(e) => setReviewed(e.target.checked)}
            />
            I reviewed the exact saved content, target, plan and risks above.
          </label>
          <button className="g-button" disabled={!reviewed || busy} onClick={() => void approve()}>
            Approve execution plan
          </button>
        </div>
      )}
      {!canApprove && <p className="text-sm">An owner or admin must approve this plan.</p>}
    </Panel>
  );
}
