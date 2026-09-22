import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";

const base = "/api/v1/company-brain";
const fields = [
  ["company", "Company", "What is your company called?"],
  ["product_service", "Product or service", "What do you sell, and how does it work?"],
  ["value_proposition", "Value proposition", "What measurable problem do you solve?"],
  ["icp", "Ideal customer", "Which organizations are the best fit? Include size and exclusions."],
  ["industries", "Industries", "Which sectors do you serve?"],
  ["geographies", "Geographies", "Where do you operate and sell?"],
  ["buyer_personas", "Buyer personas", "Who buys, influences and uses your product?"],
  ["pain_points", "Pain points", "What makes customers look for a solution?"],
  ["competitors", "Competitors", "What alternatives do customers consider?"],
  ["gtm_objectives", "GTM objectives", "What outcomes should your AI GTM employee pursue?"],
  ["positioning", "Positioning", "Why choose you over alternatives?"],
  ["tone_guidance", "Tone and brand", "How should we sound? Include words and styles to avoid."],
] as const;
type Source = { key: string; kind: string; title: string; url: string | null; content: string };
type Claim = { text: string; disposition: "approved" | "prohibited"; source_key: string | null };
type Version = { id: string; number: number; status: string; revision: number; profile: Record<string, string>; sources: Source[]; claims: Claim[]; content_hash: string | null };
type Summary = Pick<Version, "id" | "number" | "status">;

