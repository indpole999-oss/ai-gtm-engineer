/**
 * Typed access to the AI GTM Engineer FastAPI backend.
 * Every call here maps 1:1 to an operation in the imported OpenAPI contract.
 * No endpoint, field or response is invented.
 */
import { apiFetch, extractItems } from "./api";
import {
  ACTION_ENDPOINTS,
  HEALTH_ENDPOINT,
  RESOURCE_ENDPOINTS,
} from "./api-config";

export type Json = Record<string, unknown>;

/* ---------------------------------- reads --------------------------------- */

export const listLeads = () => apiFetch<unknown>(RESOURCE_ENDPOINTS.leads);

export const listCompanies = () =>
  apiFetch<unknown>(RESOURCE_ENDPOINTS.companies);

export const getCompany = (id: string) =>
  apiFetch<Json>(`${RESOURCE_ENDPOINTS.companies}${id}`);

export const listContacts = () =>
  apiFetch<unknown>(RESOURCE_ENDPOINTS.contacts);

export const getContact = (id: string) =>
  apiFetch<Json>(`${RESOURCE_ENDPOINTS.contacts}${id}`);

export const listEmails = () =>
  apiFetch<unknown>(RESOURCE_ENDPOINTS.emails);

export const listCrm = () =>
  apiFetch<unknown>(RESOURCE_ENDPOINTS.crm);

export const listMeetings = () =>
  apiFetch<unknown>(RESOURCE_ENDPOINTS.calendar);

export const listAgents = () =>
  apiFetch<AgentsListResponse>(RESOURCE_ENDPOINTS.agents);

export const listWorkflows = () =>
  apiFetch<unknown>(RESOURCE_ENDPOINTS.workflows);

export const getWorkflow = (name: string) =>
  apiFetch<Json>(`${RESOURCE_ENDPOINTS.workflows}${name}`);

export const getHealth = () =>
  apiFetch<Json>(HEALTH_ENDPOINT);

export const getCalendarAuth = () =>
  apiFetch<Json>(ACTION_ENDPOINTS.calendarAuth);

export interface AgentsListResponse {
  agents?: Record<string, string>;
  total?: number;
}

/* --------------------------------- writes --------------------------------- */

export const createCompany = (body: {
  name: string;
  domain?: string | null;
  industry?: string | null;
  employee_count?: number | null;
  revenue?: string | null;
  location?: string | null;
  description?: string | null;
}) =>
  apiFetch<Json>(RESOURCE_ENDPOINTS.companies, {
    method: "POST",
    body: JSON.stringify(body),
  });

export const createContact = (body: {
  company_id: string;
  first_name: string;
  last_name: string;
  email: string;
  title?: string | null;
  linkedin_url?: string | null;
  phone?: string | null;
}) =>
  apiFetch<Json>(RESOURCE_ENDPOINTS.contacts, {
    method: "POST",
    body: JSON.stringify(body),
  });

export const enrichLead = (contactId: string) =>
  apiFetch<Json>(ACTION_ENDPOINTS.enrichLead(contactId), {
    method: "POST",
  });

export const sendEmail = (body: {
  contact_id: string;
  subject: string;
  body: string;
}) =>
  apiFetch<Json>(ACTION_ENDPOINTS.sendEmail, {
    method: "POST",
    body: JSON.stringify(body),
  });

export const createCrmRecord = (contactId: string) =>
  apiFetch<Json>(RESOURCE_ENDPOINTS.crm, {
    method: "POST",
    body: JSON.stringify({ contact_id: contactId }),
  });

export const createCrmCompany = (companyId: string) =>
  apiFetch<Json>(ACTION_ENDPOINTS.crmCompany, {
    method: "POST",
    body: JSON.stringify({ company_id: companyId }),
  });

export const createCrmActivity = (body: {
  record_id: string;
  note: string;
}) =>
  apiFetch<Json>(ACTION_ENDPOINTS.crmActivity, {
    method: "POST",
 body: JSON.stringify(body),
 });

export const createCrmDeal = (body: {
  deal_name: string;
  amount?: number | null;
  stage?: string;
  pipeline?: string;
  close_date?: string | null;
  company_id?: string | null;
}) =>
  apiFetch<Json>(ACTION_ENDPOINTS.crmDeal, {
    method: "POST",
    body: JSON.stringify(body),
  });

