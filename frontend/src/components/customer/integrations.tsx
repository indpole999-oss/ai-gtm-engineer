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
  connect_available: boolean;
  execution_available: boolean;
};

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
        : "Returned from Google. Check the saved connection status below; this does not enable calendar writes.",
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
  const unavailable = rows.filter(
    (r) => !(calendar && r.category === "calendar" && r.provider === "google"),
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
      {calendar ? (
        <section className="g-panel space-y-4" aria-label="Google Calendar connection">
          <h2 className="text-xl font-semibold">Google Calendar</h2>
          <p className="text-sm text-muted-foreground">
            Authorize with Google to verify calendar access. Meeting creation and calendar writes
            are currently unavailable.
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
        Email sending, CRM sync and calendar writes are unavailable. Saving credentials or verifying
        access does not enable these actions.
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
