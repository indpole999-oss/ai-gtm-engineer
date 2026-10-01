import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  CalendarDays,
  Check,
  Database,
  Mail,
  Plug,
  Search,
  Sparkles,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace";
import {
  Heading,
  Panel,
  Status,
  Loading,
  ErrorState,
  Feedback,
  Field,
  friendlyError,
  useData,
} from "./ui";
import type { Integration } from "./contracts";

type Provider = { category: string; provider: string; auth_types: string[]; config_keys: string[] };

const CATEGORY_META: Record<string, { title: string; description: string; icon: typeof Mail }> = {
  email: {
    title: "Email",
    description: "Connect the inbox your GTM employee will work with.",
    icon: Mail,
  },
  crm: {
    title: "CRM",
    description: "Keep accounts, contacts and pipeline aligned with your system of record.",
    icon: Database,
  },
  calendar: {
    title: "Calendar",
    description: "Use your preferred calendar for approved meeting actions.",
    icon: CalendarDays,
  },
  search: {
    title: "Research",
    description: "Bring the search provider you trust for public account research.",
    icon: Search,
  },
  enrichment: {
    title: "Enrichment",
    description: "Connect enrichment data without locking your workspace to one vendor.",
    icon: Sparkles,
  },
};

const CATEGORY_ORDER = ["email", "crm", "calendar", "search", "enrichment"];

const DISPLAY_NAMES: Record<string, string> = {
  google: "Google Calendar",
  gmail: "Gmail",
  outlook: "Outlook",
  resend: "Resend",
  hubspot: "HubSpot",
  salesforce: "Salesforce",
  serper: "Serper",
  apollo: "Apollo",
  custom: "Other / Custom",
};

function displayName(provider: Provider, connection?: Integration) {
  if (provider.provider === "custom" && connection?.config?.tool_name) return connection.config.tool_name;
  return DISPLAY_NAMES[provider.provider] || provider.provider.replaceAll("_", " ");
}

function ProviderMark({ name }: { name: string }) {
  return (
    <div
      className="flex size-11 items-center justify-center rounded-xl border border-white/8 bg-white/[.035] text-sm font-semibold text-foreground shadow-[inset_0_1px_0_rgba(255,255,255,.035)]"
      aria-hidden
    >
      {name.slice(0, 1).toUpperCase()}
    </div>
  );
}

