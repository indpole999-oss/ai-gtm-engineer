// Only opaque IDs go in the URL or session storage. Plan content and approval acknowledgements do not.
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const storagePrefix = "gaps:gtm-selection:v1";

export type ExecutionSelection = { plan: string; cycle: string };
type StorageLike = Pick<Storage, "getItem" | "setItem" | "removeItem">;

function cleanSelection(plan: string, cycle: string): ExecutionSelection {
  return {
    plan: uuid.test(plan) ? plan : "",
    cycle: uuid.test(cycle) ? cycle : "",
  };
}

export function readExecutionSelection(search: string, workspaceId: string): ExecutionSelection {
  const params = new URLSearchParams(search);
  const valid = params.get("gtm_workspace") === workspaceId;
  return valid
    ? cleanSelection(params.get("gtm_plan") || "", params.get("gtm_cycle") || "")
    : { plan: "", cycle: "" };
}

export function executionSearch(
  search: string,
  workspaceId: string,
  plan: string,
  cycle: string,
) {
  const params = new URLSearchParams(search);
  params.set("gtm_workspace", workspaceId);
  for (const [key, value] of [
    ["gtm_plan", plan],
    ["gtm_cycle", cycle],
  ] as const) {
    if (value && uuid.test(value)) params.set(key, value);
    else params.delete(key);
  }
  return params.toString();
}

export function executionSelectionStorageKey(workspaceId: string, actorId: string) {
  if (!workspaceId.trim() || !actorId.trim()) return "";
  return `${storagePrefix}:${encodeURIComponent(actorId.trim())}:${encodeURIComponent(workspaceId.trim())}`;
}

export function readStoredExecutionSelection(
  storage: StorageLike | null,
  workspaceId: string,
  actorId: string,
): ExecutionSelection {
  const key = executionSelectionStorageKey(workspaceId, actorId);
  if (!storage || !key) return { plan: "", cycle: "" };
  try {
    const raw = storage.getItem(key);
    if (!raw) return { plan: "", cycle: "" };
    const parsed = JSON.parse(raw) as { plan?: unknown; cycle?: unknown };
    return cleanSelection(
      typeof parsed.plan === "string" ? parsed.plan : "",
      typeof parsed.cycle === "string" ? parsed.cycle : "",
    );
  } catch {
    return { plan: "", cycle: "" };
  }
}

export function writeStoredExecutionSelection(
  storage: StorageLike | null,
  workspaceId: string,
  actorId: string,
  plan: string,
  cycle: string,
) {
  const key = executionSelectionStorageKey(workspaceId, actorId);
  if (!storage || !key) return;
  const selection = cleanSelection(plan, cycle);
  try {
    if (!selection.plan && !selection.cycle) storage.removeItem(key);
    else storage.setItem(key, JSON.stringify(selection));
  } catch {
    // Storage can be blocked by privacy settings. URL state remains authoritative.
  }
}

export function resolveExecutionSelection(
  search: string,
  workspaceId: string,
  actorId: string,
  storage: StorageLike | null,
): { selection: ExecutionSelection; source: "url" | "storage" | "none" } {
  const params = new URLSearchParams(search);
  const hasExplicitSelection =
    params.has("gtm_workspace") || params.has("gtm_plan") || params.has("gtm_cycle");
  if (hasExplicitSelection) {
    return { selection: readExecutionSelection(search, workspaceId), source: "url" };
  }
  const selection = readStoredExecutionSelection(storage, workspaceId, actorId);
  return {
    selection,
    source: selection.plan || selection.cycle ? "storage" : "none",
  };
}

export function planAuthorLabel(method: string) {
  if (method.startsWith("ollama:")) return "local AI";
  if (method.startsWith("groq:")) return "hosted AI";
  if (method === "explicit_research_template") return "guided research template";
  if (["reviewed_outreach", "reviewed_outcome"].includes(method)) return "reviewed external action";
  return method === "customer_revision" ? "customer revision" : "unknown author method";
}
