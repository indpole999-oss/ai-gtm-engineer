/**
 * Aligned with the AI GTM Engineer FastAPI OpenAPI spec (v1.0.0).
 * All routes are mounted under /api/v1.
 */

export const API_BASE_URL: string =
  (import.meta.env["VITE_API_BASE_URL"] as string | undefined)?.replace(/\/$/, "") ??
  "http://localhost:8000";

export const API_PREFIX = "/api/v1";

export const AUTH_ENDPOINTS = {
  /** OAuth2 password flow: application/x-www-form-urlencoded username+password */
  token: `${API_PREFIX}/auth/login`,
  register: `${API_PREFIX}/auth/register`,
  me: `${API_PREFIX}/auth/me`,
} as const;

export const HEALTH_ENDPOINT = `${API_PREFIX}/health`;

export type ResourceKey =
  | "leads"
  | "companies"
  | "contacts"
  | "workflows"
  | "emails"
  | "agents"
  | "crm"
  | "calendar";

export const RESOURCE_ENDPOINTS: Record<ResourceKey, string> = {
  leads: `${API_PREFIX}/leads/`,
  companies: `${API_PREFIX}/companies/`,
  contacts: `${API_PREFIX}/contacts/`,
  workflows: `${API_PREFIX}/workflows/`,
  emails: `${API_PREFIX}/emails/`,
  agents: `${API_PREFIX}/agents/`,
  crm: `${API_PREFIX}/crm/`,
  calendar: `${API_PREFIX}/calendar/`,
};

export const ACTION_ENDPOINTS = {
  enrichLead: (contactId: string) =>
    `${API_PREFIX}/leads/enrich/${contactId}`,

  sendEmail: `${API_PREFIX}/emails/send`,

  runAgent: `${API_PREFIX}/agents/run`,

  research: `${API_PREFIX}/agents/research`,

  runWorkflow: `${API_PREFIX}/workflows/run`,

  bookMeeting: `${API_PREFIX}/calendar/book`,

  calendarAuth: `${API_PREFIX}/calendar/auth`,

  crmCompany: `${API_PREFIX}/crm/company`,

  crmDeal: `${API_PREFIX}/crm/deal`,
  crmActivity: `${API_PREFIX}/crm/activity`,
} as const;

export const TOKEN_STORAGE_KEY = "gtm.access_token";

