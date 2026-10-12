import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { Heading, Loading, ErrorState, Feedback, friendlyError, useData } from "./ui";
import { connectionLabel, type Integration } from "./contracts";

type Provider = {
  category: string;
  provider: string;
  auth_types: string[];
  connect_available: boolean;
  execution_available: boolean;
  read_available: boolean;
  write_available: boolean;
  reason: string;
};

function TokenConnection({
  provider,
  connections,
  canApprove,
  refreshed,
  remove,
}: {
  provider: Provider;
  connections: Integration[];
  canApprove: boolean;
  refreshed: () => Promise<unknown>;
  remove: (row: Integration) => void;
}) {
  const [token, setToken] = useState("");
  const [authMethod, setAuthMethod] = useState<"api_key" | "bearer">(
    provider.auth_types.includes("api_key") ? "api_key" : "bearer",
  );
  const [secret, setSecret] = useState("");
  const [config, setConfig] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [editing, setEditing] = useState<Integration | null>(null);
  async function save() {
    setBusy(true);
    setMessage("");
    try {
      await apiFetch(editing ? `/api/v1/integrations/${editing.id}` : "/api/v1/integrations", {
        method: editing ? "PUT" : "POST",
        body: JSON.stringify({
          ...(editing ? {} : {
            category: provider.category,
            provider: provider.provider,
            auth_type: authMethod,
          }),
          credentials: { [authMethod === "bearer" ? "access_token" : "api_key"]: token, ...(secret ? { webhook_secret: secret } : {}) },
          config: provider.provider === "resend"
            ? { from_email: config }
            : provider.provider === "salesforce"
              ? { instance_url: config }
              : ["custom", "configured"].includes(provider.provider)
                ? { tool_name: config }
                : {},
        }),
      });
      setToken("");
      setSecret("");
      setConfig("");
      setEditing(null);
      await refreshed();
      setMessage("Credentials saved securely. Use Check access to verify the provider; no external action was performed.");
    } catch (error) {
      setToken("");
      setSecret("");
      setMessage(friendlyError(error));
    } finally {
      setBusy(false);
    }
  }
  async function check(connection: Integration) {
    setBusy(true);
    try {
      const result = await apiFetch<{ integration: Integration }>(
        `/api/v1/integrations/${connection.id}/test`,
        { method: "POST" },
      );
      await refreshed();
      setMessage(connectionLabel(result.integration));
    } catch (error) {
      setMessage(friendlyError(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="g-panel space-y-3" aria-label={`${provider.provider} connection`}>
      <h2 className="text-xl font-semibold capitalize">
        {provider.provider === "configured" ? "Supported research provider" : provider.provider}
      </h2>
      <p className="text-sm">{provider.reason}</p>
      <p className="text-sm">
        Reads: {provider.read_available ? "Available with verified access" : "Paused"} · Writes:{" "}
        {provider.write_available ? "Reviewed approval required" : "Unavailable"}
      </p>
      <Feedback message={message} />
      {connections.map((row) => (
        <article key={row.id} className="space-y-2">
          <p>{connectionLabel(row)}</p>
          {canApprove && (
            <button
              className="g-button g-button-secondary"
              disabled={busy}
              onClick={() => void check(row)}
            >
              Check {provider.provider} access
            </button>
          )}
          {canApprove && (
            <button type="button" className="g-button g-button-secondary" disabled={busy}
              onClick={() => {
                setEditing(row);
                setAuthMethod(row.auth_type === "bearer" ? "bearer" : "api_key");
                setToken("");
                setSecret("");
                setConfig(String(row.config?.[provider.provider === "resend" ? "from_email" : provider.provider === "salesforce" ? "instance_url" : "tool_name"] || ""));
                setMessage("Enter replacement credentials below. Existing access stays unchanged until saved.");
              }}>
              Reconnect / replace credentials
            </button>
          )}
          {canApprove && (
            <button
              className="g-button g-button-secondary"
              disabled={busy}
              onClick={() => remove(row)}
            >
              Remove saved connection
            </button>
          )}
        </article>
      ))}
      {(!connections.length || editing !== null) && canApprove && (
        <form
          className="space-y-3"
          onSubmit={(event) => {
            event.preventDefault();
            void save();
          }}
        >
          {provider.auth_types.includes("api_key") && provider.auth_types.includes("bearer") && (
            <label className="block">
              Authentication method
              <select className="g-input" value={authMethod} disabled={editing !== null}
                onChange={(event) => setAuthMethod(event.target.value as "api_key" | "bearer")}>
                <option value="api_key">API key</option>
                <option value="bearer">Bearer token</option>
              </select>
            </label>
          )}
          <label className="block">
            {provider.provider} {authMethod === "bearer" ? "Bearer token" : "API key"}
            <input
              className="g-input"
              type="password"
              autoComplete="off"
              required
              value={token}
              onChange={(event) => setToken(event.target.value)}
            />
          </label>
          {["custom", "configured"].includes(provider.provider) && (
            <label className="block">
              Provider or integration name
              <input className="g-input" required value={config}
                onChange={(event) => setConfig(event.target.value)}
                placeholder="Name of your custom integration" />
            </label>
          )}
          {provider.provider === "resend" && (
            <>
              <label className="block">
                Verified sender email
                <input
                  className="g-input"
                  type="email"
                  required
                  value={config}
                  onChange={(event) => setConfig(event.target.value)}
                />
              </label>
              <label className="block">
                Webhook signing secret
                <input
                  className="g-input"
                  type="password"
                  autoComplete="off"
                  value={secret}
                  onChange={(event) => setSecret(event.target.value)}
                />
              </label>
            </>
          )}
          {provider.provider === "salesforce" && (
            <label className="block">
              Salesforce instance URL
              <input
                className="g-input"
                type="url"
                required
                value={config}
                onChange={(event) => setConfig(event.target.value)}
              />
            </label>
          )}
          <div className="flex flex-wrap gap-2">
            <button className="g-button" disabled={busy}>
              {editing ? `Replace ${provider.provider} credentials` : `Save ${provider.provider} connection`}
            </button>
            {editing && (
              <button type="button" className="g-button g-button-secondary" disabled={busy}
                onClick={() => {
                  setEditing(null);
                  setToken("");
                  setSecret("");
                  setConfig("");
                  setMessage("Credential replacement cancelled; saved connection was not changed.");
                }}>
                Cancel
              </button>
            )}
          </div>
        </form>
      )}
      {!canApprove && <p>Ask a workspace owner or admin to manage this connection.</p>}
    </section>
  );
}

type CalendarTest = {
  id: string;
  status: string;
  title: string;
  provider_event_id: string | null;
  start: { dateTime: string };
  end: { dateTime: string };
  verified_at: string | null;
  receipt: { html_link?: string | null; version: string } | null;
};

function CalendarVerification({
  connection,
  canApprove,
}: {
  connection: Integration;
  canApprove: boolean;
}) {
  const path = `/api/v1/integrations/${connection.id}/calendar-test-event`;
  const result = useData<{ event: CalendarTest | null }>(path);
  const [busy, setBusy] = useState(false);
  const [review, setReview] = useState(false);
  const [message, setMessage] = useState("");
  const event = result.data?.event;
  const healthy =
    connection.status === "connected" &&
    connection.health === "healthy" &&
    !connection.reconnect_required;
  async function verify() {
    setBusy(true);
    setMessage("");
    try {
      const response = await apiFetch<{ event: CalendarTest }>(path, { method: "POST" });
      await result.refetch();
      setMessage(
        response.event.status === "confirmed"
          ? "Google returned the event and the backend saved the verified result."
          : "Google could not confirm this event. Check calendar access, then retry verification. No success is assumed.",
      );
    } catch (error) {
      setMessage(friendlyError(error));
    } finally {
      setBusy(false);
    }
  }
  if (result.isPending) return <Loading />;
  if (result.isError) return <ErrorState retry={() => void result.refetch()} />;
  return (
    <div className="space-y-3 border-t pt-3">
      <h4 className="font-medium">Verify event creation</h4>
      <p className="text-sm">
        {event
          ? "The saved test event is shown below. Verification reads the same event from Google; it does not schedule another meeting."
          : "Create one real 10-minute test event on this calendar, starting 10 minutes from now. No attendees, invitations, reminders or prospect updates. Retries reuse the same event."}
      </p>
      <Feedback message={message} />
      {event && (
        <div className="space-y-1 text-sm" aria-label="Saved Google event result">
          <p>
            {event.status === "confirmed" ? "Confirmed by Google" : "Event not currently verified"}{" "}
            · {event.title}
          </p>
          <p>
            {new Date(event.start.dateTime).toLocaleString()} –{" "}
            {new Date(event.end.dateTime).toLocaleTimeString()}
          </p>
          <p className="break-all">
            Google event ID: {event.provider_event_id || "Not confirmed yet"}
          </p>
          {event.verified_at && (
            <p>Last verified: {new Date(event.verified_at).toLocaleString()}</p>
          )}
          {event.receipt?.version && (
            <p className="break-all text-xs">Google revision: {event.receipt.version}</p>
          )}
          {event.receipt?.html_link && (
            <a
              className="underline"
              href={event.receipt.html_link}
              target="_blank"
              rel="noopener noreferrer"
            >
              Open event in Google Calendar
            </a>
          )}
        </div>
      )}
      {canApprove && (
        <button
          className="g-button"
          disabled={busy || !healthy}
          onClick={() => (event ? void verify() : setReview(true))}
        >
          {busy
            ? "Checking Google…"
            : event
              ? "Verify same event with Google"
              : "Create test calendar event"}
        </button>
      )}
      {!healthy && (
        <p className="text-sm">Verify calendar access before creating or checking an event.</p>
      )}
      <ConfirmDialog
        open={review}
        onOpenChange={setReview}
        title="Create a real test event?"
        description={`Google Calendar (${String(connection.config?.["calendar_id"] || "primary")}) will receive one event titled “GAPS AI — test calendar connection”, lasting 10 minutes and starting 10 minutes from now. There are no attendees or invitations.`}
        confirmLabel="Create real test event"
        onConfirm={() => {
          setReview(false);
          void verify();
        }}
      />
    </div>
  );
}

export function IntegrationsPage() {
  const { canApprove, workspace } = useWorkspace();
  const cache = useQueryClient();
  const connections = useData<{ integrations: Integration[] }>("/api/v1/integrations");
  const providers = useData<Provider[]>("/api/v1/integrations/providers");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [disconnect, setDisconnect] = useState<Integration | null>(null);

  useEffect(() => {
    const url = new URL(window.location.href);
    const result = url.searchParams.get("connection");
    if (!result) return;
    setMessage(
      result === "failed"
        ? "Google authorization was not completed. Your saved connection has not been replaced."
        : "Returned from Google. Check the saved connection status below before creating a test event.",
    );
    void cache.invalidateQueries({ queryKey: ["customer", workspace.id, "/api/v1/integrations"] });
    url.searchParams.delete("connection");
    window.history.replaceState(window.history.state, "", url);
  }, [cache, workspace.id]);

  async function act(connection: Integration, method: "POST" | "DELETE") {
    setBusy(true);
    setMessage("");
    try {
      const result = await apiFetch<{ integration?: Integration }>(
        `/api/v1/integrations/${connection.id}${method === "POST" ? "/test" : ""}`,
        { method },
      );
      await cache.invalidateQueries({ queryKey: ["customer", workspace.id] });
      setMessage(
        method === "DELETE"
          ? "Saved connection removed. Revoke access at the provider if needed."
          : result.integration
            ? connectionLabel(result.integration)
            : "Access check did not return a verified result.",
      );
    } catch (error) {
      setMessage(friendlyError(error));
    } finally {
      setBusy(false);
    }
  }

  async function googleOAuth(connection?: Integration) {
    setBusy(true);
    setMessage("");
    try {
      const query = connection ? `?integration_id=${encodeURIComponent(connection.id)}` : "";
      const result = await apiFetch<{ authorization_url: string }>(
        `/api/v1/calendar/oauth/google/start${query}`,
      );
      const url = new URL(result.authorization_url);
      if (url.protocol !== "https:" || url.hostname !== "accounts.google.com")
        throw new Error("Unexpected authorization destination");
      window.location.assign(url.href);
    } catch (error) {
      setMessage(friendlyError(error));
      setBusy(false);
    }
  }

  if (connections.isPending || providers.isPending) return <Loading />;
  if (connections.isError || providers.isError)
    return (
      <ErrorState
        retry={() => {
          void connections.refetch();
          void providers.refetch();
        }}
      />
    );
  const rows = connections.data?.integrations ?? [];
  const calendar = providers.data?.find(
    (p) => p.category === "calendar" && p.provider === "google" && p.connect_available,
  );
  const calendars = rows.filter((r) => r.category === "calendar" && r.provider === "google");
  const catalog = [
    { title: "Calendars", category: "calendar", options: [["google", "Google Calendar"], ["calendly", "Calendly"], ["custom", "Custom"]] },
    { title: "Email", category: "email", options: [["gmail", "Gmail"], ["outlook", "Outlook"], ["custom", "Custom"]] },
    { title: "CRM", category: "crm", options: [["hubspot", "HubSpot"], ["salesforce", "Salesforce"], ["custom", "Custom"]] },
    { title: "Enrichment", category: "enrichment", options: [["apollo", "Apollo"], ["hunter", "Hunter.io"], ["custom", "Custom"]] },
    { title: "Research", category: "research", options: [["configured", "Supported Provider Configuration"], ["custom", "Custom"]] },
    { title: "Email Delivery", category: "delivery", options: [["resend", "Resend"], ["custom", "Custom"]] },
  ];
  const tokenProviders = providers.data?.filter(
    (p) => p.connect_available && !(p.category === "calendar" && p.provider === "google"),
  ) ?? [];
  const unavailable = rows.filter(
    (r) =>
      !(calendar && r.category === "calendar" && r.provider === "google") &&
      !tokenProviders.some((p) => p.provider === r.provider && p.category === r.category),
  );
  const removeButton = (row: Integration) =>
    canApprove && (
      <button
        disabled={busy}
        className="g-button g-button-secondary"
        onClick={() => setDisconnect(row)}
      >
        Remove saved connection
      </button>
    );

  return (
    <>
      <Heading
        title="Integrations"
        description="Review provider access separately from permission to act. Only available connection flows are offered."
      />
      <Feedback message={message} />
      {catalog.map((group) => (
        <section key={group.category} className="space-y-3" aria-label={`${group.title} integrations`}>
          <h2 className="text-xl font-semibold">{group.title}</h2>
          <div className="grid gap-3 md:grid-cols-2">
            {group.options.map(([key, label], index) => {
              const provider = tokenProviders.find((p) => p.category === group.category && p.provider === key);
              if (provider) return (
                <TokenConnection
                  key={`${workspace.id}:${group.category}:${key}:${index}`}
                  provider={provider}
                  connections={rows.filter((row) => row.provider === key && row.category === group.category)}
                  canApprove={canApprove}
                  remove={setDisconnect}
                  refreshed={() => cache.invalidateQueries({ queryKey: ["customer", workspace.id] })}
                />
              );
              return (
                <article key={`${key}:${index}`} className="g-panel space-y-2">
                  <h3 className="font-semibold">{label}</h3>
                  <p className="text-sm text-muted-foreground">
                    {key === "google" && group.category === "calendar"
                      ? "Use the Google Calendar OAuth connection below."
                      : "Connection is not configured on this server. No credentials are requested."}
                  </p>
                </article>
              );
            })}
          </div>
        </section>
      ))}
      {calendar ? (
        <section className="g-panel space-y-4" aria-label="Google Calendar connection">
          <h2 className="text-xl font-semibold">Google Calendar</h2>
          <p className="text-sm text-muted-foreground">
            Verify calendar access and create a real test event. Customer meetings require the
            existing reviewed scheduling workflow.
          </p>
          <p className="text-sm">
            Use a dedicated test Google account. No Google password, API key or access token is
            needed here.
          </p>
          {calendars.length > 1 && (
            <p role="status" className="text-sm">
              Multiple saved connections exist. Reconnect the intended record below. Existing
              credentials are preserved until you explicitly remove a record.
            </p>
          )}
          {calendars.map((row, index) => (
            <article key={row.id} className="g-panel-subtle space-y-3">
              <h3 className="font-medium">Saved calendar connection {index + 1}</h3>
              <p>{connectionLabel(row)}</p>
              <p className="text-xs text-muted-foreground">
                Reference: {row.id.slice(0, 8)} · Calendar:{" "}
                {String(row.config?.["calendar_id"] || "primary")}
              </p>
              {canApprove && (
                <div className="flex flex-wrap gap-2">
                  <button
                    disabled={busy}
                    className="g-button"
                    onClick={() => void googleOAuth(row)}
                  >
                    Reconnect with Google
                  </button>
                  <button
                    disabled={busy}
                    className="g-button g-button-secondary"
                    onClick={() => void act(row, "POST")}
                  >
                    Check calendar access
                  </button>
                  {removeButton(row)}
                </div>
              )}
              {calendar.execution_available && (
                <CalendarVerification connection={row} canApprove={canApprove} />
              )}
            </article>
          ))}
          {!calendars.length && canApprove && (
            <button disabled={busy} className="g-button" onClick={() => void googleOAuth()}>
              Connect Google Calendar
            </button>
          )}
          {!canApprove && (
            <p className="text-sm">Ask a workspace owner or admin to manage this connection.</p>
          )}
        </section>
      ) : (
        <section className="g-panel space-y-3">
          <h2 className="text-xl font-semibold">No connection setup is available</h2>
          <p className="text-sm">
            Google Calendar authorization needs administrator configuration. Unsupported provider
            setup is hidden; no credentials are needed until a working connection flow is available.
          </p>
        </section>
      )}
      <p className="text-sm text-muted-foreground">
        {providers.data?.some((p) => p.category === "email" && p.write_available)
          ? "Email requires exact message and delivery approval. CRM writes remain unavailable."
          : "Email sending and CRM sync remain unavailable."}{" "}
        Calendar tests do not enable AI or automated outreach.
      </p>
      {unavailable.length > 0 && (
        <details className="g-panel">
          <summary>Previously saved connections ({unavailable.length})</summary>
          <p className="my-3 text-sm">
            These records are retained for review. They are not available execution integrations.
          </p>
          {unavailable.map((row) => (
            <article key={row.id} className="my-3 space-y-2 border-t pt-3">
              <h3 className="capitalize">
                {row.provider.replaceAll("_", " ")} · {row.category}
              </h3>
              <p className="text-sm">Saved record · setup unavailable · {row.id.slice(0, 8)}</p>
              {removeButton(row)}
            </article>
          ))}
        </details>
      )}
      <ConfirmDialog
        open={disconnect !== null}
        onOpenChange={(open) => {
          if (!open) setDisconnect(null);
        }}
        title="Remove this saved connection?"
        description="This deletes the saved credentials for this record. It does not revoke access at the provider. Keep the record if you still need it."
        confirmLabel="Remove connection"
        destructive
        onConfirm={() => {
          if (disconnect) void act(disconnect, "DELETE");
          setDisconnect(null);
        }}
      />
    </>
  );
}
