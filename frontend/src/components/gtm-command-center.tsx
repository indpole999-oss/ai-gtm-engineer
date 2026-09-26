import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";

type Step = { action: "research" | "outreach_send" | "crm_sync" | "calendar_schedule"; outcome_id?: string | null; outcome_hash?: string | null; message_id?: string | null; target_index: number; dependencies: number[]; rationale: string; expected_output: string; side_effect: "read_only" | "outbound" | "external_write"; approval_required: true };
type Document = { objective: string; success_metrics: string[]; target_segment: string; constraints: string[]; assumptions: string[]; risks: string[]; steps: Step[]; cost_estimate_cents: number; stop_conditions: string[]; review_checkpoint: string; max_attempts: number; timeout_seconds: number };
type Plan = { id: string; goal_id: string; status: string; number: number; content_hash: string; author_method: string; document: { plan: Document; brain_version_id: string; targets: { company_id: string; source_urls: string[] }[] } };
type Cycle = { id: string; status: string; stop_reason: string | null };
type CycleDetail = Cycle & { steps: { position: number; status: string; output: { research_job_id?: string; message_id?: string; provider_message_id?: string; provider_object_id?: string } | null }[]; commands: { id: string; status: string; attempts: number; error_code: string | null }[]; events: { kind: string; at: string }[] };

