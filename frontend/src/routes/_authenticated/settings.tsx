import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  RefreshCw,
  XCircle,
  Plus,
  Trash2,
  Plug,
  Loader2,
} from "lucide-react";
import { useEffect, useState } from "react";

import { PageHeader } from "@/components/page-header";
import { CompanyBrainEditor } from "@/components/company-brain";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { apiFetch, ApiError } from "@/lib/api";
import {
  API_BASE_URL,
  AUTH_ENDPOINTS,
  HEALTH_ENDPOINT,
  RESOURCE_ENDPOINTS,
  type ResourceKey,
} from "@/lib/api-config";
import { displayName, useAuth } from "@/lib/auth";
import { humanizeKey } from "@/lib/format";
import { isNotConfigured } from "@/lib/gtm-api";
import {
  useCrm,
  useEmails,
  useHealth,
  useMeetings,
} from "@/lib/gtm-queries";

export const Route = createFileRoute("/_authenticated/settings")({
  head: () => ({
    meta: [
      { title: "Settings — AI GTM Engineer" },
      {
        name: "description",
        content:
          "Account, backend connection, health and integration status for the GTM console.",
      },
      {
        property: "og:title",
        content: "Settings — AI GTM Engineer",
      },
      {
        property: "og:description",
        content:
          "Account, backend connection and integrations.",
      },
      {
        property: "og:type",
        content: "website",
      },
      {
        name: "twitter:card",
        content: "summary",
      },
    ],
  }),
  component: SettingsPage,
});

type ProbeResult = Record<
  string,
  {
    ok: boolean;
    status: number | string;
  }
>;

type Integration = {
  id: string;
  category: string;
  provider: string;
  auth_type: string;
  config: Record<string, unknown>;
  status: string;
  last_connected_at: string | null;
  last_error: string | null;
  created_at: string | null;
  updated_at: string | null;
};

type IntegrationCategory = "crm" | "enrichment" | "email" | "calendar" | "search";
type ProviderDefinition = {
  name: string;
  description: string;
  auth: "api_key" | "oauth2";
};
const PROVIDERS: Record<IntegrationCategory, ProviderDefinition[]> = {
  crm: [
    { name: "Salesforce", description: "Use an existing access token and your Salesforce instance URL.", auth: "oauth2" },
    { name: "HubSpot", description: "Connect a private app token for your CRM.", auth: "api_key" },
  ],
  enrichment: [{ name: "Apollo", description: "Connect your existing account for buyer enrichment.", auth: "api_key" }],
  email: [
    { name: "Gmail", description: "Connect an existing authorized mailbox token. Reconnect when it expires.", auth: "oauth2" },
    { name: "Outlook", description: "Connect an existing Microsoft mailbox token. Reconnect when it expires.", auth: "oauth2" },
    { name: "Resend", description: "Connect your sending account and approved sender address.", auth: "api_key" },
  ],
  calendar: [{ name: "Google Calendar", description: "Authorize your calendar securely with Google.", auth: "oauth2" }],
  search: [{ name: "Serper", description: "Use your search account. Saving a connection does not spend search credits.", auth: "api_key" }],
};
const CATEGORY_LABELS: Record<IntegrationCategory, string> = {
  crm: "CRM", enrichment: "Enrichment", email: "Email", calendar: "Calendar", search: "Search",
};
const CATEGORY_DESCRIPTIONS: Record<IntegrationCategory, string> = {
  crm: "Connect the CRM your company uses.",
  enrichment: "Connect a source of buyer and company information.",
  email: "Connect your approved sending identity.",
  calendar: "Connect the calendar used for meetings.",
  search: "Connect the search provider used for research.",
};

function integrationState(query: {
  isPending: boolean;
  isError: boolean;
  error: unknown;
  data: unknown;
}) {
  if (query.isPending) {
    return "pending" as const;
  }

  if (isNotConfigured(query.data)) {
    return "not_configured" as const;
  }

  if (query.isError) {
    const err = query.error;

    if (err instanceof ApiError) {
      if (
        isNotConfigured(
          err.detail ?? err.message,
        )
      ) {
        return "not_configured" as const;
      }

      if (
        err.status === 404 ||
        err.status === 501
      ) {
        return "not_configured" as const;
      }
    }

    return "error" as const;
  }

  return "success" as const;
}

