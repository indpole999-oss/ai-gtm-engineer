import { API_BASE_URL, TOKEN_STORAGE_KEY } from "./api-config";

export type Json =
  | string
  | number
  | boolean
  | null
  | Json[]
  | { [key: string]: Json };

export type WorkflowState =
  | "success"
  | "warning"
  | "error"
  | "skipped"
  | "not_configured"
  | "unknown";

export interface WorkflowStage {
  agent: string;
  state: WorkflowState;
  result: Json;
  status: string;
}

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;

  try {
    return window.localStorage.getItem(TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null) {
  if (typeof window === "undefined") return;

  try {
    if (token) {
      window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
    } else {
      window.localStorage.removeItem(TOKEN_STORAGE_KEY);
    }
  } catch {
    /* storage unavailable */
  }
}

function describeDetail(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;

  if (Array.isArray(detail)) {
    const parts = detail
      .map((d) => {
        if (d && typeof d === "object" && "msg" in d) {
          const loc =
            "loc" in d && Array.isArray((d as { loc: unknown[] }).loc)
              ? (d as { loc: unknown[] }).loc.slice(-1).join(".")
              : "";

          const message = String((d as { msg: unknown }).msg);

          return loc ? `${loc}: ${message}` : message;
        }

        return String(d);
      })
      .filter(Boolean);

    if (parts.length) return parts.join(" · ");
  }

  if (
    detail &&
    typeof detail === "object" &&
    "message" in detail
  ) {
    return String((detail as { message: unknown }).message);
  }

  return fallback;
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const token = getToken();
  const headers = new Headers(init.headers);

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  if (
    init.body &&
    !(init.body instanceof FormData) &&
    !headers.has("Content-Type")
  ) {
    headers.set("Content-Type", "application/json");
  }

  headers.set("Accept", "application/json");

  let response: Response;

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers,
    });
  } catch {
    throw new ApiError(
      0,
      `Cannot reach the API at ${API_BASE_URL}. Check that the FastAPI server is running and CORS allows this origin.`,
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const responseText = await response.text();

  let payload: unknown = undefined;

  if (responseText) {
    try {
      payload = JSON.parse(responseText);
    } catch {
      payload = responseText;
    }
  }

  if (!response.ok) {
    const detail =
      payload &&
      typeof payload === "object" &&
      "detail" in payload
        ? (payload as { detail: unknown }).detail
        : payload;

    const fallback =
      response.status === 401
        ? "Your session has expired. Sign in again."
        : response.status === 403
          ? "You don't have access to this resource."
          : response.status === 404
            ? "This endpoint does not exist on the backend."
            : `Request failed with status ${response.status}.`;

    throw new ApiError(
      response.status,
      describeDetail(detail, fallback),
      detail,
    );
  }

  return payload as T;
}

/** A list may contain plain strings; keep them addressable by name. */
function normalizeList(list: unknown[]): Record<string, unknown>[] {
  return list.map((item) =>
    item && typeof item === "object"
      ? (item as Record<string, unknown>)
      : { name: String(item) },
  );
}

/**
 * Backends return a bare array, a paginated envelope,
 * or a name->description map. Handle all common shapes.
 */
export function extractItems(
  payload: unknown,
): Record<string, unknown>[] {
  if (Array.isArray(payload)) {
    return normalizeList(payload);
  }

  if (payload && typeof payload === "object") {
    const obj = payload as Record<string, unknown>;

    for (const key of [
      "items",
      "results",
      "data",
      "records",
      "leads",
      "emails",
      "workflows",
      "companies",
      "contacts",
      "meetings",
      "events",
    ]) {
      if (Array.isArray(obj[key])) {
        return normalizeList(obj[key] as unknown[]);
      }
    }

    const agents = obj["agents"];

    if (
      agents &&
      typeof agents === "object" &&
      !Array.isArray(agents)
    ) {
      return Object.entries(
        agents as Record<string, unknown>,
      ).map(([name, description]) => ({
        name,
        description,
      }));
    }

    for (const value of Object.values(obj)) {
      if (
        Array.isArray(value) &&
        value.every(
          (v) => v && typeof v === "object",
        )
      ) {
        return value as Record<string, unknown>[];
      }
    }
  }

  return [];
}

export function extractTotal(
  payload: unknown,
  fallback: number,
): number {
  if (
    payload &&
    typeof payload === "object" &&
    !Array.isArray(payload)
  ) {
    for (const key of [
      "total",
      "count",
      "total_count",
    ]) {
      const value = (payload as Record<string, unknown>)[key];

      if (typeof value === "number") {
        return value;
      }
    }
  }

  return fallback;
}

/**
 * Convert backend status values into the small state vocabulary
 * used by the workflow UI.
 */
export function normalizeState(
  value: unknown,
): WorkflowState {
  const status = String(value ?? "")
    .trim()
    .toLowerCase();

  if (
    status === "completed" ||
    status === "complete" ||
    status === "success" ||
    status === "succeeded" ||
    status === "done"
  ) {
    return "success";
  }

  if (
    status === "error" ||
    status === "failed" ||
    status === "failure"
  ) {
    return "error";
  }

  if (
    status === "partial" ||
    status === "warning" ||
    status === "warn"
  ) {
    return "warning";
  }

  if (
    status === "skipped" ||
    status === "skip"
  ) {
    return "skipped";
  }

  if (
    status === "not_configured" ||
    status === "not-configured" ||
    status === "not configured" ||
    status === "unconfigured"
  ) {
    return "not_configured";
  }

  return "unknown";
}

/**
 * Safely unwrap the result returned by ManagerAgent / WorkflowEngine.
 *
 * Depending on the agent implementation, a stage can look like:
 *
 * {
 *   status: "success",
 *   result: {...}
 * }
 *
 * or:
 *
 * {
 *   status: "success",
 *   result: {
 *     status: "completed",
 *     ...
 *   }
 * }
 */
function unwrapStageResult(
  value: unknown,
): {
  result: Json;
  status: unknown;
} {
  if (!value || typeof value !== "object") {
    return {
      result: value as Json,
      status: undefined,
    };
  }

  const obj = value as Record<string, unknown>;

  if ("result" in obj) {
    const inner = obj['result'];

    if (
      inner &&
      typeof inner === "object" &&
      !Array.isArray(inner)
    ) {
      const innerObj = inner as Record<string, unknown>;

      return {
        result: inner as Json,
        status:
          innerObj['status'] ??
          obj['status'],
      };
    }

    return {
      result: inner as Json,
      status: obj['status'],
    };
  }

  return {
    result: value as Json,
    status: obj['status'],
  };
}

/**
 * Extract the per-agent results returned by:
 *
 * WorkflowEngine.execute()
 *
 * {
 *   workflow: "...",
 *   results: [
 *     {
 *       agent: "research",
 *       result: ...
 *     }
 *   ],
 *   status: "...",
 *   context: {...}
 * }
 */
export function deriveStages(
  payload: Json,
): WorkflowStage[] {
  if (!payload || typeof payload !== "object") {
    return [];
  }

  const root = payload as Record<string, unknown>;
  const rawResults = root['results'];

  if (!Array.isArray(rawResults)) {
    return [];
  }

  return rawResults.map((item, index) => {
    if (!item || typeof item !== "object") {
      return {
        agent: `stage-${index + 1}`,
        state: "unknown",
        result: item as Json,
        status: "",
      };
    }

    const wrapper = item as Record<string, unknown>;

    const agent =
      typeof wrapper['agent'] === "string"
        ? wrapper['agent']
        : typeof wrapper['name'] === "string"
          ? wrapper['name']
          : `stage-${index + 1}`;

    const unwrapped = unwrapStageResult(
      wrapper['result'],
    );

    const rawStatus =
      unwrapped.status ??
      wrapper['status'];

    const state = normalizeState(rawStatus);

    return {
      agent,
      state,
      result: unwrapped.result,
      status: String(rawStatus ?? ""),
    };
  });
}

/**
 * Execute a workflow using the exact backend contract:
 *
 * POST /api/v1/workflows/run
 *
 * {
 *   workflow_name: "lead_pipeline",
 *   context: {...}
 * }
 */
export async function runWorkflow(
  workflowName: string,
  context: Json = {},
): Promise<Json> {
  return apiFetch<Json>("/workflows/run", {
    method: "POST",
    body: JSON.stringify({
      workflow_name: workflowName,
      context:
        context &&
        typeof context === "object" &&
        !Array.isArray(context)
          ? context
          : {},
    }),
  });
}
