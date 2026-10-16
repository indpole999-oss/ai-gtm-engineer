type ResearchPlan = {
  id: string;
  document: {
    plan: {
      steps: { action: string; side_effect: string }[];
    };
  };
};

type Request = <T>(path: string, init?: RequestInit) => Promise<T>;

// Reuse the revision endpoint: it retains the goal and targets and creates only
// an unapproved draft. It neither invokes a planner nor queues execution.
export async function createResearchRevision<T extends ResearchPlan>(plan: T, request: Request): Promise<T> {
  const steps = plan.document.plan.steps;
  if (!steps.length || steps.some((step) => step.action !== "research" || step.side_effect !== "read_only")) {
    throw new Error("Only read-only research plans can be copied for review.");
  }
  return request<T>(`/api/v1/gtm/plans/${plan.id}/revisions`, {
    method: "POST",
    body: JSON.stringify(plan.document.plan),
  });
}