export const bookMeeting = (body: {
  contact_id: string;
  title?: string;
  duration_minutes?: number;
  preferred_date?: string | null;
  notes?: string | null;
}) =>
  apiFetch<Json>(ACTION_ENDPOINTS.bookMeeting, {
    method: "POST",
    body: JSON.stringify(body),
  });

export const runAgent = (body: {
  agent: string;
  task: string;
  context?: Json;
}) =>
  apiFetch<Json>(ACTION_ENDPOINTS.runAgent, {
    method: "POST",
    body: JSON.stringify(body),
  });

export const researchCompany = (companyName: string, domain?: string) => {
  const qs = new URLSearchParams({ company_name: companyName });

  if (domain) {
    qs.set("domain", domain);
  }

  return apiFetch<Json>(`${ACTION_ENDPOINTS.research}?${qs.toString()}`, {
    method: "POST",
  });
};

export const runWorkflow = (
  workflowName: string,
  context: Json = {},
) =>
  apiFetch<Json>(ACTION_ENDPOINTS.runWorkflow, {
    method: "POST",
    body: JSON.stringify({
      workflow_name: workflowName,
      context,
    }),
  });

/* ------------------------------ state semantics ---------------------------- */

export type BackendState =
  | "success"
  | "warning"
  | "skipped"
  | "error"
  | "not_configured"
  | "generated"
  | "pending"
  | "unknown";

const MATCHERS: [RegExp, BackendState][] = [
  [
    /not[_\s-]?configured|no[_\s-]?provider|missing[_\s-]?credential|not[_\s-]?connected|unconfigured|disabled/i,
    "not_configured",
  ],
  [/error|failed|failure|exception|invalid/i, "error"],
  [/skipped|not[_\s-]?sent|no[_\s-]?op|nothing[_\s-]?to/i, "skipped"],
  [/warning|partial|degraded/i, "warning"],
  [/generated|draft|created|updated|scheduled|queued/i, "generated"],
  [/pending|running|in[_\s-]?progress|processing/i, "pending"],
  [
    /success|completed|complete|ok|sent|booked|synced|done|active|healthy/i,
    "success",
  ],
];

export function normalizeState(value: unknown): BackendState {
  if (value === null || value === undefined) {
    return "unknown";
  }

  if (typeof value === "boolean") {
    return value ? "success" : "not_configured";
  }

  const s = String(value);

  for (const [re, state] of MATCHERS) {
    if (re.test(s)) {
      return state;
    }
  }

  return "unknown";
}

export const STATE_LABEL: Record<BackendState, string> = {
  success: "Success",
  warning: "Warning",
  skipped: "Skipped",
  error: "Error",
  not_configured: "Not configured",
  generated: "Generated",
  pending: "Pending",
  unknown: "Unknown",
};

export interface StageResult {
  key: string;
  label: string;
  state: BackendState;
  message?: string | undefined;
  raw: unknown;
}

const STAGE_LABELS: Record<string, string> = {
  research: "Research",
  enrichment: "Enrichment",
  email: "Email",
  crm: "CRM",
  calendar: "Calendar",
  meeting: "Meeting",
  meetings: "Meetings",
};

function stageMessage(value: Json): string | undefined {
  for (const key of [
    "error",
    "message",
    "detail",
    "reason",
    "note",
    "summary",
  ]) {
    const v = value[key];

    if (typeof v === "string" && v.trim()) {
      return v;
    }
  }

  return undefined;
}

