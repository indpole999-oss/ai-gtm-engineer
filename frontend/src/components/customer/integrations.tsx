import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
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
export function IntegrationsPage() {
  const { canApprove } = useWorkspace();
  const cache = useQueryClient();
  const connections = useData<{ integrations: Integration[] }>("/api/v1/integrations"),
    providers = useData<Provider[]>("/api/v1/integrations/providers");
  const [selected, setSelected] = useState<Provider | null>(null),
    [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false);
  async function act(path: string, method: string, body?: unknown) {
    setBusy(true);
    try {
      await apiFetch(path, { method, body: body === undefined ? null : JSON.stringify(body) });
      await cache.invalidateQueries({ queryKey: ["customer"] });
      setMessage("Connection record updated. The provider-reported state is shown below.");
      setSelected(null);
    } catch (e) {
      setMessage(friendlyError(e));
    } finally {
      setBusy(false);
    }
  }
  async function oauth() {
    setBusy(true);
    try {
      const result = await apiFetch<{ authorization_url: string }>(
        "/api/v1/calendar/oauth/google/start",
      );
      const url = new URL(result.authorization_url);
      if (url.protocol !== "https:" || url.hostname !== "accounts.google.com")
        throw new Error("Unexpected authorization destination");
      window.location.assign(url.href);
    } catch (e) {
      setMessage(friendlyError(e));
      setBusy(false);
    }
  }
  return (
    <>
      <Heading
        title="Integrations"
        description="Connect the tools you trust. See connection health and required attention without exposing credentials."
      />
      <Feedback message={message} />
      {connections.isPending || providers.isPending ? (
        <Loading />
      ) : connections.isError || providers.isError ? (
        <ErrorState
          retry={() => {
            void connections.refetch();
            void providers.refetch();
          }}
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {providers.data?.map((p) => {
            const connected =
              connections.data?.integrations.filter(
                (i) => i.category === p.category && i.provider === p.provider,
              ) || [];
            return (
              <Panel key={p.category + p.provider}>
                <div
                  className="mb-6 flex size-11 items-center justify-center rounded-xl bg-accent text-lg font-semibold text-primary"
                  aria-hidden
                >
                  {p.provider.slice(0, 1).toUpperCase()}
                </div>
                <p className="eyebrow uppercase">{p.category}</p>
                <h2 className="mt-2 text-xl font-semibold capitalize">
                  {p.provider.replaceAll("_", " ")}
                </h2>
                {!connected.length && (
                  <p className="my-4 text-sm text-muted-foreground">Not connected</p>
                )}
                {connected.map((i) => (
                  <div key={i.id} className="mt-4 space-y-3 border-t pt-4">
                    <div className="flex flex-wrap gap-2">
                      <Status value={i.status} />
                      <Status value={i.health} />
                    </div>
                    {i.reconnect_required && (
                      <p className="text-sm text-destructive">Reconnect required</p>
                    )}
                    <details className="text-xs">
                      <summary>Connection permissions</summary>
                      <ul className="mt-2 break-all">
                        {i.scopes?.length ? (
                          i.scopes.map((s) => <li key={s}>{s}</li>)
                        ) : (
                          <li>Scopes have not been reported.</li>
                        )}
                      </ul>
                    </details>
                    {canApprove && (
                      <div className="flex flex-wrap gap-2">
                        <button
                          disabled={busy}
                          className="g-button g-button-secondary"
                          onClick={() => void act(`/api/v1/integrations/${i.id}/test`, "POST")}
                        >
                          Check health
                        </button>
                        <details>
                          <summary className="py-3 text-xs">Disconnect</summary>
                          <p className="my-2 text-xs">
                            This removes the local connection. Revoke access at the provider
                            separately.
                          </p>
                          <button
                            disabled={busy}
                            className="g-button g-button-secondary"
                            onClick={() => void act(`/api/v1/integrations/${i.id}`, "DELETE")}
                          >
                            Confirm disconnect
                          </button>
                        </details>
                      </div>
                    )}
                  </div>
                ))}
                {canApprove && (
                  <button
                    disabled={busy}
                    className="g-button mt-5"
                    onClick={() => (p.provider === "google" ? void oauth() : setSelected(p))}
                  >
                    {connected.length ? "Add or reconnect" : "Connect"}
                  </button>
                )}
                {!canApprove && (
                  <p className="mt-5 text-xs text-muted-foreground">
                    An owner or admin manages connections.
                  </p>
                )}
              </Panel>
            );
          })}
        </div>
      )}
      {selected && canApprove && (
        <Panel title={`Connect ${selected.provider}`}>
          <p className="mb-5 text-sm text-muted-foreground">
            Credentials are stored securely by the server and never returned. Saving does not verify
            health or enable automatic actions.
          </p>
          <form
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              const auth = String(f.get("auth_type"));
              const config = Object.fromEntries(
                selected.config_keys.map((k) => [k, String(f.get(k) || "")]).filter(([, v]) => v),
              );
              void act("/api/v1/integrations", "POST", {
                category: selected.category,
                provider: selected.provider,
                auth_type: auth,
                credentials: {
                  [auth === "api_key" ? "api_key" : "access_token"]: f.get("credential"),
                },
                config,
              });
              e.currentTarget.reset();
            }}
          >
            <Field label="Authorization method">
              <select className="g-input" name="auth_type">
                {selected.auth_types.map((a) => (
                  <option key={a} value={a}>
                    {a === "oauth2" ? "Existing authorized access token" : a.replaceAll("_", " ")}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Provider credential">
              <input
                className="g-input"
                type="password"
                name="credential"
                required
                autoComplete="off"
              />
            </Field>
            {selected.config_keys.map((k) => (
              <Field key={k} label={k.replaceAll("_", " ")}>
                <input className="g-input" name={k} required={k === "instance_url"} />
              </Field>
            ))}
            <div className="flex gap-3">
              <button className="g-button" disabled={busy}>
                Save connection
              </button>
              <button
                className="g-button g-button-secondary"
                type="button"
                onClick={() => setSelected(null)}
              >
                Cancel
              </button>
            </div>
          </form>
        </Panel>
      )}
      <p className="text-xs text-muted-foreground">
        A healthy connection is not approval to act. Sending, CRM writes and calendar creation
        retain their separate review and provider-confirmation requirements.
      </p>
    </>
  );
}