export function CompanyBrainEditor() {
  const cache = useQueryClient();
  const versions = useQuery({ queryKey: ["company-brain"], queryFn: () => apiFetch<{ versions: Summary[] }>(base) });
  const [draft, setDraft] = useState<Version | null>(null);
  const [step, setStep] = useState(0);
  const [dirty, setDirty] = useState(false);
  const [reviewed, setReviewed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [source, setSource] = useState<Source>({ key: "", kind: "manual_edit", title: "", url: null, content: "" });
  const [claim, setClaim] = useState<Claim>({ text: "", disposition: "approved", source_key: null });
  const readOnly = draft?.status === "published";

  async function run(work: () => Promise<void>) {
    setBusy(true); setMessage("");
    try { await work(); } catch (error) { setMessage(error instanceof Error ? error.message : "Could not update Company Brain"); }
    finally { setBusy(false); }
  }
  function edit(next: Version) { setDraft(next); setDirty(true); setReviewed(false); }
  async function load(id?: string) {
    const next = await apiFetch<Version>(id ? `${base}/versions/${id}` : `${base}/drafts`, { method: id ? "GET" : "POST" });
    setDraft(next); setDirty(false); setReviewed(false); setStep(0);
    await cache.invalidateQueries({ queryKey: ["company-brain"] });
  }
  async function save() {
    if (!draft) return;
    const next = await apiFetch<Version>(`${base}/versions/${draft.id}`, { method: "PUT", body: JSON.stringify({ revision: draft.revision, profile: draft.profile, sources: draft.sources, claims: draft.claims }) });
    setDraft(next); setDirty(false); setReviewed(false); setMessage("Draft saved. Review it before publishing.");
  }
  async function publish() {
    if (!draft || dirty || !reviewed) return;
    const next = await apiFetch<Version>(`${base}/versions/${draft.id}/publish`, { method: "POST", body: JSON.stringify({ revision: draft.revision, reviewed: true }) });
    setDraft(next); setMessage(`Version ${next.number} published. Future edits create a new version.`);
    await cache.invalidateQueries({ queryKey: ["company-brain"] });
  }
  const inputClass = "w-full rounded-md border bg-background p-2 text-sm";
  return <section className="space-y-4 rounded-lg border p-5" aria-labelledby="brain-heading">
    <div><h2 id="brain-heading" className="text-lg font-semibold">Company Brain</h2><p className="text-sm text-muted-foreground">Teach your AI GTM employee about your company. Review sources and claims, then publish a fixed version for future plans.</p></div>
    {versions.isPending && <p>Loading versions…</p>}
    {versions.error && <p role="alert">{versions.error.message}</p>}
    <div className="flex flex-wrap gap-2">
      <Button disabled={busy || dirty} onClick={() => void run(() => load())}>Open working draft</Button>
      {versions.data?.versions.map(v => <Button key={v.id} variant="outline" disabled={busy || dirty} onClick={() => void run(() => load(v.id))}>Version {v.number} · {v.status}</Button>)}
    </div>
    {message && <p role="status" className="text-sm">{message}</p>}
    {draft && <div className="space-y-4">
      <p className="text-sm">Version {draft.number} · {draft.status}{dirty ? " · unsaved changes" : ""}</p>
      <div className="flex flex-wrap gap-2">{["Company and market", "Sources", "Claims", "Review and publish"].map((label, index) => <Button key={label} variant={step === index ? "default" : "outline"} onClick={() => setStep(index)}>{index + 1}. {label}</Button>)}</div>
      <fieldset disabled={busy || readOnly} className="space-y-3">
        {step === 0 && fields.map(([key, label, prompt]) => <label key={key} className="block space-y-1"><span className="text-sm font-medium">{label}</span><textarea className={inputClass} maxLength={4000} value={draft.profile[key] ?? ""} placeholder={prompt} onChange={e => edit({ ...draft, profile: { ...draft.profile, [key]: e.target.value } })} /></label>)}
        {step === 1 && <>
          <p className="text-sm text-muted-foreground">Paste source excerpts with their original URL, or upload a document. Content stays a customer-provided source until reviewed; adding a URL does not fetch or verify it.</p>
          <label className="block">Upload TXT, Markdown, DOCX or text PDF (2 MB maximum)<input type="file" accept=".txt,.md,.docx,.pdf" onChange={e => { const file = e.target.files?.[0]; if (!file) return; void run(async () => { if (file.size > 2000000) throw new Error("Document must be at most 2 MB"); const body = new FormData(); body.append("file", file); const preview = await apiFetch<{ title: string; content: string }>(`${base}/documents/preview`, { method: "POST", body }); setSource({ key: crypto.randomUUID(), kind: "uploaded_document", url: null, ...preview }); }); }} /></label>
          <label className="block">Source type<select className={inputClass} value={source.kind} onChange={e => setSource({ ...source, kind: e.target.value })}>{["guided_answers", "website", "product_page", "case_study", "uploaded_document", "manual_edit", "crm_metadata"].map(kind => <option key={kind} value={kind}>{kind.replaceAll("_", " ")}</option>)}</select></label>
          <label className="block">Title<input className={inputClass} maxLength={300} value={source.title} onChange={e => setSource({ ...source, title: e.target.value })} /></label>
          <label className="block">Original URL (optional)<input className={inputClass} type="url" value={source.url ?? ""} onChange={e => setSource({ ...source, url: e.target.value || null })} /></label>
          <label className="block">Source text<textarea className={inputClass} rows={5} maxLength={100000} value={source.content} onChange={e => setSource({ ...source, content: e.target.value })} /></label>
          <Button disabled={!source.title.trim() || !source.content.trim() || draft.sources.length >= 30} onClick={() => { edit({ ...draft, sources: [...draft.sources, { ...source, key: source.key || crypto.randomUUID() }] }); setSource({ key: "", kind: "manual_edit", title: "", url: null, content: "" }); }}>Add source to draft</Button>
        </>}
        {step === 2 && <>
          <p className="text-sm text-muted-foreground">Approved claims may be used in outreach after publication. Prohibited claims must never be used. Customer approval is not independent verification.</p>
          <label className="block">Claim<textarea className={inputClass} maxLength={4000} value={claim.text} onChange={e => setClaim({ ...claim, text: e.target.value })} /></label>
          <label className="block">Policy<select className={inputClass} value={claim.disposition} onChange={e => setClaim({ ...claim, disposition: e.target.value as Claim["disposition"] })}><option value="approved">Approved</option><option value="prohibited">Prohibited</option></select></label>
          <label className="block">Supporting source<select className={inputClass} value={claim.source_key ?? ""} onChange={e => setClaim({ ...claim, source_key: e.target.value || null })}><option value="">Customer-approved manual claim</option>{draft.sources.map(s => <option key={s.key} value={s.key}>{s.title}</option>)}</select></label>
          <Button disabled={!claim.text.trim() || draft.claims.length >= 100} onClick={() => { edit({ ...draft, claims: [...draft.claims, claim] }); setClaim({ text: "", disposition: "approved", source_key: null }); }}>Add claim to draft</Button>
        </>}
      </fieldset>
      {(step === 1 || step === 3) && draft.sources.map(s => <article key={s.key} className="rounded border p-3"><h3 className="font-medium">{s.title}</h3><p className="break-all text-xs">{s.url}</p><p className="max-h-48 overflow-auto whitespace-pre-wrap text-sm">{s.content}</p>{!readOnly && step === 1 && <Button variant="outline" disabled={busy} onClick={() => edit({ ...draft, sources: draft.sources.filter(x => x.key !== s.key), claims: draft.claims.map(c => c.source_key === s.key ? { ...c, source_key: null } : c) })}>Remove source</Button>}</article>)}
      {(step === 2 || step === 3) && draft.claims.map((c, index) => <article key={index} className="rounded border p-3"><p className="text-xs font-semibold uppercase">{c.disposition}</p><p className="whitespace-pre-wrap text-sm">{c.text}</p><p className="text-xs">{draft.sources.find(s => s.key === c.source_key)?.title ?? "Customer manual claim"}</p>{!readOnly && step === 2 && <Button variant="outline" disabled={busy} onClick={() => edit({ ...draft, claims: draft.claims.filter((_, i) => i !== index) })}>Remove claim</Button>}</article>)}
      {step === 3 && <>
        <dl className="space-y-2">{fields.map(([key, label]) => <div key={key}><dt className="text-sm font-medium">{label}</dt><dd className="whitespace-pre-wrap text-sm text-muted-foreground">{draft.profile[key] || "Not provided"}</dd></div>)}</dl>
        {!readOnly && <><p className="text-sm">Owners and admins can publish. Save first, then confirm you have reviewed the exact content above. Published versions cannot be edited.</p><label className="flex items-center gap-2"><input type="checkbox" checked={reviewed} disabled={dirty || busy} onChange={e => setReviewed(e.target.checked)} />I have reviewed this saved version and its claims.</label><Button disabled={dirty || !reviewed || busy} onClick={() => void run(publish)}>Publish reviewed version</Button></>}
      </>}
      {!readOnly && <Button disabled={!dirty || busy} onClick={() => void run(save)}>{busy ? "Working…" : "Save draft"}</Button>}
    </div>}
  </section>;
}
