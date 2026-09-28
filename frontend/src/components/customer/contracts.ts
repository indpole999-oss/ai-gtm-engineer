export type Company = { id: string; name: string; domain?: string; description?: string };
export type Contact = {
  id: string;
  company_id: string;
  first_name: string;
  last_name: string;
  title?: string;
  email?: string;
};
export type Pipeline = {
  id: string;
  company_id: string;
  contact_id?: string;
  stage: string;
  revision: number;
  history?: {
    id: string;
    to_stage: string;
    from_stage: string;
    applied: boolean;
    source: string;
    reason: string;
    created_at: string;
    evidence: Record<string, string>;
  }[];
};
export type Integration = {
  id: string;
  provider: string;
  category: string;
  status: string;
  health: string;
  reconnect_required: boolean;
  scopes: string[];
  config: Record<string, string>;
};
export type Metric = {
  numerator: number;
  denominator: number;
  sample_size: number;
  rate: number | null;
  status: string;
  reason?: string;
  numerator_ids: string[];
  denominator_ids: string[];
};
export type Recommendation = {
  rule: string;
  status: string;
  observed_gap: string | null;
  supporting_metric: Metric;
  sample_size: number;
  confidence: string;
  limitations: string[];
  proposed_action: string | null;
  expected_outcome: string;
  risk: string;
  required_approval: boolean;
  cost: { status: string; value: number | null };
};
export type Insights = {
  date_range: { start: string; end_exclusive: string };
  funnel: {
    sample_size: number;
    cohort: string;
    current_stage_as_of_end: Record<string, number>;
    observed_stage_entries: Record<string, number>;
    conversions: Record<string, Metric>;
    ambiguous_current_stage_ids: string[];
  };
  metrics: {
    outreach: { sent: number; reply: Metric; positive_reply: Metric };
    contacted_to_confirmed_meeting: Metric;
    account_research_coverage: Metric;
    crm_confirmed_sync_coverage: Metric;
  };
  breakdowns: Record<
    string,
    {
      status: string;
      groups: { value: string; sent: number; reply: Metric; positive_reply: Metric }[];
    }
  >;
  recommendations: Recommendation[];
  limitations: string[];
  report_hash: string;
  version: string;
  generated_at: string;
  cost_per_meeting: { status: string; value: number | null };
  revenue: { status: string; value: number | null };
  evidence_manifest: {
    id: string;
    kind: string;
    occurred_at: string;
    source: { table: string; id: string };
  }[];
};
export const STAGES = [
  "discovered",
  "qualified",
  "contacted",
  "engaged",
  "interested",
  "meeting",
  "opportunity",
  "won",
  "lost",
];
export function sendLabel(message: {
  state: string;
  provider_message_id?: string | null;
  accepted_at?: string | null;
}) {
  return message.state === "sent"
    ? message.provider_message_id && message.accepted_at
      ? "Provider-confirmed sent"
      : "Confirmation unavailable"
    : message.state.replaceAll("_", " ");
}
export function canApproveRole(role: string) {
  return role === "owner" || role === "admin";
}
export function percent(metric: Metric) {
  return metric.rate === null ? "Not enough data" : `${(metric.rate * 100).toFixed(1)}%`;
}
