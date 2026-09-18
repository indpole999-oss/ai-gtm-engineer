import { useQuery } from "@tanstack/react-query";

import {
  getHealth,
  listAgents,
  listCompanies,
  listContacts,
  listCrm,
  listEmails,
  listLeads,
  listMeetings,
  listWorkflows,
  rowsOf,
} from "./gtm-api";

const retry = (failureCount: number, error: unknown) => {
  const status = (error as { status?: number }).status;
  if (status && status < 500) return false;
  return failureCount < 1;
};

export const useLeads = () => useQuery({ queryKey: ["leads"], queryFn: listLeads, retry });
export const useCompanies = () => useQuery({ queryKey: ["companies"], queryFn: listCompanies, retry });
export const useContacts = () => useQuery({ queryKey: ["contacts"], queryFn: listContacts, retry });
export const useEmails = () => useQuery({ queryKey: ["emails"], queryFn: listEmails, retry });
export const useCrm = () => useQuery({ queryKey: ["crm"], queryFn: listCrm, retry });
export const useMeetings = () => useQuery({ queryKey: ["calendar"], queryFn: listMeetings, retry });
export const useAgents = () => useQuery({ queryKey: ["agents"], queryFn: listAgents, retry });
export const useWorkflows = () => useQuery({ queryKey: ["workflows"], queryFn: listWorkflows, retry });
export const useHealth = () => useQuery({ queryKey: ["health"], queryFn: getHealth, retry });

/** Read a field from a backend row, trying several plausible key spellings. */
export function pick(row: Record<string, unknown>, keys: string[]): unknown {
  for (const key of keys) {
    const value = row[key];
    if (value !== undefined && value !== null && value !== "") return value;
  }
  return undefined;
}

export function text(row: Record<string, unknown>, keys: string[], fallback = "—"): string {
  const v = pick(row, keys);
  if (v === undefined) return fallback;
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

export const rows = rowsOf;
