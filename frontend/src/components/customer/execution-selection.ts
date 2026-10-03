// Only opaque IDs go in the URL. Plan content and approval acknowledgements do not.
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export function readExecutionSelection(search: string, workspaceId: string) {
  const params = new URLSearchParams(search);
  const valid = params.get("gtm_workspace") === workspaceId;
  const plan = params.get("gtm_plan") || "";
  const cycle = params.get("gtm_cycle") || "";
  return {
    plan: valid && uuid.test(plan) ? plan : "",
    cycle: valid && uuid.test(cycle) ? cycle : "",
  };
}
export function executionSearch(search: string, workspaceId: string, plan: string, cycle: string) {
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
export function planAuthorLabel(method: string) {
  if (method.startsWith("ollama:")) return "local AI";
  if (method.startsWith("groq:")) return "hosted AI";
  if (method === "explicit_research_template") return "guided research template";
  if (["reviewed_outreach", "reviewed_outcome"].includes(method)) return "reviewed external action";
  return method === "customer_revision" ? "customer revision" : "unknown author method";
}