function SettingsPage() {
  const {
    user,
    profileUnavailable,
    signOut,
    refresh,
  } = useAuth();

  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [probing, setProbing] = useState(false);
  const [results, setResults] =
    useState<ProbeResult | null>(null);

  const [integrations, setIntegrations] =
    useState<Integration[]>([]);
  const [loadingIntegrations, setLoadingIntegrations] =
    useState(false);

  const [selectedCategory, setSelectedCategory] =
    useState<IntegrationCategory>("crm");

  const [selectedProvider, setSelectedProvider] =
    useState<ProviderDefinition | null>(null);

  const [credentials, setCredentials] =
    useState("");

  const [config, setConfig] =
    useState("");

  const [savingIntegration, setSavingIntegration] =
    useState(false);

  const [testingId, setTestingId] =
    useState<string | null>(null);

  const [deletingId, setDeletingId] =
    useState<string | null>(null);

  const [startingGoogleOAuth, setStartingGoogleOAuth] =
    useState(false);

  const [integrationMessage, setIntegrationMessage] =
    useState<string | null>(null);

  const health = useHealth();
  const crm = useCrm();
  const meetings = useMeetings();
  const emails = useEmails();

  async function loadIntegrations() {
    setLoadingIntegrations(true);

    try {
      const response = await apiFetch<
        | Integration[]
        | {
            items?: Integration[];
            integrations?: Integration[];
            data?: Integration[];
            count?: number;
          }
      >("/api/v1/integrations/");

      const items = Array.isArray(response)
        ? response
        : response.items ??
          response.integrations ??
          response.data ??
          [];

      setIntegrations(items);
    } catch (error) {
      console.error(
        "Failed to load integrations:",
        error,
      );
    } finally {
      setLoadingIntegrations(false);
    }
  }

  useEffect(() => {
    void loadIntegrations();
    const url = new URL(window.location.href);
    if (url.searchParams.has("connection")) {
      setIntegrationMessage(url.searchParams.get("connection") === "success"
        ? "Google Calendar connected. Your workspace connection is ready."
        : "Calendar connection was not completed. Please try again.");
      url.searchParams.delete("connection");
      window.history.replaceState({}, "", url.pathname + url.search);
    }
  }, []);

  async function probe() {
    setProbing(true);

    const entries = Object.entries(
      RESOURCE_ENDPOINTS,
    ) as [ResourceKey, string][];

    const next: ProbeResult = {};

    await Promise.all(
      [
        ...entries,
        [
          "health",
          HEALTH_ENDPOINT,
        ] as [string, string],
        [
          "auth profile",
          AUTH_ENDPOINTS.me,
        ] as [string, string],
      ].map(async ([key, path]) => {
        try {
          await apiFetch(path);

          next[key] = {
            ok: true,
            status: 200,
          };
        } catch (error) {
          const status = (
            error as {
              status?: number;
            }
          ).status;

          next[key] = {
            ok: false,
            status:
              status === 0
                ? "offline"
                : (status ?? "error"),
          };
        }
      }),
    );

    setResults(next);
    setProbing(false);
  }

  async function handleSignOut() {
    await queryClient.cancelQueries();

    queryClient.clear();

    signOut();

    navigate({
      to: "/login",
      replace: true,
    });
  }

  async function startGoogleCalendarOAuth() {
    setStartingGoogleOAuth(true);
    setIntegrationMessage(null);

    try {
      const response =
        await apiFetch<{
          authorization_url: string;
        }>(
          "/api/v1/calendar/oauth/google/start",
        );

      if (!response.authorization_url) {
        throw new Error(
          "Google OAuth authorization URL was not returned.",
        );
      }

      window.location.href =
        response.authorization_url;
    } catch (error) {
      const message =
        error instanceof ApiError
          ? error.message
          : error instanceof Error
            ? error.message
            : "Unable to start Google Calendar OAuth.";

      setIntegrationMessage(message);
      setStartingGoogleOAuth(false);
    }
  }

  async function saveIntegration() {
    if (!selectedProvider) {
      setIntegrationMessage(
        "Select a provider first.",
      );
      return;
    }

    if (
      selectedCategory === "calendar" &&
      selectedProvider.name === "Google Calendar"
    ) {
      await startGoogleCalendarOAuth();
      return;
    }

    if (!credentials.trim()) {
      setIntegrationMessage(
        "Enter the provider credentials before connecting.",
      );
      return;
    }

    setSavingIntegration(true);
    setIntegrationMessage(null);

    let parsedConfig: Record<
      string,
      unknown
    > = {};

    if (config.trim()) {
      try {
        parsedConfig = JSON.parse(config);
      } catch {
        setIntegrationMessage(
          "Configuration must be valid JSON.",
        );
        setSavingIntegration(false);
        return;
      }
    }

    try {
      const created =
        await apiFetch<Integration>(
          "/api/v1/integrations/",
          {
            method: "POST",
            body: JSON.stringify({
              category: selectedCategory,

              provider:
                selectedProvider.name
                  .toLowerCase()
                  .replace(/\s+/g, "_"),

              auth_type:
                selectedProvider.auth,

              credentials: {
                access_token:
                  credentials.trim(),
              },

              config: parsedConfig,
            }),
          },
        );

      setIntegrations((current) => [
        created,
        ...current,
      ]);

      setSelectedProvider(null);
      setCredentials("");
      setConfig("");

      setIntegrationMessage(
        `${selectedProvider.name} configuration saved.`,
      );
    } catch (error) {
      const message =
        error instanceof ApiError
          ? error.message
          : "Unable to save integration.";

      setIntegrationMessage(message);
    } finally {
      setSavingIntegration(false);
    }
  }

  async function testIntegration(
    id: string,
  ) {
    setTestingId(id);
    setIntegrationMessage(null);

    try {
      const response =
        await apiFetch<{
          success: boolean;
          integration: Integration;
          message?: string;
        }>(
          `/api/v1/integrations/${id}/test`,
          {
            method: "POST",
          },
        );

      setIntegrations((current) =>
        current.map((item) =>
          item.id === id
            ? response.integration
            : item,
        ),
      );

      setIntegrationMessage(
        response.message ??
          "Connection check completed. Review its status below.",
      );
    } catch (error) {
      const message =
        error instanceof ApiError
          ? error.message
          : "Integration test failed.";

      setIntegrationMessage(message);

      await loadIntegrations();
    } finally {
      setTestingId(null);
    }
  }

  async function deleteIntegration(
    id: string,
  ) {
    setDeletingId(id);
    setIntegrationMessage(null);

    try {
      await apiFetch(
        `/api/v1/integrations/${id}`,
        {
          method: "DELETE",
        },
      );

      setIntegrations((current) =>
        current.filter(
          (item) => item.id !== id,
        ),
      );

      setIntegrationMessage(
        "Local connection removed. Revoke its token at the provider if needed.",
      );
    } catch (error) {
      const message =
        error instanceof ApiError
          ? error.message
          : "Unable to disconnect integration.";

      setIntegrationMessage(message);
    } finally {
      setDeletingId(null);
    }
  }

  function openProvider(
    provider: ProviderDefinition,
  ) {
    setSelectedProvider(provider);
    setCredentials("");
    setConfig("");
    setIntegrationMessage(null);
  }

  const healthEntries = Object.entries(
    health.data ?? {},
  ).filter(
    ([, v]) =>
      v === null ||
      typeof v !== "object",
  );

  const legacyIntegrations = [
    {
      name: "Email records API",
      state: integrationState(emails),
      note: "Backed by the email API.",
    },
    {
      name: "CRM",
      state: integrationState(crm),
      note: "CRM records API responsiveness.",
    },
    {
      name: "Calendar",
      state: integrationState(meetings),
      note: "Meeting records API responsiveness.",
    },
    {
      name: "Backend health API",
      state: health.isPending
        ? ("pending" as const)
        : health.isError
          ? ("error" as const)
          : ("success" as const),
      note:
        "Reported through the backend health endpoint.",
    },
  ];

  return (
    <div className="max-w-5xl space-y-6">
      <PageHeader
        title="Settings"
        description="Account, backend connection and integrations for your GTM workspace."
        actions={
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              void health.refetch();
              void crm.refetch();
              void meetings.refetch();
              void emails.refetch();
              void loadIntegrations();
            }}
          >
            <RefreshCw
              className="size-4"
              aria-hidden
            />
            Refresh
          </Button>
        }
      />

      {/* ACCOUNT */}

      <CompanyBrainEditor />

      <section className="rounded-lg border bg-card p-5 shadow-xs">
        <h2 className="text-sm font-semibold">
          Account
        </h2>

        <p className="mt-3 text-sm">
          Signed in as{" "}
          <span className="font-medium">
            {displayName(user)}
          </span>
        </p>

        {profileUnavailable ? (
          <p className="mt-2 text-sm text-warning">
            The profile endpoint is not available,
            so only the access token is known.
          </p>
        ) : user ? (
          <dl className="mt-4 space-y-2 text-sm">
            {Object.entries(user)
              .filter(
                ([, v]) =>
                  v === null ||
                  typeof v !== "object",
              )
              .map(([key, value]) => (
                <div
                  key={key}
                  className="flex justify-between gap-4 border-b pb-2 last:border-0"
                >
                  <dt className="text-muted-foreground">
                    {humanizeKey(key)}
                  </dt>

                  <dd className="font-mono text-xs">
                    {String(value)}
                  </dd>
                </div>
              ))}
          </dl>
        ) : null}

        <div className="mt-5 flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => refresh()}
          >
            Refresh session
          </Button>

          <Button
            variant="destructive"
            size="sm"
            onClick={handleSignOut}
          >
            Sign out
          </Button>
        </div>
      </section>

      {/* BACKEND */}

      <section className="rounded-lg border bg-card p-5 shadow-xs">
        <h2 className="text-sm font-semibold">
          Backend connection
        </h2>

        <dl className="mt-4 space-y-3 text-sm">
          <div className="flex justify-between gap-4">
            <dt className="text-muted-foreground">
              API base URL
            </dt>

            <dd className="font-mono text-xs">
              {API_BASE_URL}
            </dd>
          </div>

          <div className="flex justify-between gap-4">
            <dt className="text-muted-foreground">
              Token endpoint
            </dt>

            <dd className="font-mono text-xs">
              {AUTH_ENDPOINTS.token}
            </dd>
          </div>

          <div className="flex justify-between gap-4">
            <dt className="text-muted-foreground">
              Profile endpoint
            </dt>

            <dd className="font-mono text-xs">
              {AUTH_ENDPOINTS.me}
            </dd>
          </div>
        </dl>

        <p className="mt-4 text-xs text-muted-foreground">
          Set{" "}
          <span className="font-mono">
            VITE_API_BASE_URL
          </span>{" "}
          to point at a different FastAPI server.
          No API keys are stored directly in this
          frontend.
        </p>
      </section>

      {/* UNIVERSAL INTEGRATIONS */}

      <section className="rounded-lg border bg-card p-5 shadow-xs">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-sm font-semibold">
              Universal Integrations
            </h2>

            <p className="mt-1 text-xs text-muted-foreground">
              Connect the tools your company already
              uses. GTM Engineer is not locked to one
              CRM, enrichment provider, email system
              or calendar.
            </p>
          </div>

          <Plug
            className="size-5 text-muted-foreground"
            aria-hidden
          />
        </div>

        {integrationMessage ? (
          <div className="mt-4 rounded-md border p-3 text-sm">
            {integrationMessage}
          </div>
        ) : null}

        <div className="mt-5 grid gap-5 lg:grid-cols-[180px_1fr]">
          {/* CATEGORIES */}

          <div className="space-y-2">
            {(
              Object.keys(
                CATEGORY_LABELS,
              ) as IntegrationCategory[]
            ).map((category) => (
              <button
                key={category}
                type="button"
                onClick={() => {
                  setSelectedCategory(category);
                  setSelectedProvider(null);
                  setCredentials("");
                  setConfig("");
                  setIntegrationMessage(null);
                }}
                className={`w-full rounded-md border px-3 py-2 text-left text-sm transition ${
                  selectedCategory === category
                    ? "bg-accent font-medium"
                    : "hover:bg-muted"
                }`}
              >
                {CATEGORY_LABELS[category]}
              </button>
            ))}
          </div>

          {/* PROVIDERS */}

          <div>
            <h3 className="text-sm font-medium">
              {CATEGORY_LABELS[selectedCategory]}
            </h3>

            <p className="mt-1 text-xs text-muted-foreground">
              {
                CATEGORY_DESCRIPTIONS[
                  selectedCategory
                ]
              }
            </p>

            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {PROVIDERS[selectedCategory].map(
                (provider) => {
                  const providerKey =
                    provider.name
                      .toLowerCase()
                      .replace(/\s+/g, "_");

                  const connected =
                    integrations.some(
                      (item) =>
                        item.category ===
                          selectedCategory &&
                        item.provider ===
                          (provider.name ===
                          "Google Calendar"
                            ? "google"
                            : providerKey) &&
                        item.status ===
                          "connected",
                    );

                  return (
                    <div
                      key={provider.name}
                      className="rounded-lg border p-4"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-medium">
                            {provider.name}
                          </p>

                          <p className="mt-1 text-xs text-muted-foreground">
                            {provider.description}
                          </p>
                        </div>

                        {connected ? (
                          <CheckCircle2
                            className="size-4 text-success"
                            aria-hidden
                          />
                        ) : null}
                      </div>

                      <Button
                        className="mt-4 w-full"
                        variant={
                          connected
                            ? "outline"
                            : "default"
                        }
                        size="sm"
                        onClick={() =>
                          openProvider(provider)
                        }
                      >
                        {connected
                          ? "Configure"
                          : "Connect"}
                      </Button>
                    </div>
                  );
                },
              )}
            </div>
          </div>
        </div>

        {/* CONNECT FORM */}

        {selectedProvider ? (
          <div className="mt-6 rounded-lg border bg-muted/30 p-5">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold">
                  Connect {selectedProvider.name}
                </h3>

                <p className="mt-1 text-xs text-muted-foreground">
                  Authentication:{" "}
                  {selectedProvider.auth ===
                  "api_key"
                    ? "API Key"
                    : selectedProvider.auth ===
                        "oauth2"
                      ? "OAuth 2.0"
                      : "Custom"}
                </p>
              </div>

              <Button
                variant="ghost"
                size="sm"
                onClick={() =>
                  setSelectedProvider(null)
                }
              >
                Cancel
              </Button>
            </div>

            {selectedCategory === "calendar" &&
            selectedProvider.name ===
              "Google Calendar" ? (
              <div className="mt-4 rounded-md border bg-background p-4">
                <p className="text-sm">
                  Google Calendar uses secure OAuth
                  authentication. No credentials need
                  to be pasted here.
                </p>

                <p className="mt-2 text-xs text-muted-foreground">
                  Click the button below to continue to
                  Google and authorize calendar access.
                </p>

                <Button
                  className="mt-4"
                  onClick={() =>
                    void startGoogleCalendarOAuth()
                  }
                  disabled={startingGoogleOAuth}
                >
                  {startingGoogleOAuth ? (
                    <>
                      <Loader2
                        className="size-4 animate-spin"
                        aria-hidden
                      />
                      Connecting…
                    </>
                  ) : (
                    "Connect Google Calendar"
                  )}
                </Button>
              </div>
            ) : (
              <div className="mt-4 space-y-4">
                <div>
                  <label className="text-xs font-medium">
                    Credentials
                  </label>

                  <textarea
                    value={credentials}
                    onChange={(event) =>
                      setCredentials(
                        event.target.value,
                      )
                    }
                    placeholder={
                      selectedProvider.auth ===
                      "api_key"
                        ? "Paste API key"
                        : "Paste credential / token"
                    }
                    className="mt-2 min-h-24 w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2"
                  />

                  <p className="mt-1 text-xs text-muted-foreground">
                    Credentials are sent to the backend,
                    not stored in the browser UI.
                  </p>
                </div>

                <div>
                  <label className="text-xs font-medium">
                    Configuration
                  </label>

                  <textarea
                    value={config}
                    onChange={(event) =>
                      setConfig(
                        event.target.value,
                      )
                    }
                    placeholder='Optional JSON, e.g. {"base_url":"https://api.example.com"}'
                    className="mt-2 min-h-20 w-full rounded-md border bg-background px-3 py-2 font-mono text-xs outline-none focus:ring-2"
                  />
                </div>

                <Button
                  onClick={() =>
                    void saveIntegration()
                  }
                  disabled={savingIntegration}
                >
                  {savingIntegration ? (
                    <>
                      <Loader2
                        className="size-4 animate-spin"
                        aria-hidden
                      />
                      Saving…
                    </>
                  ) : (
                    <>
                      <Plus
                        className="size-4"
                        aria-hidden
                      />
                      Save Connection
                    </>
                  )}
                </Button>
              </div>
            )}
          </div>
        ) : null}

        {/* CONNECTED INTEGRATIONS */}

        <div className="mt-6">
          <h3 className="text-sm font-semibold">
            Connected integrations
          </h3>

          {loadingIntegrations ? (
            <p className="mt-3 text-sm text-muted-foreground">
              Loading integrations…
            </p>
          ) : integrations.length === 0 ? (
            <p className="mt-3 text-sm text-muted-foreground">
              No integrations connected yet.
            </p>
          ) : (
            <div className="mt-3 space-y-2">
              {integrations.map(
                (integration) => (
                  <div
                    key={integration.id}
                    className="flex items-center justify-between gap-4 rounded-md border p-3"
                  >
                    <div>
                      <p className="text-sm font-medium">
                        {humanizeKey(
                          integration.provider,
                        )}
                      </p>

                      <p className="text-xs text-muted-foreground">
                        {
                          CATEGORY_LABELS[
                            integration.category as IntegrationCategory
                          ]
                        }{" "}
                        · {integration.auth_type}
                      </p>
                    </div>

                    <div className="flex items-center gap-2">
                      <StatusBadge
                        value={
                          integration.status
                        }
                      />

                      <Button
                        variant="outline"
                        size="sm"
                        disabled={
                          testingId ===
                          integration.id
                        }
                        onClick={() =>
                          void testIntegration(
                            integration.id,
                          )
                        }
                      >
                        {testingId ===
                        integration.id ? (
                          <Loader2 className="size-4 animate-spin" />
                        ) : (
                          "Test"
                        )}
                      </Button>

                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={
                          deletingId ===
                          integration.id
                        }
                        onClick={() =>
                          void deleteIntegration(
                            integration.id,
                          )
                        }
                      >
                        {deletingId ===
                        integration.id ? (
                          <Loader2 className="size-4 animate-spin" />
                        ) : (
                          <Trash2
                            className="size-4"
                            aria-hidden
                          />
                        )}
                      </Button>
                    </div>
                  </div>
                ),
              )}
            </div>
          )}
        </div>
      </section>

      {/* LEGACY / CURRENT BACKEND STATUS */}

      <section className="rounded-lg border bg-card p-5 shadow-xs">
        <h2 className="text-sm font-semibold">
          Endpoint availability
        </h2>

        <p className="mt-1 text-xs text-muted-foreground">
          These checks show API responsiveness only. Provider connection health
          appears on each saved integration above.
        </p>

        <ul className="mt-4 space-y-2">
          {legacyIntegrations.map(
            (integration) => (
              <li
                key={integration.name}
                className="flex items-center justify-between gap-3 border-b pb-3 last:border-0"
              >
                <div>
                  <p className="text-sm font-medium">
                    {integration.name}
                  </p>

                  <p className="text-xs text-muted-foreground">
                    {integration.note}
                  </p>
                </div>

                <StatusBadge
                  state={integration.state}
                />
              </li>
            ),
          )}
        </ul>
      </section>

      {/* HEALTH */}

      <section className="rounded-lg border bg-card p-5 shadow-xs">
        <h2 className="text-sm font-semibold">
          Health status
        </h2>

        {health.isPending ? (
          <p className="mt-3 text-sm text-muted-foreground">
            Checking backend health…
          </p>
        ) : health.isError ? (
          <p className="mt-3 text-sm text-destructive">
            Health endpoint unreachable — the backend
            may be offline or the base URL is wrong.
          </p>
        ) : healthEntries.length === 0 ? (
          <p className="mt-3 text-sm text-muted-foreground">
            The health endpoint returned no scalar
            fields.
          </p>
        ) : (
          <dl className="mt-4 space-y-2 text-sm">
            {healthEntries.map(
              ([key, value]) => (
                <div
                  key={key}
                  className="flex items-center justify-between gap-4 border-b pb-2 last:border-0"
                >
                  <dt className="text-muted-foreground">
                    {humanizeKey(key)}
                  </dt>

                  <dd>
                    <StatusBadge
                      value={value}
                    />
                  </dd>
                </div>
              ),
            )}
          </dl>
        )}
      </section>

      {/* ENDPOINT HEALTH */}

      <section className="rounded-lg border bg-card p-5 shadow-xs">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-sm font-semibold">
            Endpoint health
          </h2>

          <Button
            size="sm"
            variant="outline"
            onClick={probe}
            disabled={probing}
          >
            {probing
              ? "Checking…"
              : "Run check"}
          </Button>
        </div>

        {results ? (
          <ul className="mt-4 space-y-2 text-sm">
            {Object.entries(results).map(
              ([key, value]) => (
                <li
                  key={key}
                  className="flex items-center justify-between gap-3 border-b pb-2 last:border-0"
                >
                  <span className="flex items-center gap-2">
                    {value.ok ? (
                      <CheckCircle2
                        className="size-4 text-success"
                        aria-hidden
                      />
                    ) : (
                      <XCircle
                        className="size-4 text-destructive"
                        aria-hidden
                      />
                    )}

                    {humanizeKey(key)}
                  </span>

                  <span className="font-mono text-xs text-muted-foreground">
                    {value.status}
                  </span>
                </li>
              ),
            )}
          </ul>
        ) : (
          <p className="mt-3 text-sm text-muted-foreground">
            Run a check to see which backend routes
            respond for your account.
          </p>
        )}
      </section>
    </div>
  );
}
