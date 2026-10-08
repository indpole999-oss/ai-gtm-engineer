export type DraftSnapshot = {
  id: string;
  scheduled_id: string;
  content_hash: string;
  envelope: {
    recipient: string; sender: string; subject: string; body: string;
    contact_id: string; research_job_id: string; evidence_id: string;
    brain_version_id: string; sequence_version_id: string; due_at: string;
    composition_method?: string;
  };
};
export type ReviewState = {
  status: string; revision: number; current_draft_id: string;
  warnings: string[];
  evidence: { excerpt: string; claim: string; source_url: string; source_hash: string; brain_claim: string };
  history: { id: string; draft_id: string; revision: number; action: string; actor_id: string; created_at: string; reason: string; content_hash: string }[];
};
export type ReviewAction = "revisions" | "submit" | "approve" | "rejected" | "changes_requested";

export function reviewPermissions(role: string, state: string, current: boolean, dirty: boolean) {
  const editor = ["owner", "admin", "member"].includes(role);
  const reviewer = ["owner", "admin"].includes(role);
  return {
    edit: current && editor && ["draft", "rejected", "changes_requested"].includes(state),
    submit: current && editor && state === "draft" && !dirty,
    decide: current && reviewer && state === "submitted" && !dirty,
  };
}

// The allowlist deliberately contains no delivery/plan-execution operation.
export function createReviewClient(request: (path: string, init: RequestInit) => Promise<unknown>) {
  let pending = false;
  return {
    async run(draft: DraftSnapshot, revision: number, action: ReviewAction,
      values: { subject?: string; body?: string; reason?: string; acknowledge?: boolean } = {}) {
      if (pending) throw new Error("A review action is already in progress");
      if (!["revisions", "submit", "approve", "rejected", "changes_requested"].includes(action))
        throw new Error("Unsupported review action");
      const payload: Record<string, unknown> = { content_hash: draft.content_hash, expected_revision: revision };
      let endpoint: string = action;
      if (action === "revisions") {
        if (!values.subject?.trim() || !values.body?.trim()) throw new Error("Subject and body are required");
        payload.subject = values.subject; payload.body = values.body;
      } else if (action === "rejected" || action === "changes_requested") {
        if (!values.reason?.trim()) throw new Error("A review reason is required");
        endpoint = "decision"; payload.action = action; payload.reason = values.reason.trim();
      } else if (action === "approve") {
        payload.reviewed = true; payload.acknowledge_unverified_edits = values.acknowledge === true;
      }
      pending = true;
      try {
        return await request("/api/v1/outreach/drafts/" + encodeURIComponent(draft.id) + "/" + endpoint,
          { method: "POST", body: JSON.stringify(payload) });
      } finally { pending = false; }
    },
  };
}
