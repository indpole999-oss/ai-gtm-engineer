import { useData } from "./ui";

export type ResearchReadiness = {
  provider: string;
  state: string;
  can_attempt: boolean;
  message: string;
};

export function useResearchReadiness() {
  return useData<ResearchReadiness>("/api/v1/research/readiness");
}

// Only these non-secret response fields are exposed in provider diagnostics.
export function readinessDetails(value: ResearchReadiness) {
  return {
    provider: value.provider,
    state: value.state,
    can_attempt: value.can_attempt,
  };
}
