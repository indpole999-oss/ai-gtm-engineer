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
