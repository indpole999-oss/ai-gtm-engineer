import { useState } from "react";
import { Check, Copy, Pencil, Send, X } from "lucide-react";
import { toast } from "sonner";

import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { timingLabel, type SequenceStep } from "@/lib/sequence";

export interface StepDraft {
  subject: string;
  body: string;
}

export function SequenceTimeline({
  steps,
  drafts,
  onDraftChange,
  onSend,
  sendingIndex,
  canSend,
}: {
  steps: SequenceStep[];
  drafts: Record<number, StepDraft>;
  onDraftChange: (index: number, draft: StepDraft) => void;
  onSend: (step: SequenceStep, draft: StepDraft) => void;
  sendingIndex: number | null;
  canSend: boolean;
}) {
  return (
    <ol className="relative space-y-4 pl-8">
      <span
        className="absolute left-3 top-3 bottom-3 w-px bg-border"
        aria-hidden
      />
      {steps.map((step) => (
        <StepCard
          key={step.index}
          step={step}
          draft={drafts[step.index] ?? { subject: step.subject ?? "", body: step.body ?? "" }}
          onDraftChange={(draft) => onDraftChange(step.index, draft)}
          onSend={onSend}
          sending={sendingIndex === step.index}
          canSend={canSend}
        />
      ))}
    </ol>
  );
}

function StepCard({
  step,
  draft,
  onDraftChange,
  onSend,
  sending,
  canSend,
}: {
  step: SequenceStep;
  draft: StepDraft;
  onDraftChange: (draft: StepDraft) => void;
  onSend: (step: SequenceStep, draft: StepDraft) => void;
  sending: boolean;
  canSend: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [local, setLocal] = useState(draft);

  const timing = timingLabel(step);
  const edited = draft.subject !== (step.subject ?? "") || draft.body !== (step.body ?? "");

  const copy = async () => {
    const text = [draft.subject ? `Subject: ${draft.subject}` : null, draft.body]
      .filter(Boolean)
      .join("\n\n");
    if (!text) {
      toast.warning("Nothing to copy — the backend returned no subject or body for this step.");
      return;
    }
    try {
      await navigator.clipboard.writeText(text);
      toast.success(`Step ${step.stepNumber} copied`);
    } catch {
      toast.error("Clipboard is unavailable in this browser context.");
    }
  };

  return (
    <li className="relative">
      <span
        className="absolute -left-8 top-4 flex size-6 items-center justify-center rounded-full border bg-card font-mono text-[11px] font-medium"
        aria-hidden
      >
        {step.stepNumber}
      </span>

      <article className="rounded-lg border bg-card p-5 shadow-xs">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="font-mono text-xs uppercase tracking-wide text-muted-foreground">
              Step {step.stepNumber}
              {step.delayDays !== undefined ? ` · Day ${step.delayDays}` : ""}
            </p>
            {timing ? <p className="mt-1 text-xs text-muted-foreground">{timing}</p> : null}
          </div>
          <div className="flex items-center gap-2">
            {edited ? (
              <span className="rounded-full border border-info/30 bg-info/10 px-2 py-0.5 text-xs text-info">
                Edited locally
              </span>
            ) : null}
            {step.status ? <StatusBadge value={step.status} /> : <StatusBadge state={step.state} />}
          </div>
        </div>

        {editing ? (
          <div className="mt-4 space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor={`subject-${step.index}`}>Subject</Label>
              <Input
                id={`subject-${step.index}`}
                value={local.subject}
                onChange={(e) => setLocal({ ...local, subject: e.target.value })}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor={`body-${step.index}`}>Body</Label>
              <Textarea
                id={`body-${step.index}`}
                rows={8}
                value={local.body}
                onChange={(e) => setLocal({ ...local, body: e.target.value })}
              />
            </div>
            <p className="text-xs text-muted-foreground">
              Edits stay in this browser session — the backend has no endpoint to store sequence drafts.
            </p>
            <div className="flex gap-2">
              <Button
                size="sm"
                onClick={() => {
                  onDraftChange(local);
                  setEditing(false);
                }}
              >
                <Check className="size-4" aria-hidden />
                Save locally
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  setLocal(draft);
                  setEditing(false);
                }}
              >
                <X className="size-4" aria-hidden />
                Cancel
              </Button>
            </div>
          </div>
        ) : (
          <div className="mt-4 space-y-3">
            {draft.subject ? (
              <p className="text-sm font-medium">
                <span className="text-muted-foreground">Subject: </span>
                {draft.subject}
              </p>
            ) : (
              <p className="text-sm text-muted-foreground">No subject returned for this step.</p>
            )}
            {draft.body ? (
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">{draft.body}</p>
            ) : (
              <p className="text-sm text-muted-foreground">No body returned for this step.</p>
            )}
          </div>
        )}

        <div className="mt-4 flex flex-wrap gap-2">
          <Button size="sm" variant="outline" onClick={copy}>
            <Copy className="size-4" aria-hidden />
            Copy email
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              setLocal(draft);
              setEditing((v) => !v);
            }}
          >
            <Pencil className="size-4" aria-hidden />
            {editing ? "Close editor" : "Edit email"}
          </Button>
          <Button
            size="sm"
            disabled={!canSend || sending || !draft.subject.trim() || !draft.body.trim()}
            onClick={() => onSend(step, draft)}
          >
            <Send className="size-4" aria-hidden />
            {sending ? "Sending…" : "Send this email"}
          </Button>
        </div>
        {!canSend ? (
          <p className="mt-2 text-xs text-muted-foreground">
            Add a contact ID above to enable sending — nothing is ever sent automatically.
          </p>
        ) : null}

        <details className="mt-3">
          <summary className="cursor-pointer text-xs text-muted-foreground">View raw step</summary>
          <pre className="mt-2 max-h-56 overflow-auto rounded-md bg-muted p-3 font-mono text-xs">
            {JSON.stringify(step.raw, null, 2)}
          </pre>
        </details>
      </article>
    </li>
  );
}