function normalizeStage(
  key: string,
  value: unknown,
): StageResult | null {
  const normalizedKey = key.toLowerCase();
  const label = STAGE_LABELS[normalizedKey];

  if (!label) {
    return null;
  }

  let state: BackendState = "unknown";
  let message: string | undefined;

  if (value === null || value === undefined) {
    state = "skipped";
  } else if (
    typeof value === "object" &&
    !Array.isArray(value)
  ) {
    const obj = value as Json;

    message = stageMessage(obj);

    if (obj["error"]) {
      state = "error";
    } else if (obj["status"] !== undefined) {
      state = normalizeState(obj["status"]);
      if (state === "unknown" && obj["result"] && typeof obj["result"] === "object" && !Array.isArray(obj["result"])) {
        const nestedStatus = (obj["result"] as Json)["status"];
        if (nestedStatus !== undefined) state = normalizeState(nestedStatus);
      }
    } else if (obj["success"] !== undefined) {
      state = obj["success"] ? "success" : "error";
    } else if (message) {
      state = normalizeState(message);
    } else {
      state = "success";
    }

    if (
      message &&
      normalizeState(message) === "not_configured"
    ) {
      state = "not_configured";
    }
  } else {
    state = normalizeState(value);
    message = typeof value === "string" ? value : undefined;
  }

  return {
    key,
    label,
    state,
    message,
    raw: value,
  };
}

/**
 * Derive per-stage state from workflow/agent responses.
 *
 * Supports the actual FastAPI workflow response:
 *
 * {
 *   workflow: "lead_pipeline",
 *   results: [
 *     {
 *       agent: "research",
 *       result: {
 *         status: "completed",
 *         result: {...}
 *       }
 *     }
 *   ],
 *   status: "partial"
 * }
 *
 * Also supports older stages/result/direct-map response formats.
 */
export function deriveStages(payload: unknown): StageResult[] {
  if (!payload || typeof payload !== "object") {
    return [];
  }

  const root = payload as Json;

  /*
   * Actual FastAPI workflow response format:
   *
   * {
   *   "results": [
   *     {
   *       "agent": "research",
   *       "result": {
   *         "status": "completed",
   *         "result": {...}
   *       }
   *     }
   *   ]
   * }
   *
   * The outer "status" describes execution of the Manager/agent wrapper.
   * The nested "result.status" describes the actual stage outcome.
   */
  if (Array.isArray(root["results"])) {
    const stages: StageResult[] = [];

    for (const item of root["results"]) {
      if (
        !item ||
        typeof item !== "object" ||
        Array.isArray(item)
      ) {
        continue;
      }

      const entry = item as Json;
      const agent = entry["agent"];

      if (
        typeof agent !== "string" ||
        !agent.trim()
      ) {
        continue;
      }

      const wrapper = entry["result"];

      /*
       * Backend currently returns:
       *
       * result: {
       *   status: "completed",
       *   agent_used: "...",
       *   task: "...",
       *   result: {
       *     status: "error" | "skipped" | "completed",
       *     ...
       *   }
       * }
       *
       * Use the nested result object when present so the UI
       * reflects the real stage outcome.
       */
      const stagePayload =
        wrapper &&
        typeof wrapper === "object" &&
        !Array.isArray(wrapper) &&
        (wrapper as Json)["result"] &&
        typeof (wrapper as Json)["result"] === "object" &&
        !Array.isArray((wrapper as Json)["result"])
          ? (wrapper as Json)["result"]
          : wrapper;

      const stage = normalizeStage(
        agent,
        stagePayload,
      );

      if (stage) {
        stages.push(stage);
      }
    }

    return stages;
  }

  /*
   * Backward-compatible stages/result/direct response formats.
   */
  let source: Json;

  if (
    root["stages"] &&
    typeof root["stages"] === "object" &&
    !Array.isArray(root["stages"])
  ) {
    source = root["stages"] as Json;
  } else if (
    root["result"] &&
    typeof root["result"] === "object" &&
    !Array.isArray(root["result"])
  ) {
    source = root["result"] as Json;
  } else {
    source = root;
  }

  const stages: StageResult[] = [];

  for (const [key, value] of Object.entries(source)) {
    const stage = normalizeStage(key, value);

    if (stage) {
      stages.push(stage);
    }
  }

  return stages;
}

/** True when the payload (or an error message) says the integration is missing. */
export function isNotConfigured(payload: unknown): boolean {
  if (!payload) {
    return false;
  }

  const text =
    typeof payload === "string"
      ? payload
      : JSON.stringify(payload);

  return /not[_\s-]?configured|no[_\s-]?provider|missing[_\s-]?credential|not[_\s-]?connected/i.test(
    text,
  );
}

export const rowsOf = extractItems;





