const HIDDEN_KEYS = new Set(["password", "hashed_password", "embedding", "vector"]);

export function humanizeKey(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\bid\b/i, "ID")
    .replace(/\burl\b/i, "URL")
    .replace(/^\w/, (c) => c.toUpperCase());
}

export function isLikelyDate(key: string, value: unknown): boolean {
  return (
    typeof value === "string" &&
    /(_at|_on|date|time)$/i.test(key) &&
    !Number.isNaN(Date.parse(value))
  );
}

export function formatValue(key: string, value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (isLikelyDate(key, value)) {
    return new Date(value as string).toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    });
  }
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") return String(value);
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.length ? `${value.length} item(s)` : "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

/** Derive table columns from the rows the backend actually returned. */
export function deriveColumns(rows: Record<string, unknown>[], limit = 7): string[] {
  const seen: string[] = [];
  for (const row of rows.slice(0, 25)) {
    for (const key of Object.keys(row)) {
      if (HIDDEN_KEYS.has(key.toLowerCase())) continue;
      if (!seen.includes(key)) seen.push(key);
    }
  }
  const priority = ["name", "title", "full_name", "company", "email", "status", "state", "stage", "score"];
  seen.sort((a, b) => {
    const ai = priority.indexOf(a.toLowerCase());
    const bi = priority.indexOf(b.toLowerCase());
    if (ai === -1 && bi === -1) return 0;
    if (ai === -1) return 1;
    if (bi === -1) return -1;
    return ai - bi;
  });
  const idIndex = seen.findIndex((k) => k.toLowerCase() === "id");
  if (idIndex > 0) seen.unshift(seen.splice(idIndex, 1)[0]!);
  return seen.slice(0, limit);
}

export function rowLabel(row: Record<string, unknown>, fallback: string): string {
  for (const key of ["name", "title", "full_name", "email", "subject", "id"]) {
    const v = row[key];
    if (typeof v === "string" && v.trim()) return v;
    if (typeof v === "number") return String(v);
  }
  return fallback;
}

const STATUS_KEYS = ["status", "state", "stage", "is_active", "active", "enabled"];

export function findStatus(row: Record<string, unknown>): { key: string; value: unknown } | null {
  for (const key of STATUS_KEYS) {
    if (key in row && row[key] !== null && row[key] !== undefined) {
      return { key, value: row[key] };
    }
  }
  return null;
}

export function statusTone(value: unknown): "success" | "warning" | "danger" | "neutral" {
  if (value === true) return "success";
  if (value === false) return "neutral";
  const s = String(value).toLowerCase();
  if (/(active|running|completed|success|sent|won|enabled|replied|qualified)/.test(s)) return "success";
  if (/(pending|queued|draft|paused|scheduled|in_progress|processing|new)/.test(s)) return "warning";
  if (/(failed|error|bounced|lost|disabled|cancelled|canceled|unsubscribed)/.test(s)) return "danger";
  return "neutral";
}