export function IntegrationsPage() {
  const { canApprove } = useWorkspace();
  const cache = useQueryClient();
  const connections = useData<{ integrations: Integration[] }>("/api/v1/integrations");
  const providers = useData<Provider[]>("/api/v1/integrations/providers");
  const [selected, setSelected] = useState<Provider | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const grouped = useMemo(() => {
    const list = providers.data || [];
    return CATEGORY_ORDER.map((category) => ({
      category,
      providers: list.filter((provider) => provider.category === category),
    })).filter((group) => group.providers.length);
  }, [providers.data]);

  async function act(path: string, method: string, body?: unknown) {
    setBusy(true);
    try {
      await apiFetch(path, { method, body: body === undefined ? null : JSON.stringify(body) });
      await cache.invalidateQueries({ queryKey: ["customer"] });
      setMessage("Connection updated.");
      setSelected(null);
    } catch (error) {
      setMessage(friendlyError(error));
    } finally {
      setBusy(false);
    }
  }

  async function googleOAuth() {
    setBusy(true);
    try {
      const result = await apiFetch<{ authorization_url: string }>("/api/v1/calendar/oauth/google/start");
      const url = new URL(result.authorization_url);
      if (url.protocol !== "https:" || url.hostname !== "accounts.google.com") {
        throw new Error("Unexpected authorization destination");
      }
      window.location.assign(url.href);
    } catch (error) {
      setMessage(friendlyError(error));
      setBusy(false);
    }
  }

  if (connections.isPending || providers.isPending) return <Loading />;
  if (connections.isError || providers.isError) {
    return (
      <ErrorState
        retry={() => {
          void connections.refetch();
          void providers.refetch();
        }}
      />
    );
  }

  return (
    <>
      <Heading
        title="Integrations"
        description="Connect the tools your AI GTM employee uses. Choose a supported provider or Other / Custom when your team uses something different."
      />
      <Feedback message={message} />

      <div className="space-y-6">
        {grouped.map(({ category, providers: categoryProviders }) => {
          const meta = CATEGORY_META[category] || {
            title: category,
            description: "Connect the tool your team already uses.",
            icon: Plug,
          };
          const Icon = meta.icon;
          return (
            <section key={category} className="g-panel">
              <div className="mb-6 flex items-start gap-4">
                <div className="flex size-11 items-center justify-center rounded-xl border border-primary/10 bg-primary/10 text-primary">
                  <Icon className="size-5" aria-hidden />
                </div>
                <div>
                  <h2 className="text-xl font-semibold tracking-tight">{meta.title}</h2>
                  <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">{meta.description}</p>
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                {categoryProviders.map((provider) => {
                  const matching =
                    connections.data?.integrations.filter(
                      (integration) =>
                        integration.category === provider.category &&
                        integration.provider === provider.provider,
                    ) || [];
                  const primary = matching[0];
                  const name = displayName(provider, primary);
                  const isGoogleCalendar =
                    provider.category === "calendar" && provider.provider === "google";

                  return (
                    <article key={provider.category + provider.provider} className="g-provider-tile">
                      <div className="flex items-start justify-between gap-3">
                        <ProviderMark name={name} />
                        {primary ? <Status value={primary.status} /> : null}
                      </div>
                      <h3 className="mt-5 text-base font-semibold capitalize">{name}</h3>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {provider.provider === "custom"
                          ? "Use the tool your team already has."
                          : primary
                            ? primary.health === "configured_unverified"
                              ? "Connected · provider verification unavailable"
                              : "Connection available"
                            : "Not connected"}
                      </p>

                      {matching.map((integration) => (
                        <div key={integration.id} className="mt-4 border-t pt-4">
                          <div className="flex flex-wrap gap-2">
                            <Status value={integration.health} />
                            {integration.reconnect_required ? <Status value="reconnect_required" /> : null}
                          </div>
                          {canApprove && (
                            <div className="mt-4 flex flex-wrap gap-2">
                              <button
                                disabled={busy}
                                className="g-button g-button-secondary"
                                onClick={() =>
                                  void act(`/api/v1/integrations/${integration.id}/test`, "POST")
                                }
                              >
                                Check
                              </button>
                              <button
                                disabled={busy}
                                className="g-button g-button-secondary"
                                onClick={() =>
                                  void act(`/api/v1/integrations/${integration.id}`, "DELETE")
                                }
                              >
                                Disconnect
                              </button>
                            </div>
                          )}
                        </div>
                      ))}

                      {canApprove && (
                        <button
                          disabled={busy}
                          className="g-button mt-5 w-full"
                          onClick={() => (isGoogleCalendar ? void googleOAuth() : setSelected(provider))}
                        >
                          {primary ? "Add or reconnect" : "Connect"}
                        </button>
                      )}
                    </article>
                  );
                })}
              </div>
            </section>
          );
        })}
      </div>

      {selected && canApprove && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/65 p-4 backdrop-blur-md">
          <div className="g-panel max-h-[90vh] w-full max-w-xl overflow-y-auto">
            <div className="mb-6 flex items-start justify-between gap-4">
              <div>
                <p className="eyebrow uppercase">{CATEGORY_META[selected.category]?.title || selected.category}</p>
                <h2 className="mt-2 text-2xl font-semibold">
                  {selected.provider === "custom" ? "Connect Other / Custom" : `Connect ${displayName(selected)}`}
                </h2>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  Enter only the credentials required for this connection. Secrets are encrypted and never returned to the browser after saving.
                </p>
              </div>
              <button
                className="g-button g-button-secondary"
                type="button"
                onClick={() => setSelected(null)}
                aria-label="Close"
              >
                ×
              </button>
            </div>

            <form
              className="space-y-4"
              onSubmit={(event) => {
                event.preventDefault();
                const form = new FormData(event.currentTarget);
                const auth = String(form.get("auth_type"));
                const isCustom = selected.provider === "custom";
                const config = Object.fromEntries(
                  selected.config_keys
                    .map((key) => [key, String(form.get(key) || "").trim()])
                    .filter(([, value]) => value),
                );
                const credential = String(form.get("credential") || "");
                const credentialKey = auth === "api_key" ? "api_key" : "access_token";

                void act("/api/v1/integrations", "POST", {
                  category: selected.category,
                  provider: selected.provider,
                  auth_type: auth,
                  credentials: { [credentialKey]: credential },
                  config,
                });
                event.currentTarget.reset();
                if (isCustom) setMessage("Custom connection saved. Provider verification depends on a native connector.");
              }}
            >
              {selected.provider === "custom" && (
                <Field label="Tool name">
                  <input
                    className="g-input"
                    name="tool_name"
                    placeholder="Your CRM, email, calendar or data tool"
                    required
                  />
                </Field>
              )}

              <Field label="Connection method">
                <select className="g-input" name="auth_type">
                  {selected.auth_types.map((auth) => (
                    <option key={auth} value={auth}>
                      {auth === "oauth2"
                        ? "OAuth access token"
                        : auth === "api_key"
                          ? "API key"
                          : auth === "bearer"
                            ? "Bearer token"
                            : auth.replaceAll("_", " ")}
                    </option>
                  ))}
                </select>
              </Field>

              <Field label="Credential">
                <input
                  className="g-input"
                  type="password"
                  name="credential"
                  required
                  autoComplete="off"
                  placeholder="Paste credential"
                />
              </Field>

              {selected.config_keys
                .filter((key) => key !== "tool_name")
                .map((key) => (
                  <Field key={key} label={key === "instance_url" ? "Instance / API URL (if required)" : key.replaceAll("_", " ")}>
                    <input className="g-input" name={key} required={key === "instance_url" && selected.provider === "salesforce"} />
                  </Field>
                ))}

              <button className="g-button w-full" disabled={busy}>
                {busy ? "Connecting…" : "Connect"}
              </button>
            </form>
          </div>
        </div>
      )}

      <div className="flex items-start gap-3 rounded-xl border border-white/7 bg-white/[.025] p-4 text-xs leading-5 text-muted-foreground">
        <Check className="mt-0.5 size-4 shrink-0 text-success" aria-hidden />
        <p>
          Connected does not mean permission to act. GAPS AI still requires the appropriate review and approval before outbound email, CRM writes or calendar actions.
        </p>
      </div>
    </>
  );
}
