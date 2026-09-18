/**
 * Parses email-sequence steps out of the existing email_sequence workflow response.
 * Nothing is invented: a field that the backend did not return stays undefined and
 * the UI omits it rather than showing a placeholder value.
 */
import { normalizeState, type BackendState, type Json } from "./gtm-api";

export interface SequenceStep {
  /** Index in the returned array (stable key). */
  index: number;
  /** Step number from the backend if present, else the 1-based position. */
  stepNumber: number;
  stepNumberFromBackend: boolean;
  subject?: string | undefined;
  body?: string | undefined;
  delayDays?: number | undefined;
  scheduledAt?: string | undefined;
  status?: string | undefined;
  state: BackendState;
  raw: Json;
}

const SUBJECT_KEYS = ["subject", "subject_line", "title", "headline"];
const BODY_KEYS = ["body", "content", "email_body", "message", "text", "html", "draft"];
const DELAY_KEYS = ["delay_days", "delay", "wait_days", "days", "day", "send_after_days", "offset_days"];
const SCHEDULE_KEYS = ["send_at", "scheduled_at", "scheduled_for", "send_date", "scheduled", "timing"];
const STEP_KEYS = ["step", "step_number", "sequence_number", "order", "position", "number"];
const STATUS_KEYS = ["status", "state", "send_status", "delivery_status"];

function str(obj: Json, keys: string[]): string | undefined {
  for (const key of keys) {
    const v = obj[key];
    if (typeof v === "string" && v.trim()) return v;
  }
  return undefined;
}

function num(obj: Json, keys: string[]): number | undefined {
  for (const key of keys) {
    const v = obj[key];
    if (typeof v === "number" && Number.isFinite(v)) return v;
    if (typeof v === "string" && v.trim() !== "" && Number.isFinite(Number(v))) return Number(v);
  }
  return undefined;
}

function looksLikeEmail(value: unknown): value is Json {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const obj = value as Json;
  return (
    SUBJECT_KEYS.some((k) => typeof obj[k] === "string") ||
    BODY_KEYS.some((k) => typeof obj[k] === "string")
  );
}

/** Depth-first search for the first array whose entries look like generated emails. */
function findStepArray(value: unknown, depth = 0): Json[] | null {
  if (depth > 5 || !value || typeof value !== "object") return null;
  if (Array.isArray(value)) {
    const emails = value.filter(looksLikeEmail);
    if (emails.length > 0 && emails.length === value.length) return emails;
    for (const entry of value) {
      const nested = findStepArray(entry, depth + 1);
      if (nested) return nested;
    }
    return null;
  }
  const obj = value as Json;
  // Prefer explicitly named containers before scanning everything else.
  for (const key of ["sequence", "steps", "emails", "email_sequence", "drafts", "messages"]) {
    const found = findStepArray(obj[key], depth + 1);
    if (found) return found;
  }
  for (const nestedValue of Object.values(obj)) {
    const found = findStepArray(nestedValue, depth + 1);
    if (found) return found;
  }
  return null;
}

export function parseSequenceSteps(payload: unknown): SequenceStep[] {
  const found = findStepArray(payload);
  if (!found) return [];
  return found.map((raw, index) => {
    const backendStep = num(raw, STEP_KEYS);
    const status = str(raw, STATUS_KEYS);
    const sentFlag = raw["sent"];
    const state: BackendState =
      status !== undefined
        ? normalizeState(status)
        : typeof sentFlag === "boolean"
          ? sentFlag
            ? "success"
            : "generated"
          : "generated";
    return {
      index,
      stepNumber: backendStep ?? index + 1,
      stepNumberFromBackend: backendStep !== undefined,
      subject: str(raw, SUBJECT_KEYS),
      body: str(raw, BODY_KEYS),
      delayDays: num(raw, DELAY_KEYS),
      scheduledAt: str(raw, SCHEDULE_KEYS),
      status,
      state,
      raw,
    };
  });
}

/** Human timing label — only derived from data the backend actually returned. */
export function timingLabel(step: SequenceStep): string | undefined {
  if (step.scheduledAt) {
    const parsed = new Date(step.scheduledAt);
    if (!Number.isNaN(parsed.getTime())) {
      return parsed.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
    }
    return step.scheduledAt;
  }
  if (step.delayDays === undefined) return undefined;
  if (step.delayDays === 0) return "Sends immediately";
  return `Sends ${step.delayDays} day${step.delayDays === 1 ? "" : "s"} after the previous step`;
}