export function GtmCommandCenter() {
  const cache = useQueryClient();
  const [objective, setObjective] = useState("");
  const [brain, setBrain] = useState("");
  const [company, setCompany] = useState("");
  const [urls, setUrls] = useState("");
  const [plan, setPlan] = useState<Plan | null>(null);
  const [selectedCycle, setSelectedCycle] = useState("");
  const [dirty, setDirty] = useState(false);
  const [reviewed, setReviewed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const goals = useQuery({ queryKey: ["gtm-goals"], queryFn: () => apiFetch<{ id: string; objective: string }[]>("/api/v1/gtm/goals") });
  const brains = useQuery({ queryKey: ["company-brain"], queryFn: () => apiFetch<{ versions: { id: string; number: number; status: string }[] }>("/api/v1/company-brain") });
  const companies = useQuery({ queryKey: ["planning-companies"], queryFn: () => apiFetch<{ id: string; name: string }[]>("/api/v1/companies/") });
  const cycles = useQuery({ queryKey: ["gtm-cycles"], queryFn: () => apiFetch<Cycle[]>("/api/v1/gtm/cycles"), refetchInterval: 5000 });
  const cycle = useQuery({ queryKey: ["gtm-cycle", selectedCycle], queryFn: () => apiFetch<CycleDetail>(`/api/v1/gtm/cycles/${selectedCycle}`), enabled: Boolean(selectedCycle), refetchInterval: 3000 });
  const outcomeId = plan?.document.plan.steps.find(s => s.outcome_id)?.outcome_id;
  const outcome = useQuery({ queryKey: ["outcome-review", outcomeId], queryFn: () => apiFetch<{ id: string; content_hash: string; payload: Record<string, unknown> }>(`/api/v1/outcomes/actions/${outcomeId}`), enabled: Boolean(outcomeId) });
  const outcomeReady = !outcomeId || Boolean(outcome.data && outcome.data.id === outcomeId && outcome.data.content_hash === plan?.document.plan.steps.find(s => s.outcome_id)?.outcome_hash);
  const style = "mt-1 w-full rounded border bg-background p-2 text-sm";
  async function run(work: () => Promise<void>) { setBusy(true); setMessage(""); try { await work(); } catch (e) { setMessage(e instanceof Error ? e.message : "Operation failed"); } finally { setBusy(false); } }
  function selectPlan(next: Plan) { setPlan(next); setDirty(false); setReviewed(false); }
  function edit(document: Document) { if (plan) { setPlan({ ...plan, document: { ...plan.document, plan: document } }); setDirty(true); setReviewed(false); } }
  async function generate(mode: "local_ai" | "research_template") {
    const goal = await apiFetch<{ id: string }>("/api/v1/gtm/goals", { method: "POST", body: JSON.stringify({ objective, brain_version_id: brain, targets: [{ company_id: company, source_urls: urls.split("\n").map(s => s.trim()).filter(Boolean) }] }) });
    selectPlan(await apiFetch<Plan>(`/api/v1/gtm/goals/${goal.id}/plans`, { method: "POST", body: JSON.stringify({ mode }) }));
    await cache.invalidateQueries({ queryKey: ["gtm-goals"] });
  }
  async function approve() {
    if (!plan || dirty || !reviewed || !outcomeReady) return;
    const result = await apiFetch<Cycle>(`/api/v1/gtm/plans/${plan.id}/approve`, { method: "POST", body: JSON.stringify({ content_hash: plan.content_hash, reviewed: true }) });
    selectPlan({ ...plan, status: "approved" }); setSelectedCycle(result.id);
    await cache.invalidateQueries({ queryKey: ["gtm-cycles"] });
    setMessage(outcomeId ? "Reviewed CRM or calendar action queued. Live provider writes remain disabled." : plan.document.plan.steps.some(s => s.action === "outreach_send") ? "Reviewed outreach queued for the background worker. Live providers remain disabled." : "Research plan approved and queued for the background worker.");
  }
  return <section className="space-y-4 rounded-lg border p-5" aria-labelledby="gtm-center">
    <h2 id="gtm-center" className="text-xl font-semibold">AI GTM command center</h2>
    <p className="text-sm text-muted-foreground">Give your GTM employee a goal, review its plan, then approve execution. Research plans and separately reviewed outreach run through the background worker. Live outreach providers remain disabled.</p>
    <fieldset disabled={busy} className="grid gap-3 md:grid-cols-2">
      <label className="text-sm md:col-span-2">Business goal<textarea className={style} value={objective} maxLength={4000} placeholder="Identify accounts that match our ICP and explain the strongest evidence" onChange={e => setObjective(e.target.value)} /></label>
      <label className="text-sm">Published Company Brain<select className={style} value={brain} onChange={e => setBrain(e.target.value)}><option value="">Select version</option>{brains.data?.versions.filter(v => v.status === "published").map(v => <option key={v.id} value={v.id}>Version {v.number}</option>)}</select></label>
      <label className="text-sm">Target account<select className={style} value={company} onChange={e => setCompany(e.target.value)}><option value="">Select account</option>{companies.data?.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
      <label className="text-sm md:col-span-2">Public source URLs (one to three, one per line)<textarea className={style} value={urls} onChange={e => setUrls(e.target.value)} /></label>
    </fieldset>
    <div className="flex flex-wrap gap-2"><Button disabled={busy || objective.trim().length < 10 || !brain || !company || !urls.trim()} onClick={() => void run(() => generate("local_ai"))}>Generate plan with local AI</Button><Button variant="outline" disabled={busy || objective.trim().length < 10 || !brain || !company || !urls.trim()} onClick={() => void run(() => generate("research_template"))}>Use research template (no AI planning)</Button></div>
    {(message || goals.error || brains.error || companies.error || cycles.error || cycle.error) && <p role="status" className="text-sm">{message || goals.error?.message || brains.error?.message || companies.error?.message || cycles.error?.message || cycle.error?.message}</p>}
    <div className="flex flex-wrap gap-2">{goals.data?.map(g => <Button key={g.id} variant="outline" disabled={busy || dirty} onClick={() => void run(async () => { const list = await apiFetch<Plan[]>(`/api/v1/gtm/goals/${g.id}/plans`); if (list[0]) selectPlan(list[0]); else setMessage("This goal has no saved plan yet. Generate a plan to continue."); })}>{g.objective.slice(0,70)}</Button>)}</div>
    {plan && <article className="space-y-3 rounded border p-4">
      <h3 className="font-semibold">Plan version {plan.number} · {plan.status}{dirty ? " · unsaved revision" : ""}</h3>
      <p className="text-xs text-muted-foreground">Created by {plan.author_method.startsWith("ollama:") ? "local AI" : plan.author_method === "explicit_research_template" ? "research template" : ["reviewed_outreach", "reviewed_outcome"].includes(plan.author_method) ? "reviewed external action" : "customer revision"}. Paid API budget: $0.</p>
      <label className="block text-sm">Objective<textarea className={style} disabled={busy || plan.status === "approved" || ["reviewed_outreach", "reviewed_outcome"].includes(plan.author_method)} value={plan.document.plan.objective} onChange={e => edit({ ...plan.document.plan, objective: e.target.value })} /></label>
      <p className="text-sm">Target segment: {plan.document.plan.target_segment}</p>
      {([['Success metrics',plan.document.plan.success_metrics],['Constraints',plan.document.plan.constraints],['Assumptions',plan.document.plan.assumptions],['Risks',plan.document.plan.risks],['Stop conditions',plan.document.plan.stop_conditions]] as [string,string[]][]).map(([title,values]) => <div key={title}><h4 className="text-sm font-medium">{title}</h4><ul className="list-inside list-disc text-sm">{values.map((v,i) => <li key={i}>{v}</li>)}</ul></div>)}
      <ol className="space-y-3">{plan.document.plan.steps.map((s,index) => <li key={index} className="rounded border p-3"><p className="font-medium">{index + 1}. {s.action === "outreach_send" ? "Send approved outreach to" : s.action === "crm_sync" ? "Sync CRM for" : s.action === "calendar_schedule" ? "Schedule a reviewed meeting for" : "Research"} {companies.data?.find(c => c.id === plan.document.targets[s.target_index]?.company_id)?.name || "target account"}</p><p className="text-sm">{s.rationale}</p><p className="text-sm">Expected: {s.expected_output}</p><p className="text-xs">{s.side_effect === "outbound" ? "Outbound: separate message approval required" : s.side_effect === "external_write" ? "External write: exact payload and plan approval required" : "Read-only"} · dependencies: {s.dependencies.length ? s.dependencies.map(d => d + 1).join(", ") : "none"}</p></li>)}</ol>
      <div className="text-sm"><h4 className="font-medium">Approved research sources</h4>{plan.document.targets.map(target => <ul key={target.company_id} className="list-inside list-disc">{target.source_urls.map(url => <li key={url} className="break-all">{url}</li>)}</ul>)}</div>
      {outcomeId && <div className="rounded border p-3"><h4 className="font-medium">External action to review</h4>{outcomeReady ? <pre className="whitespace-pre-wrap break-words text-xs">{JSON.stringify(Object.fromEntries(Object.entries(outcome.data?.payload || {}).filter(([key]) => !["input_hash", "integration_binding"].includes(key))), null, 2)}</pre> : <p>Load the exact saved action before approving. {outcome.isError ? "Action could not be loaded." : "Loading…"}</p>}</div>}
      <p className="text-sm">Execution limits: {plan.document.plan.max_attempts} attempts per step, {plan.document.plan.timeout_seconds} seconds per attempt.</p>
      <p className="text-sm">Review checkpoint: {plan.document.plan.review_checkpoint}</p>
      {plan.status === "draft" && <><Button disabled={!dirty || busy || ["reviewed_outreach", "reviewed_outcome"].includes(plan.author_method)} variant="outline" onClick={() => void run(async () => selectPlan(await apiFetch<Plan>(`/api/v1/gtm/plans/${plan.id}/revisions`, { method: "POST", body: JSON.stringify(plan.document.plan) })))}>Save revised plan</Button><label className="flex items-center gap-2 text-sm"><input type="checkbox" disabled={dirty || busy} checked={reviewed} onChange={e => setReviewed(e.target.checked)} />I reviewed this saved plan, targets, constraints and risks.</label><Button disabled={!reviewed || dirty || busy || !outcomeReady} onClick={() => void run(approve)}>Approve and queue plan</Button></>}
      <Button variant="outline" disabled={busy || dirty || ["reviewed_outreach", "reviewed_outcome"].includes(plan.author_method)} onClick={() => void run(async () => selectPlan(await apiFetch<Plan>(`/api/v1/gtm/goals/${plan.goal_id}/plans`, { method: "POST", body: JSON.stringify({ mode: "local_ai" }) })))}>Generate a new plan version with local AI</Button>
    </article>}
    <div className="flex flex-wrap gap-2">{cycles.data?.map((c,i) => <Button key={c.id} variant="outline" onClick={() => setSelectedCycle(c.id)}>Execution {cycles.data.length - i} · {c.status}</Button>)}</div>
    {cycle.data && <article className="space-y-3 rounded border p-4"><h3 className="font-semibold">Execution: {cycle.data.status}</h3>{cycle.data.stop_reason && <p>{cycle.data.stop_reason.replaceAll("_"," ")}</p>}<ol className="list-inside list-decimal text-sm">{cycle.data.steps.map(s => <li key={s.position}>{s.status}{s.output?.provider_message_id ? "Provider accepted the message" : s.output?.provider_object_id ? " — provider confirmed CRM/calendar outcome" : s.output?.research_job_id ? " — account intelligence is available in the company details" : ""}</li>)}</ol><p className="text-xs">Attempts: {cycle.data.commands.map(c => c.attempts).join(", ")}</p>{["running","paused"].includes(cycle.data.status) && <div className="flex gap-2">{(["pause","resume","cancel"] as const).map(action => <Button key={action} disabled={busy} variant="outline" onClick={() => void run(async () => { await apiFetch(`/api/v1/gtm/cycles/${selectedCycle}/control`, { method: "POST", body: JSON.stringify({ action }) }); await cache.invalidateQueries({ queryKey: ["gtm-cycle", selectedCycle] }); await cache.invalidateQueries({ queryKey: ["gtm-cycles"] }); })}>{action}</Button>)}</div>}<details><summary className="cursor-pointer text-sm">Activity</summary><ul className="text-xs">{cycle.data.events.map((event,i) => <li key={i}>{event.kind.replaceAll("_"," ")} · {event.at}</li>)}</ul></details></article>}
  </section>;
}
